"""Gateway display books and essential financial reports (live data)."""

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounting.models import (
    Account,
    BankAccount,
    BankTransaction,
    JournalEntry,
    JournalItem,
)


def _parse_dates(request):
    today = date.today()
    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")
    if not date_from:
        date_from = f"{today.year}-{today.month:02d}-01"
    if not date_to:
        last_day = monthrange(today.year, today.month)[1]
        date_to = f"{today.year}-{today.month:02d}-{last_day:02d}"
    ngo_project = request.query_params.get("ngo_project")
    return date_from, date_to, ngo_project


class DayBookView(APIView):
    """Posted journal entries for a date range (optional NGO project)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_from, date_to, ngo_project = _parse_dates(request)
        qs = (
            JournalEntry.objects.filter(
                status="posted", date__gte=date_from, date__lte=date_to
            )
            .select_related("journal", "ngo_project")
            .prefetch_related("items__account")
            .order_by("date", "id")
        )
        if ngo_project:
            qs = qs.filter(ngo_project_id=ngo_project)

        rows = []
        for entry in qs:
            rows.append(
                {
                    "id": entry.id,
                    "date": entry.date,
                    "reference": entry.reference,
                    "journal": entry.journal.name if entry.journal else "",
                    "narration": entry.narration,
                    "total_debit": float(entry.total_debit),
                    "total_credit": float(entry.total_credit),
                    "ngo_project": entry.ngo_project_id,
                    "ngo_project_title": getattr(entry.ngo_project, "title", "") or "",
                    "lines": [
                        {
                            "account_code": item.account.code if item.account else "",
                            "account_name": item.account.name if item.account else "",
                            "label": item.label,
                            "debit": float(item.debit),
                            "credit": float(item.credit),
                        }
                        for item in entry.items.all()
                    ],
                }
            )
        return Response(
            {
                "date_from": date_from,
                "date_to": date_to,
                "ngo_project": ngo_project,
                "count": len(rows),
                "results": rows,
            }
        )


class CashBankBookView(APIView):
    """Bank/cash book from BankTransaction (optional bank_account + project)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_from, date_to, ngo_project = _parse_dates(request)
        bank_account_id = request.query_params.get("bank_account")
        qs = (
            BankTransaction.objects.filter(date__gte=date_from, date__lte=date_to)
            .select_related("bank_account", "ngo_project", "voucher")
            .order_by("date", "id")
        )
        if bank_account_id:
            qs = qs.filter(bank_account_id=bank_account_id)
        if ngo_project:
            qs = qs.filter(ngo_project_id=ngo_project)

        bank_info = None
        if bank_account_id:
            bank = BankAccount.objects.filter(pk=bank_account_id).first()
            if bank:
                bank_info = {
                    "id": bank.id,
                    "name": bank.name,
                    "bank_name": bank.bank_name,
                    "account_number": bank.account_number,
                    "current_balance": float(bank.current_balance),
                    "account_type": bank.account_type,
                }

        results = [
            {
                "id": t.id,
                "date": t.date,
                "description": t.description,
                "reference": t.reference,
                "transaction_type": t.transaction_type,
                "amount": float(t.amount),
                "running_balance": float(t.running_balance),
                "bank_account": t.bank_account_id,
                "bank_account_name": t.bank_account.name if t.bank_account else "",
                "voucher": t.voucher_id,
                "voucher_number": t.voucher.voucher_number if t.voucher_id else "",
                "ngo_project": t.ngo_project_id,
                "is_system_generated": t.is_system_generated,
            }
            for t in qs
        ]
        return Response(
            {
                "date_from": date_from,
                "date_to": date_to,
                "ngo_project": ngo_project,
                "bank_account": bank_info,
                "count": len(results),
                "results": results,
            }
        )


