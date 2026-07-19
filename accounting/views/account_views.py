from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import models
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from accounting.models import AccountType, AccountGroup, Account, AccountTag
from accounting.serializers.account_serializers import (
    AccountTypeSerializer,
    AccountGroupSerializer,
    AccountListSerializer,
    AccountDetailSerializer,
    AccountTagSerializer,
)


class AccountTypeViewSet(viewsets.ModelViewSet):
    queryset = AccountType.objects.all()
    serializer_class = AccountTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name"]

    ordering_fields = ["name", "created_at", "id"]
    ordering = ["-id"]


class AccountGroupViewSet(viewsets.ModelViewSet):
    queryset = AccountGroup.objects.select_related("parent", "account_type").all()
    serializer_class = AccountGroupSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "code_prefix_start"]

    ordering = ["-created_at"]

    @action(detail=False, methods=["get"])
    def tree(self, request):
        root_groups = self.filter_queryset(self.get_queryset()).filter(parent__isnull=True)
        serializer = self.get_serializer(root_groups, many=True)
        return Response(serializer.data)
    


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.select_related(
        "account_type", "account_group", "parent", "ngo_project"
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["code", "name"]
    filterset_fields = [
        "account_type",
        "account_group",
        "is_active",
        "is_deprecated",
        "is_reconcilable",
    ]
    ordering_fields = ["code", "name", "current_balance", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        ngo_project = self.request.query_params.get("ngo_project")
        global_only = self.request.query_params.get("global_only")
        if global_only in ("1", "true", "True"):
            return qs.filter(ngo_project__isnull=True)
        if ngo_project:
            # Project CoA + shared global bank/cash ledgers (active only)
            return qs.filter(
                models.Q(ngo_project_id=ngo_project)
                | models.Q(
                    ngo_project__isnull=True,
                    account_type__liquidity_type="bank_cash",
                    is_active=True,
                    is_deprecated=False,
                )
            ).distinct()
        return qs

    def get_serializer_class(self):
        if self.action in ["list"]:
            return AccountListSerializer
        if self.action in ["retrieve"]:
            return AccountDetailSerializer
        if self.action in ["create", "update", "partial_update"]:
            return AccountListSerializer
        return AccountDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        account = self.get_object()
        if account.ngo_project_id is None and (
            getattr(account.account_type, "liquidity_type", None) == "bank_cash"
            or account.bank_accounts.exists()
        ):
            return Response(
                {
                    "detail": (
                        "Global bank/cash accounts cannot be deleted from a "
                        "project chart. Manage them under Bank / Cash masters."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Return chart of accounts as a hierarchical tree."""
        accounts = self.filter_queryset(self.get_queryset()).filter(
            parent__isnull=True, is_active=True
        )
        serializer = AccountListSerializer(accounts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Return account summary by classification."""
        from django.db.models import Sum, Count

        data = {}
        qs_base = self.get_queryset().filter(is_active=True)
        for classification in ["asset", "liability", "equity", "income", "expense"]:
            qs = qs_base.filter(account_type__classification=classification)
            agg = qs.aggregate(
                total_balance=Sum("current_balance"),
                count=Count("id"),
            )
            data[classification] = {
                "count": agg["count"],
                "total_balance": str(agg["total_balance"] or 0),
            }
        return Response(data)

    @action(detail=False, methods=["post"])
    def seed(self, request):
        """Seed chart of accounts with standard NGO data (optionally per project)."""
        import io
        from django.core.management import call_command

        ngo_project = request.data.get("ngo_project") or request.query_params.get(
            "ngo_project"
        )
        out = io.StringIO()
        try:
            kwargs = {"stdout": out}
            if ngo_project:
                kwargs["ngo_project"] = int(ngo_project)
            call_command("seed_chart_of_accounts", **kwargs)
            message = out.getvalue().strip()
        except Exception as e:
            return Response(
                {"detail": f"Seeding failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        accounts_qs = Account.objects.all()
        if ngo_project:
            accounts_qs = accounts_qs.filter(
                models.Q(ngo_project_id=ngo_project)
                | models.Q(
                    ngo_project__isnull=True,
                    account_type__liquidity_type="bank_cash",
                )
            )
        accounts_count = accounts_qs.count()
        types_count = AccountType.objects.count()
        groups_count = AccountGroup.objects.count()

        return Response(
            {
                "detail": message or "Chart of accounts seeded successfully",
                "accounts_count": accounts_count,
                "types_count": types_count,
                "groups_count": groups_count,
                "ngo_project": ngo_project,
            }
        )

    @action(detail=False, methods=["get"])
    def relatable(self, request):
        """Return accounts relatable to vendor bill transactions.

        Query param ?type=expense|payment|payable filters to a specific group.
        Without ?type, returns all three groups tagged with a 'relatable_type' key.
        """
        relatable_type = request.query_params.get("type")

        def _serialize(qs, group_label):
            return [
                {
                    "id": a.id,
                    "code": a.code,
                    "name": a.name,
                    "classification": a.account_type.classification if a.account_type else "",
                    "relatable_type": group_label,
                }
                for a in qs
            ]

        data = {}

        if not relatable_type or relatable_type == "expense":
            # Expense / COGS accounts — for bill line items (DEBIT side of posting JE)
            expense_accounts = Account.objects.filter(
                account_type__classification="expense",
                is_active=True,
                is_deprecated=False,
            ).select_related("account_type").order_by("code")
            data["expense"] = _serialize(expense_accounts, "expense")

        if not relatable_type or relatable_type == "payment":
            # Bank / Cash accounts — for payment (CREDIT side of payment JE)
            payment_accounts = Account.objects.filter(
                is_active=True,
                is_deprecated=False,
            ).select_related("account_type").filter(
                # Bank/Cash: asset with bank_cash liquidity, or asset with code 10xx/11xx
                models.Q(
                    account_type__classification="asset",
                    account_type__liquidity_type="bank_cash",
                )
                | models.Q(
                    account_type__classification="asset",
                    code__startswith="10",
                )
                | models.Q(
                    account_type__classification="asset",
                    code__startswith="11",
                )
            ).order_by("code")
            data["payment"] = _serialize(payment_accounts, "payment")

        if not relatable_type or relatable_type == "payable":
            # Accounts Payable — liability with payable liquidity
            payable_accounts = Account.objects.filter(
                account_type__classification="liability",
                account_type__liquidity_type="payable",
                is_active=True,
            ).select_related("account_type").order_by("code")
            data["payable"] = _serialize(payable_accounts, "payable")

        if relatable_type:
            return Response(data.get(relatable_type, []))
        return Response(data)

    @action(detail=False, methods=["get"])
    def trial_balance(self, request):
        """Return trial balance data with Opening/Period/Closing Dr/Cr per account.

        Query params:
          date_from — period start (YYYY-MM-DD), default: 1st of current month
          date_to   — period end (YYYY-MM-DD), default: last day of current month
          ngo_project — optional ProjectManagementProject id filter
          as_of_date — legacy single-cutoff param (ignored when date_from/date_to are set)
        """
        from datetime import date
        from calendar import monthrange
        from django.db.models import Sum, Count
        from accounting.models import JournalItem, JournalEntry

        today = date.today()

        # Determine date range
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        ngo_project = request.query_params.get("ngo_project")

        if not date_from:
            date_from = f"{today.year}-{today.month:02d}-01"
        if not date_to:
            last_day = monthrange(today.year, today.month)[1]
            date_to = f"{today.year}-{today.month:02d}-{last_day:02d}"

        accounts = Account.objects.select_related("account_type", "parent").filter(
            is_active=True
        ).order_by("code")

        # Opening: all posted journal items BEFORE date_from, grouped by account
        pre_period_entries = JournalEntry.objects.filter(
            status="posted", date__lt=date_from
        )
        if ngo_project:
            pre_period_entries = pre_period_entries.filter(ngo_project_id=ngo_project)
        pre_period_totals = (
            JournalItem.objects.filter(journal_entry__in=pre_period_entries)
            .values("account")
            .annotate(
                pre_debit=Sum("debit"),
                pre_credit=Sum("credit"),
            )
        )
        pre_period_map = {
            item["account"]: {
                "pre_debit": float(item["pre_debit"] or 0),
                "pre_credit": float(item["pre_credit"] or 0),
            }
            for item in pre_period_totals
        }

        # Period: posted journal items between date_from and date_to
        period_entries = JournalEntry.objects.filter(
            status="posted", date__gte=date_from, date__lte=date_to
        )
        if ngo_project:
            period_entries = period_entries.filter(ngo_project_id=ngo_project)
        period_totals = (
            JournalItem.objects.filter(journal_entry__in=period_entries)
            .values("account")
            .annotate(
                period_debit=Sum("debit"),
                period_credit=Sum("credit"),
                line_count=Count("id"),
            )
        )
        period_map = {
            item["account"]: {
                "period_debit": float(item["period_debit"] or 0),
                "period_credit": float(item["period_credit"] or 0),
                "line_count": item["line_count"],
            }
            for item in period_totals
        }

        DEBIT_CLASSIFICATIONS = {"asset", "expense"}

        from accounting.services.account_hierarchy import (
            build_parent_and_children_maps,
            rollup_amount_map,
        )

        account_list = list(accounts)
        _, children_of = build_parent_and_children_maps(account_list)

        # Own (non-rolled) nets / period amounts
        own_opening_net = {}
        own_period_dr = {}
        own_period_cr = {}
        own_line_count = {}
        for acc in account_list:
            classification = acc.account_type.classification if acc.account_type else ""
            opening_bal = float(acc.opening_balance or 0)
            pre = pre_period_map.get(acc.id, {"pre_debit": 0, "pre_credit": 0})
            own_opening_net[acc.id] = opening_bal + pre["pre_debit"] - pre["pre_credit"]
            period = period_map.get(acc.id, {"period_debit": 0, "period_credit": 0, "line_count": 0})
            own_period_dr[acc.id] = period["period_debit"]
            own_period_cr[acc.id] = period["period_credit"]
            own_line_count[acc.id] = period["line_count"]

        ids = [a.id for a in account_list]
        rolled_opening = rollup_amount_map(own_opening_net, children_of, account_ids=ids)
        rolled_period_dr = rollup_amount_map(own_period_dr, children_of, account_ids=ids)
        rolled_period_cr = rollup_amount_map(own_period_cr, children_of, account_ids=ids)
        rolled_lines = rollup_amount_map(own_line_count, children_of, account_ids=ids)

        data = []
        for acc in account_list:
            classification = acc.account_type.classification if acc.account_type else ""
            net_opening_raw = float(rolled_opening.get(acc.id, 0))

            if classification in DEBIT_CLASSIFICATIONS:
                opening_dr = max(net_opening_raw, 0)
                opening_cr = abs(min(net_opening_raw, 0))
            else:
                opening_dr = abs(min(net_opening_raw, 0))
                opening_cr = max(net_opening_raw, 0)

            period_dr = float(rolled_period_dr.get(acc.id, 0))
            period_cr = float(rolled_period_cr.get(acc.id, 0))
            line_count = int(rolled_lines.get(acc.id, 0))

            net_opening = opening_dr - opening_cr
            net_period = period_dr - period_cr
            net_closing = net_opening + net_period

            if classification in DEBIT_CLASSIFICATIONS:
                closing_dr = max(net_closing, 0)
                closing_cr = abs(min(net_closing, 0))
            else:
                closing_dr = abs(min(net_closing, 0))
                closing_cr = max(net_closing, 0)

            data.append({
                "id": acc.id,
                "code": acc.code,
                "name": acc.name,
                "account_type": acc.account_type_id,
                "account_type_name": acc.account_type.name if acc.account_type else "",
                "classification": classification,
                "parent": acc.parent_id,
                "is_parent": bool(children_of.get(acc.id)),
                "is_contra": acc.is_contra,
                "opening_dr": round(opening_dr, 2),
                "opening_cr": round(opening_cr, 2),
                "period_dr": round(period_dr, 2),
                "period_cr": round(period_cr, 2),
                "closing_dr": round(closing_dr, 2),
                "closing_cr": round(closing_cr, 2),
                "line_count": line_count,
            })

        return Response({
            "date_from": date_from,
            "date_to": date_to,
            "accounts": data,
        })


class AccountTagViewSet(viewsets.ModelViewSet):
    queryset = AccountTag.objects.all()
    serializer_class = AccountTagSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name"]
