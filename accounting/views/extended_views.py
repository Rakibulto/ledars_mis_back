from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from accounting.models import (
    PaymentTerm,
    FiscalPosition,
    Incoterm,
    ReconciliationModel,
    BankStatement,
    BankStatementLine,
    Check,
    BankTransfer,
    DeferredRevenue,
    DeferredExpense,
)
from accounting.serializers.extended_serializers import (
    PaymentTermSerializer,
    FiscalPositionSerializer,
    IncotermSerializer,
    ReconciliationModelSerializer,
    BankStatementSerializer,
    BankStatementLineSerializer,
    CheckSerializer,
    BankTransferSerializer,
    DeferredRevenueSerializer,
    DeferredExpenseSerializer,
)
from accounting.views.status_transition_mixin import StatusTransitionMixin


class PaymentTermViewSet(viewsets.ModelViewSet):
    queryset = PaymentTerm.objects.all()
    serializer_class = PaymentTermSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]


class FiscalPositionViewSet(viewsets.ModelViewSet):
    queryset = FiscalPosition.objects.prefetch_related(
        "tax_mappings", "account_mappings"
    ).all()
    serializer_class = FiscalPositionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["is_active", "auto_apply"]
    search_fields = ["name", "country"]


class IncotermViewSet(viewsets.ModelViewSet):
    queryset = Incoterm.objects.all()
    serializer_class = IncotermSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["code", "name"]


class ReconciliationModelViewSet(viewsets.ModelViewSet):
    queryset = ReconciliationModel.objects.select_related(
        "match_journal", "account"
    ).all()
    serializer_class = ReconciliationModelSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["model_type", "is_active"]
    search_fields = ["name"]


class BankStatementViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = BankStatement.objects.select_related("bank_account").prefetch_related(
        "lines"
    ).all()
    serializer_class = BankStatementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["bank_account", "status"]
    ordering_fields = ["date"]

    @action(detail=True, methods=["post"], url_path="apply-line-action")
    def apply_line_action(self, request, pk=None):
        """Bulk-update statement line statuses: match, writeoff, or counterpart."""
        statement = self.get_object()
        line_ids = request.data.get("line_ids", [])
        act = request.data.get("action", "")
        model_id = request.data.get("model_id")
        counterpart_label = request.data.get("counterpart_label", "")
        note = request.data.get("note", "")

        lines = statement.lines.filter(id__in=line_ids)
        if act == "match":
            lines.update(line_status="matched", note=note or "Matched to book item")
        elif act == "writeoff":
            update_fields = {"line_status": "writeoff", "note": note or "Write-off applied"}
            if counterpart_label:
                update_fields["counterpart_label"] = counterpart_label
            if model_id:
                update_fields["rule_id"] = model_id
            lines.update(**update_fields)
        elif act == "counterpart":
            update_fields = {"line_status": "counterpart_created", "note": note or "Counterpart created"}
            if counterpart_label:
                update_fields["counterpart_label"] = counterpart_label
            lines.update(**update_fields)
        else:
            return Response({"detail": "Invalid action."}, status=400)

        # Recompute statement status
        resolved = {"matched", "writeoff", "counterpart_created"}
        total = statement.lines.count()
        unresolved = statement.lines.exclude(line_status__in=resolved).count()
        matched = statement.lines.filter(line_status="matched").count()
        if unresolved == 0:
            statement.status = "completed"
        elif matched > 0 or unresolved < total:
            statement.status = "in_progress"
        statement.save(update_fields=["status"])

        return Response(self.get_serializer(statement).data)

    @action(detail=True, methods=["post"], url_path="auto-match")
    def auto_match(self, request, pk=None):
        """Auto-apply high-confidence reconciliation models to suggested lines."""
        statement = self.get_object()
        updated = 0
        for line in statement.lines.filter(line_status="suggested"):
            if line.recommendation_type == "writeoff" and line.confidence >= 90:
                line.line_status = "writeoff"
                line.note = "Auto-applied bank charge model"
                line.save(update_fields=["line_status", "note"])
                updated += 1
            elif line.recommendation_type == "counterpart" and line.confidence >= 80:
                line.line_status = "counterpart_created"
                line.note = f"Auto-created {line.counterpart_label}"
                line.save(update_fields=["line_status", "note"])
                updated += 1

        resolved = {"matched", "writeoff", "counterpart_created"}
        unresolved = statement.lines.exclude(line_status__in=resolved).count()
        matched = statement.lines.filter(line_status="matched").count()
        if unresolved == 0:
            statement.status = "completed"
        elif matched > 0:
            statement.status = "in_progress"
        statement.save(update_fields=["status"])

        return Response({"updated": updated, **self.get_serializer(statement).data})

    @action(detail=True, methods=["post"], url_path="finalize")
    def finalize(self, request, pk=None):
        """Mark statement as completed if all lines are resolved."""
        statement = self.get_object()
        resolved = {"matched", "writeoff", "counterpart_created"}
        unresolved = statement.lines.exclude(line_status__in=resolved).count()
        if unresolved > 0:
            return Response({"completed": False, "detail": "Unresolved lines remain."}, status=400)
        statement.status = "completed"
        statement.save(update_fields=["status"])
        return Response({"completed": True, **self.get_serializer(statement).data})