class AccountLedgerView(APIView):
    """Ledger for one CoA account (includes descendant accounts when a parent is selected)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from accounting.services.account_hierarchy import (
            build_parent_and_children_maps,
            get_descendant_ids,
        )

        date_from, date_to, ngo_project = _parse_dates(request)
        account_id = request.query_params.get("account")
        if not account_id:
            return Response({"detail": "account query param is required."}, status=400)

        account = Account.objects.filter(pk=account_id).select_related("account_type").first()
        if not account:
            return Response({"detail": "Account not found."}, status=404)

        all_accounts = list(Account.objects.only("id", "parent_id"))
        _, children_of = build_parent_and_children_maps(all_accounts)
        account_ids = get_descendant_ids(
            account.id, children_of=children_of, include_self=True
        )

        descendants = {
            a.id: a
            for a in Account.objects.filter(id__in=account_ids).only(
                "id", "code", "name", "opening_balance"
            )
        }

        opening_qs = JournalItem.objects.filter(
            journal_entry__status="posted",
            journal_entry__date__lt=date_from,
            account_id__in=account_ids,
        )
        if ngo_project:
            opening_qs = opening_qs.filter(journal_entry__ngo_project_id=ngo_project)
        opening_agg = opening_qs.aggregate(d=Sum("debit"), c=Sum("credit"))
        opening_from_books = sum(
            (Decimal(str(descendants[i].opening_balance or 0)) for i in account_ids),
            Decimal("0"),
        )
        opening_balance = (
            opening_from_books
            + Decimal(str(opening_agg["d"] or 0))
            - Decimal(str(opening_agg["c"] or 0))
        )

        period_qs = (
            JournalItem.objects.filter(
                journal_entry__status="posted",
                journal_entry__date__gte=date_from,
                journal_entry__date__lte=date_to,
                account_id__in=account_ids,
            )
            .select_related("journal_entry", "account")
            .order_by("journal_entry__date", "id")
        )
        if ngo_project:
            period_qs = period_qs.filter(journal_entry__ngo_project_id=ngo_project)

        running = opening_balance
        rows = []
        for item in period_qs:
            running = running + item.debit - item.credit
            rows.append(
                {
                    "id": item.id,
                    "date": item.journal_entry.date,
                    "reference": item.journal_entry.reference,
                    "label": item.label,
                    "account_id": item.account_id,
                    "account_code": item.account.code if item.account else "",
                    "account_name": item.account.name if item.account else "",
                    "debit": float(item.debit),
                    "credit": float(item.credit),
                    "balance": float(running),
                }
            )

        return Response(
            {
                "date_from": date_from,
                "date_to": date_to,
                "ngo_project": ngo_project,
                "account": {
                    "id": account.id,
                    "code": account.code,
                    "name": account.name,
                    "classification": (
                        account.account_type.classification if account.account_type else ""
                    ),
                },
                "includes_descendants": len(account_ids) > 1,
                "descendant_account_ids": account_ids,
                "opening_balance": float(opening_balance),
                "closing_balance": float(running),
                "count": len(rows),
                "results": rows,
            }
        )


class ProfitAndLossView(APIView):
    """Income / expense P&L from posted journal items (parents include child totals)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from accounting.services.account_hierarchy import (
            build_parent_and_children_maps,
            get_leaf_ids,
            rollup_amount_map,
        )

        date_from, date_to, ngo_project = _parse_dates(request)
        items = JournalItem.objects.filter(
            journal_entry__status="posted",
            journal_entry__date__gte=date_from,
            journal_entry__date__lte=date_to,
            account__account_type__classification__in=["income", "expense"],
        ).select_related("account", "account__account_type")
        if ngo_project:
            items = items.filter(journal_entry__ngo_project_id=ngo_project)

        # Own activity per account
        own_amount = {}  # signed amount: income Cr-Dr, expense Dr-Cr
        meta = {}
        for item in items:
            key = item.account_id
            if key not in meta:
                classification = item.account.account_type.classification
                meta[key] = {
                    "account_id": item.account_id,
                    "code": item.account.code if item.account else "",
                    "name": item.account.name if item.account else "",
                    "classification": classification,
                    "parent": item.account.parent_id,
                }
                own_amount[key] = Decimal("0")
            if meta[key]["classification"] == "income":
                own_amount[key] += item.credit - item.debit
            else:
                own_amount[key] += item.debit - item.credit

        # Include inactive-parent chain for income/expense accounts so rollup works
        pl_accounts = list(
            Account.objects.filter(
                is_active=True,
                account_type__classification__in=["income", "expense"],
            ).only("id", "parent_id", "code", "name", "account_type_id")
            .select_related("account_type")
        )
        _, children_of = build_parent_and_children_maps(pl_accounts)
        for acc in pl_accounts:
            if acc.id not in meta:
                meta[acc.id] = {
                    "account_id": acc.id,
                    "code": acc.code,
                    "name": acc.name,
                    "classification": acc.account_type.classification if acc.account_type else "",
                    "parent": acc.parent_id,
                }
            own_amount.setdefault(acc.id, Decimal("0"))

        rolled = rollup_amount_map(own_amount, children_of, account_ids=list(meta.keys()))

        income = []
        expense = []
        for aid, amount in rolled.items():
            info = meta.get(aid)
            if not info or not info.get("classification"):
                continue
            if amount == 0 and aid not in own_amount:
                continue
            # Skip zero rows that have no own activity and no rolled children
            if amount == 0:
                continue
            row = {
                **info,
                "amount": float(amount),
                "is_parent": bool(children_of.get(aid)),
            }
            if info["classification"] == "income":
                income.append(row)
            elif info["classification"] == "expense":
                expense.append(row)

        income.sort(key=lambda r: r["code"])
        expense.sort(key=lambda r: r["code"])

        # Totals from leaves only to avoid double-counting parents
        leaf_ids = set(get_leaf_ids(list(meta.keys()), children_of))
        total_income = sum(
            (rolled[aid] for aid in leaf_ids if meta.get(aid, {}).get("classification") == "income"),
            Decimal("0"),
        )
        total_expense = sum(
            (rolled[aid] for aid in leaf_ids if meta.get(aid, {}).get("classification") == "expense"),
            Decimal("0"),
        )

        return Response(
            {
                "date_from": date_from,
                "date_to": date_to,
                "ngo_project": ngo_project,
                "income": income,
                "expense": expense,
                "total_income": float(total_income),
                "total_expense": float(total_expense),
                "net_profit": float(total_income - total_expense),
            }
        )


