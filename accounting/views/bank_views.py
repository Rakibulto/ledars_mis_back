from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.utils import timezone

from accounting.models import (
    BankAccount,
    BankTransaction,
    BankReconciliation,
    BankReconciliationLine,
    CashRegister,
    CashTransaction,
)
from accounting.serializers.bank_serializers import (
    BankAccountSerializer,
    BankTransactionSerializer,
    BankReconciliationListSerializer,
    BankReconciliationDetailSerializer,
    CashRegisterSerializer,
    CashTransactionSerializer,
)
from accounting.views.status_transition_mixin import StatusTransitionMixin


class BankAccountViewSet(viewsets.ModelViewSet):
    queryset = BankAccount.objects.all()
    serializer_class = BankAccountSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["status", "account_type"]
    search_fields = ["name", "bank_name", "account_number"]

    @action(detail=True, methods=["post"], url_path="sync")
    def sync(self, request, pk=None):
        """Mark bank feed as synced."""
        account = self.get_object()
        account.feed_status = "healthy"
        account.last_sync_at = timezone.now()
        account.save(update_fields=["feed_status", "last_sync_at"])
        return Response(self.get_serializer(account).data)


class BankTransactionViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = BankTransaction.objects.select_related("bank_account").all()
    serializer_class = BankTransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "bank_account",
        "transaction_type",
        "status",
        "date",
        "ngo_project",
        "voucher",
        "is_system_generated",
    ]
    search_fields = ["description", "reference"]
    ordering_fields = ["date", "amount"]


class BankReconciliationViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = BankReconciliation.objects.select_related(
        "bank_account", "reconciled_by"
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["bank_account", "status"]
    ordering_fields = ["statement_date"]

    def get_serializer_class(self):
        if self.action == "list":
            return BankReconciliationListSerializer
        return BankReconciliationDetailSerializer

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Complete the reconciliation."""
        recon = self.get_object()
        if recon.status != "in_progress":
            return Response({"detail": "Not in progress."}, status=400)

        with transaction.atomic():
            recon.status = "completed"
            recon.reconciled_by = request.user
            recon.completed_at = timezone.now()
            recon.save(update_fields=["status", "reconciled_by", "completed_at"])

            recon.lines.filter(is_matched=True).select_related(
                "bank_transaction"
            ).update()
            BankTransaction.objects.filter(
                id__in=recon.lines.filter(is_matched=True).values_list(
                    "bank_transaction_id", flat=True
                )
            ).update(status="reconciled")

            bank = recon.bank_account
            bank.last_reconciled_date = recon.statement_date
            bank.last_reconciled_balance = recon.statement_balance
            bank.save(update_fields=["last_reconciled_date", "last_reconciled_balance"])

        return Response({"detail": "Reconciliation completed."})


class CashRegisterViewSet(viewsets.ModelViewSet):
    queryset = CashRegister.objects.select_related("custodian").all()
    serializer_class = CashRegisterSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_active"]


class CashTransactionViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = CashTransaction.objects.select_related(
        "cash_register", "created_by"
    ).all()
    serializer_class = CashTransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["cash_register", "transaction_type", "date"]
    search_fields = ["description"]
    ordering_fields = ["date", "amount"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