class BankStatementLineViewSet(viewsets.ModelViewSet):
    queryset = BankStatementLine.objects.select_related("statement").all()
    serializer_class = BankStatementLineSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["statement", "line_status", "line_type"]
    ordering_fields = ["date"]


class CheckViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = Check.objects.select_related("bank_account").order_by("-created_at")
    serializer_class = CheckSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["bank_account", "status", "direction"]
    search_fields = ["check_number", "payee", "memo"]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-created_at"]

    @action(detail=True, methods=["post"], url_path="update-status")
    def update_status(self, request, pk=None):
        """Update check status and record timestamp."""
        check = self.get_object()
        new_status = request.data.get("status", "")
        valid = {s for s, _ in Check.STATUS_CHOICES}
        if new_status not in valid:
            return Response({"detail": "Invalid status."}, status=400)
        check.status = new_status
        check.last_action_at = timezone.now()
        check.save(update_fields=["status", "last_action_at"])
        return Response(self.get_serializer(check).data)

    @action(detail=True, methods=["post"], url_path="print")
    def print_check(self, request, pk=None):
        """Mark check as printed and increment print count."""
        check = self.get_object()
        check.print_status = "printed"
        check.print_count = (check.print_count or 0) + 1
        check.last_action_at = timezone.now()
        check.save(update_fields=["print_status", "print_count", "last_action_at"])
        return Response(self.get_serializer(check).data)


class BankTransferViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = BankTransfer.objects.select_related(
        "from_account", "to_account"
    ).all()
    serializer_class = BankTransferSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["status"]
    ordering_fields = ["date", "amount"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="advance-status")
    def advance_status(self, request, pk=None):
        """Advance transfer workflow status."""
        transfer = self.get_object()
        old_status = transfer.status
        new_status = request.data.get("status", "")
        valid = {s for s, _ in BankTransfer.STATUS_CHOICES}
        if new_status not in valid:
            return Response({"detail": "Invalid status."}, status=400)

        posted_date = request.data.get("posted_date")
        transfer.status = new_status
        if posted_date:
            transfer.posted_date = posted_date

        if new_status == "completed":
            with transaction.atomic():
                from accounting.models import Journal, JournalEntry, JournalItem
                from_account = transfer.from_account
                to_account = transfer.to_account
                if from_account.current_balance < transfer.amount:
                    return Response(
                        {"detail": "Insufficient funds on sender account."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                journal = Journal.objects.filter(journal_type="bank").first() or Journal.objects.filter(journal_type="general").first()
                if journal:
                    entry = JournalEntry.objects.create(
                        journal=journal,
                        date=transfer.date or timezone.now().date(),
                        reference=f"Transfer: {transfer.reference or transfer.id}",
                        status="posted",
                        total_debit=transfer.amount,
                        total_credit=transfer.amount,
                        posted_by=request.user,
                        posted_at=timezone.now(),
                    )
                    from_acc = getattr(from_account, 'account', None)
                    to_acc = getattr(to_account, 'account', None)
                    if from_acc:
                        JournalItem.objects.create(journal_entry=entry, account=from_acc, label=f"Transfer to {to_account.name if hasattr(to_account, 'name') else ''}", debit=0, credit=transfer.amount)
                    if to_acc:
                        JournalItem.objects.create(journal_entry=entry, account=to_acc, label=f"Transfer from {from_account.name if hasattr(from_account, 'name') else ''}", debit=transfer.amount, credit=0)

                from_account.current_balance -= transfer.amount
                to_account.current_balance += transfer.amount
                from_account.save(update_fields=["current_balance"])
                to_account.save(update_fields=["current_balance"])
                transfer.status = new_status
                if posted_date:
                    transfer.posted_date = posted_date
                transfer.save(update_fields=["status", "posted_date"])
        else:
            transfer.save(update_fields=["status", "posted_date"])

        return Response(self.get_serializer(transfer).data)


class DeferredRevenueViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = DeferredRevenue.objects.select_related("customer").all()
    serializer_class = DeferredRevenueSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["name", "reference"]
    ordering_fields = ["start_date", "total_amount", "created_at"]

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            remaining_amount=serializer.validated_data.get("total_amount", 0),
        )

    @action(detail=False, methods=["post"], url_path="create-draft")
    def create_draft(self, request):
        data = request.data.copy()
        total = Decimal(str(data.get("total_amount", 0)))
        instance = DeferredRevenue(
            reference=data.get("reference", ""),
            name=data.get("name", ""),
            total_amount=total,
            recognized_amount=Decimal("0"),
            remaining_amount=total,
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            periods=data.get("periods", 1),
            description=data.get("description", ""),
            status="running",
            created_by=request.user,
        )
        if data.get("customer"):
            instance.customer_id = data["customer"]
        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="recognize")
    def recognize(self, request, pk=None):
        obj = self.get_object()
        if obj.status == "fully_recognized":
            return Response(
                {"detail": "Already fully recognized."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            periods = int(obj.periods)
            monthly = obj.total_amount / Decimal(periods) if periods > 0 else obj.total_amount
        except (TypeError, ValueError, ZeroDivisionError):
            monthly = obj.remaining_amount

        new_recognized = min(obj.recognized_amount + monthly, obj.total_amount)
        obj.recognized_amount = new_recognized
        obj.remaining_amount = max(obj.total_amount - new_recognized, Decimal("0"))
        if obj.remaining_amount <= 0:
            obj.status = "fully_recognized"
        else:
            obj.status = "running"
        obj.save(update_fields=["recognized_amount", "remaining_amount", "status"])
        serializer = self.get_serializer(obj)
        return Response(serializer.data)


class DeferredExpenseViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = DeferredExpense.objects.select_related("vendor").all()
    serializer_class = DeferredExpenseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["name", "reference"]
    ordering_fields = ["start_date", "total_amount", "created_at"]

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            remaining_amount=serializer.validated_data.get("total_amount", 0),
        )

    @action(detail=False, methods=["post"], url_path="create-draft")
    def create_draft(self, request):
        data = request.data.copy()
        total = Decimal(str(data.get("total_amount", 0)))
        instance = DeferredExpense(
            reference=data.get("reference", ""),
            name=data.get("name", ""),
            total_amount=total,
            recognized_amount=Decimal("0"),
            remaining_amount=total,
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            periods=data.get("periods", 1),
            description=data.get("description", ""),
            status="running",
            created_by=request.user,
        )
        if data.get("vendor"):
            instance.vendor_id = data["vendor"]
        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="recognize")
    def recognize(self, request, pk=None):
        obj = self.get_object()
        if obj.status == "fully_recognized":
            return Response(
                {"detail": "Already fully recognized."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            periods = int(obj.periods)
            monthly = obj.total_amount / Decimal(periods) if periods > 0 else obj.total_amount
        except (TypeError, ValueError, ZeroDivisionError):
            monthly = obj.remaining_amount

        new_recognized = min(obj.recognized_amount + monthly, obj.total_amount)
        obj.recognized_amount = new_recognized
        obj.remaining_amount = max(obj.total_amount - new_recognized, Decimal("0"))
        if obj.remaining_amount <= 0:
            obj.status = "fully_recognized"
        else:
            obj.status = "running"
        obj.save(update_fields=["recognized_amount", "remaining_amount", "status"])
        serializer = self.get_serializer(obj)
        return Response(serializer.data)