class BalanceSheetView(APIView):
    """Assets / liabilities / equity as-of date_to (parents include child totals)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from accounting.services.account_hierarchy import (
            build_parent_and_children_maps,
            get_leaf_ids,
            rollup_amount_map,
        )

        _, date_to, ngo_project = _parse_dates(request)
        accounts = list(
            Account.objects.filter(
                is_active=True,
                account_type__classification__in=["asset", "liability", "equity"],
            ).select_related("account_type")
        )
        _, children_of = build_parent_and_children_maps(accounts)

        items = JournalItem.objects.filter(
            journal_entry__status="posted",
            journal_entry__date__lte=date_to,
            account_id__in=[a.id for a in accounts],
        )
        if ngo_project:
            items = items.filter(journal_entry__ngo_project_id=ngo_project)

        totals = items.values("account").annotate(d=Sum("debit"), c=Sum("credit"))
        tot_map = {
            t["account"]: Decimal(str(t["d"] or 0)) - Decimal(str(t["c"] or 0))
            for t in totals
        }

        # Own signed balance (asset-natural: debit positive)
        own_net = {}
        for acc in accounts:
            own_net[acc.id] = Decimal(str(acc.opening_balance or 0)) + tot_map.get(
                acc.id, Decimal("0")
            )

        rolled_net = rollup_amount_map(own_net, children_of, account_ids=[a.id for a in accounts])

        sections = {"asset": [], "liability": [], "equity": []}
        for acc in accounts:
            classification = acc.account_type.classification
            net = rolled_net.get(acc.id, Decimal("0"))
            if classification in ("liability", "equity"):
                display = -net
            else:
                display = net
            if display == 0 and own_net.get(acc.id, 0) == 0 and not children_of.get(acc.id):
                continue
            if display == 0 and not children_of.get(acc.id) and tot_map.get(acc.id) is None and not acc.opening_balance:
                continue
            sections[classification].append(
                {
                    "account_id": acc.id,
                    "code": acc.code,
                    "name": acc.name,
                    "parent": acc.parent_id,
                    "is_parent": bool(children_of.get(acc.id)),
                    "balance": float(display),
                }
            )

        leaf_ids = set(get_leaf_ids([a.id for a in accounts], children_of))
        section_totals = {"asset": Decimal("0"), "liability": Decimal("0"), "equity": Decimal("0")}
        for acc in accounts:
            if acc.id not in leaf_ids:
                continue
            classification = acc.account_type.classification
            net = rolled_net.get(acc.id, Decimal("0"))
            display = -net if classification in ("liability", "equity") else net
            section_totals[classification] += display

        return Response(
            {
                "as_of": date_to,
                "ngo_project": ngo_project,
                "assets": sections["asset"],
                "liabilities": sections["liability"],
                "equity": sections["equity"],
                "total_assets": float(section_totals["asset"]),
                "total_liabilities": float(section_totals["liability"]),
                "total_equity": float(section_totals["equity"]),
            }
        )


class ProjectStatementView(APIView):
    """Combined project-wise summary: TB-style totals + P&L net for one project."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_from, date_to, ngo_project = _parse_dates(request)
        if not ngo_project:
            return Response(
                {"detail": "ngo_project query param is required."}, status=400
            )

        pl = ProfitAndLossView()
        pl_request = request
        pl_data = pl.get(pl_request).data

        day = DayBookView()
        day_data = day.get(request).data

        return Response(
            {
                "date_from": date_from,
                "date_to": date_to,
                "ngo_project": ngo_project,
                "profit_and_loss": {
                    "total_income": pl_data.get("total_income"),
                    "total_expense": pl_data.get("total_expense"),
                    "net_profit": pl_data.get("net_profit"),
                },
                "voucher_entry_count": day_data.get("count"),
                "income_lines": pl_data.get("income"),
                "expense_lines": pl_data.get("expense"),
            }
        )
