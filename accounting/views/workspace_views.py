"""
ViewSets for workspace transaction pages:
CustomerReceiptViewSet, BankDepositViewSet, SupplierPaymentViewSet
"""
from datetime import date as date_cls
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from accounting.models import (
    CustomerReceipt,
    CustomerReceiptAllocation,
    BankDeposit,
    SupplierPayment,
    Vendor,
    Bill,
    CashWorkspaceTransaction,
    ContraEntry,
    ExpenseEntry,
    PayrollEntry,
    InventoryEntry,
)
from accounting.serializers.workspace_serializers import (
    CustomerReceiptListSerializer,
    CustomerReceiptDetailSerializer,
    CustomerReceiptWriteSerializer,
    CustomerReceiptAllocationSerializer,
    BankDepositListSerializer,
    BankDepositWriteSerializer,
    SupplierPaymentListSerializer,
    SupplierPaymentWriteSerializer,
    SupplierPaymentVendorSerializer,
    CashWorkspaceTransactionSerializer,
    CashWorkspaceTransactionWriteSerializer,
    ContraEntrySerializer,
    ContraEntryWriteSerializer,
    ExpenseEntrySerializer,
    ExpenseEntryWriteSerializer,
    PayrollEntrySerializer,
    PayrollEntryWriteSerializer,
    InventoryEntrySerializer,
    InventoryEntryWriteSerializer,
)
from accounting.serializers.payable_serializers import VendorListSerializer
from accounting.views.status_transition_mixin import StatusTransitionMixin


class CustomerReceiptViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = CustomerReceipt.objects.select_related("customer", "donor").prefetch_related(
        "allocations"
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["customer", "status", "allocation_status"]
    search_fields = ["receipt_number", "reference", "customer__name"]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerReceiptListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return CustomerReceiptWriteSerializer
        return CustomerReceiptDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"])
    def customers(self, request):
        """Return active customers for dropdown."""
        from accounting.models import Customer
        from accounting.serializers.receivable_serializers import CustomerListSerializer

        customers = Customer.objects.filter(status="active").order_by("name")
        serializer = CustomerListSerializer(customers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def allocate(self, request, pk=None):
        """Allocate a portion of receipt to an invoice — creates JE: DR Bank, CR Receivable."""
        receipt = self.get_object()
        invoice_number = request.data.get("invoice_number", "")
        amount = Decimal(str(request.data.get("amount") or receipt.unapplied_amount))

        if receipt.unapplied_amount <= 0:
            return Response({"detail": "No unapplied amount."}, status=400)

        allocatable = min(amount, receipt.unapplied_amount)
        if allocatable <= 0:
            return Response({"detail": "Amount must be positive."}, status=400)

        with transaction.atomic():
            from accounting.models import Journal, JournalEntry, JournalItem

            journal = Journal.objects.filter(journal_type="bank").first() or Journal.objects.filter(journal_type="cash").first() or Journal.objects.first()
            if journal:
                entry = JournalEntry.objects.create(
                    journal=journal,
                    date=timezone.now().date(),
                    reference=f"Receipt: {receipt.receipt_number}",
                    status="posted",
                    total_debit=allocatable,
                    total_credit=allocatable,
                    posted_by=request.user,
                    posted_at=timezone.now(),
                )
                # DEBIT: Bank/Cash — use FK if set, otherwise fuzzy fallback
                bank_account = receipt.bank_account
                if not bank_account:
                    from accounting.models import Account
                    bank_account = Account.objects.filter(name__icontains="bank").first() or Account.objects.filter(code__startswith="102").first() or Account.objects.filter(name__icontains="cash").first()
                if bank_account:
                    JournalItem.objects.create(
                        journal_entry=entry,
                        account=bank_account,
                        label=f"Receipt from {receipt.customer_name or receipt.counterparty}",
                        debit=allocatable,
                        credit=0,
                    )
                    bank_account.current_balance += allocatable
                    bank_account.save(update_fields=["current_balance"])
                # CREDIT: Customer Receivable or Unapplied Revenue
                receivable_account = Account.objects.filter(account_type__classification="receivable").first() or Account.objects.filter(code__startswith="110").first()
                if receivable_account:
                    JournalItem.objects.create(
                        journal_entry=entry,
                        account=receivable_account,
                        label=f"Receipt allocation: {invoice_number or receipt.receipt_number}",
                        debit=0,
                        credit=allocatable,
                    )
                    receivable_account.current_balance -= allocatable
                    receivable_account.save(update_fields=["current_balance"])

            CustomerReceiptAllocation.objects.create(
                receipt=receipt,
                invoice_number=invoice_number,
                amount=allocatable,
            )
            receipt.unapplied_amount = max(receipt.unapplied_amount - allocatable, Decimal("0"))
            receipt.status = "posted"
            receipt.allocation_status = (
                "fully_allocated" if receipt.unapplied_amount == 0 else "partially_allocated"
            )
            receipt.save(update_fields=["unapplied_amount", "status", "allocation_status"])

        serializer = CustomerReceiptDetailSerializer(receipt)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="auto-allocate")
    def auto_allocate(self, request, pk=None):
        """Auto-allocate full unapplied amount — creates JE: DR Bank, CR Receivable."""
        receipt = self.get_object()
        if receipt.unapplied_amount <= 0:
            return Response({"detail": "No unapplied amount."}, status=400)

        with transaction.atomic():
            from accounting.models import Journal, JournalEntry, JournalItem

            allocatable = receipt.unapplied_amount
            journal = Journal.objects.filter(journal_type="bank").first() or Journal.objects.filter(journal_type="cash").first() or Journal.objects.first()
            if journal:
                entry = JournalEntry.objects.create(
                    journal=journal,
                    date=timezone.now().date(),
                    reference=f"Receipt: {receipt.receipt_number}",
                    status="posted",
                    total_debit=allocatable,
                    total_credit=allocatable,
                    posted_by=request.user,
                    posted_at=timezone.now(),
                )
                # Use FK if set, otherwise fuzzy fallback
                bank_account = receipt.bank_account
                if not bank_account:
                    from accounting.models import Account
                    bank_account = Account.objects.filter(name__icontains="bank").first() or Account.objects.filter(code__startswith="102").first() or Account.objects.filter(name__icontains="cash").first()
                if bank_account:
                    JournalItem.objects.create(
                        journal_entry=entry,
                        account=bank_account,
                        label=f"Receipt from {receipt.customer_name or receipt.counterparty}",
                        debit=allocatable,
                        credit=0,
                    )
                    bank_account.current_balance += allocatable
                    bank_account.save(update_fields=["current_balance"])
                receivable_account = Account.objects.filter(account_type__classification="receivable").first() or Account.objects.filter(code__startswith="110").first()
                if receivable_account:
                    JournalItem.objects.create(
                        journal_entry=entry,
                        account=receivable_account,
                        label=f"Receipt allocation: {receipt.receipt_number}",
                        debit=0,
                        credit=allocatable,
                    )
                    receivable_account.current_balance -= allocatable
                    receivable_account.save(update_fields=["current_balance"])

            CustomerReceiptAllocation.objects.create(
                receipt=receipt,
                invoice_number=request.data.get("invoice_number", "auto"),
                amount=allocatable,
            )
            receipt.status = "posted"
            receipt.allocation_status = "fully_allocated"
            receipt.unapplied_amount = Decimal("0")
            receipt.save(update_fields=["unapplied_amount", "status", "allocation_status"])

        serializer = CustomerReceiptDetailSerializer(receipt)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="hold-as-advance")
    def hold_as_advance(self, request, pk=None):
        """Mark unapplied balance as customer advance."""
        receipt = self.get_object()
        receipt.status = "posted"
        receipt.notes = (
            f"Residual held as customer advance pending future invoice matching. {receipt.notes}"
        )
        receipt.save(update_fields=["status", "notes"])
        serializer = CustomerReceiptDetailSerializer(receipt)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="write-off-residual")
    def write_off_residual(self, request, pk=None):
        """Write off residual unapplied amount."""
        receipt = self.get_object()
        write_off_amount = Decimal(
            str(request.data.get("amount") or receipt.unapplied_amount)
        )
        applied = min(write_off_amount, receipt.unapplied_amount)
        if applied <= 0:
            return Response({"detail": "Nothing to write off."}, status=400)

        reason = request.data.get("reason", "Write-off")
        receipt.unapplied_amount = max(receipt.unapplied_amount - applied, Decimal("0"))
        receipt.status = "posted"
        receipt.allocation_status = (
            "fully_allocated" if receipt.unapplied_amount == 0 else "partially_allocated"
        )
        receipt.notes = f"Wrote off {applied} as {reason}. {receipt.notes}"
        receipt.save(
            update_fields=["unapplied_amount", "status", "allocation_status", "notes"]
        )
        serializer = CustomerReceiptDetailSerializer(receipt)
        return Response(serializer.data)


class BankDepositViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = BankDeposit.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "reconciliation_status"]
    search_fields = ["deposit_number", "description", "source", "prepared_by"]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return BankDepositWriteSerializer
        return BankDepositListSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def reconcile(self, request, pk=None):
        """Mark deposit as reconciled."""
        deposit = self.get_object()

        with transaction.atomic():
            from accounting.models import Journal, JournalEntry, JournalItem, Account
            journal = Journal.objects.filter(journal_type="bank").first() or Journal.objects.filter(journal_type="general").first()
            if journal:
                entry = JournalEntry.objects.create(
                    journal=journal,
                    date=deposit.date,
                    reference=f"Deposit: {deposit.deposit_number}",
                    status="posted",
                    total_debit=deposit.amount,
                    total_credit=deposit.amount,
                    posted_by=request.user,
                    posted_at=timezone.now(),
                )
                # Use FK if set, otherwise fuzzy fallback
                bank_account = deposit.bank_account
                if not bank_account:
                    bank_account = Account.objects.filter(name__icontains=deposit.bank_account_name).first() or Account.objects.filter(code__startswith="103").first()
                if bank_account:
                    JournalItem.objects.create(journal_entry=entry, account=bank_account, label=deposit.description or f"Deposit {deposit.deposit_number}", debit=deposit.amount, credit=0)
                    bank_account.current_balance += deposit.amount
                    bank_account.save(update_fields=["current_balance"])
                source_account = Account.objects.filter(name__icontains=deposit.source).first() or Account.objects.filter(account_type__classification="income").first()
                if source_account:
                    JournalItem.objects.create(journal_entry=entry, account=source_account, label=deposit.description or f"Deposit {deposit.deposit_number}", debit=0, credit=deposit.amount)
                    source_account.current_balance -= deposit.amount
                    source_account.save(update_fields=["current_balance"])

            deposit.status = "posted"
            deposit.reconciliation_status = "reconciled"
            deposit.save(update_fields=["status", "reconciliation_status"])
        serializer = BankDepositListSerializer(deposit)
        return Response(serializer.data)


class SupplierPaymentViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = SupplierPayment.objects.select_related("vendor").all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["vendor", "status", "release_status"]
    search_fields = ["payment_number", "payment_run", "vendor__name"]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SupplierPaymentWriteSerializer
        return SupplierPaymentListSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"])
    def vendors(self, request):
        """Return active vendors for the supplier dropdown."""
        vendors = Vendor.objects.filter(status="active").order_by("name")
        serializer = VendorListSerializer(vendors, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="payable-bills")
    def payable_bills(self, request):
        """Return unpaid bills with release readiness for payment run staging."""
        bills = Bill.objects.filter(
            status__in=["draft", "approved", "partial", "overdue"]
        ).select_related("vendor").order_by("due_date")

        today = date_cls.today()
        data = []
        for bill in bills:
            is_overdue = bill.due_date < today if bill.due_date else False
            if bill.dispute_flag or bill.match_status != "3-way matched":
                release_readiness = "blocked"
            elif bill.amount_due > 0:
                release_readiness = "ready"
            else:
                release_readiness = "covered"

            data.append(
                {
                    "id": bill.id,
                    "number": bill.bill_number,
                    "bill_number": bill.bill_number,
                    "supplier_id": bill.vendor.id,
                    "vendor_name": bill.vendor.name,
                    "due_date": bill.due_date,
                    "balance_due": float(bill.amount_due),
                    "total": float(bill.total_amount),
                    "dispute_flag": bill.dispute_flag,
                    "match_status": bill.match_status,
                    "payment_proposal": bill.payment_proposal,
                    "approval_route": bill.approval_route,
                    "release_readiness": release_readiness,
                    "is_overdue": is_overdue,
                    "status": bill.status,
                }
            )

        return Response(data)

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        """Release a queued supplier payment — creates JE: DR Payable, CR Bank."""
        payment = self.get_object()
        if payment.release_status == "blocked":
            return Response({"detail": "Payment is blocked and cannot be released."}, status=400)

        with transaction.atomic():
            from accounting.models import Journal, JournalEntry, JournalItem, Account

            journal = Journal.objects.filter(journal_type="bank").first() or Journal.objects.filter(journal_type="purchase").first() or Journal.objects.first()
            if journal:
                entry = JournalEntry.objects.create(
                    journal=journal,
                    date=timezone.now().date(),
                    reference=f"Supplier Payment: {payment.payment_number}",
                    status="posted",
                    total_debit=payment.amount,
                    total_credit=payment.amount,
                    posted_by=request.user,
                    posted_at=timezone.now(),
                )
                # DEBIT: Vendor Payable (reducing what you owe)
                payable_account = None
                if payment.vendor and payment.vendor.payable_account:
                    payable_account = payment.vendor.payable_account
                if not payable_account:
                    payable_account = Account.objects.filter(account_type__classification="liability", account_type__liquidity_type="payable").first() or Account.objects.filter(code__startswith="210").first()
                if payable_account:
                    JournalItem.objects.create(
                        journal_entry=entry,
                        account=payable_account,
                        label=f"Payment to {payment.vendor.name if payment.vendor else ''}",
                        debit=payment.amount,
                        credit=0,
                    )
                    payable_account.current_balance += payment.amount
                    payable_account.save(update_fields=["current_balance"])
                # CREDIT: Bank/Cash — use FK if set, otherwise fuzzy fallback
                bank_account = payment.bank_account
                if not bank_account:
                    bank_account = Account.objects.filter(name__icontains="bank").first() or Account.objects.filter(code__startswith="102").first() or Account.objects.filter(name__icontains="cash").first()
                if bank_account:
                    JournalItem.objects.create(
                        journal_entry=entry,
                        account=bank_account,
                        label=f"Payment: {payment.payment_number}",
                        debit=0,
                        credit=payment.amount,
                    )
                    bank_account.current_balance -= payment.amount
                    bank_account.save(update_fields=["current_balance"])

            payment.status = "posted"
            payment.release_status = "released"
            payment.save(update_fields=["status", "release_status"])

        serializer = SupplierPaymentListSerializer(payment)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        """Unblock a blocked supplier payment."""
        payment = self.get_object()
        payment.release_status = "queued"
        payment.notes = f"Block cleared. {payment.notes}"
        payment.save(update_fields=["release_status", "notes"])
        serializer = SupplierPaymentListSerializer(payment)
        return Response(serializer.data)


# ──────────────────────────────────────────────────────────────────────────────
# Cash Workspace Transactions
# ──────────────────────────────────────────────────────────────────────────────

class CashWorkspaceTransactionViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = CashWorkspaceTransaction.objects.select_related("created_by", "account").all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "direction"]
    search_fields = ["transaction_number", "counterparty", "reference", "description"]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        if self.request.method in ("POST", "PUT", "PATCH"):
            return CashWorkspaceTransactionWriteSerializer
        return CashWorkspaceTransactionSerializer

    @action(detail=False, methods=["post"], url_path="create")
    def create_entry(self, request):
        serializer = CashWorkspaceTransactionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(created_by=request.user, status="draft")
        return Response(
            CashWorkspaceTransactionSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_entry(self, request, pk=None):
        instance = self.get_object()
        if instance.status == "posted":
            return Response({"detail": "Already posted."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            from accounting.models import Journal, JournalEntry, JournalItem
            journal = Journal.objects.filter(journal_type="cash").first() or Journal.objects.filter(journal_type="general").first()
            if journal:
                entry = JournalEntry.objects.create(
                    journal=journal,
                    date=instance.date,
                    reference=f"Cash: {instance.transaction_number}",
                    status="posted",
                    total_debit=instance.amount,
                    total_credit=instance.amount,
                    posted_by=request.user,
                    posted_at=timezone.now(),
                )
                # Use the FK account directly — no fuzzy matching needed
                cash_account = instance.account
                expense_account = cash_account  # fallback if no account set
                if not cash_account:
                    from accounting.models import Account
                    cash_account = Account.objects.filter(name__icontains="cash").first() or Account.objects.filter(code__startswith="101").first()
                    expense_account = Account.objects.filter(account_type__classification="expense").first()

                if instance.direction == "outflow":
                    if expense_account:
                        JournalItem.objects.create(journal_entry=entry, account=expense_account, label=instance.description[:200], debit=instance.amount, credit=0)
                        expense_account.current_balance += instance.amount
                        expense_account.save(update_fields=["current_balance"])
                    if cash_account and cash_account != expense_account:
                        JournalItem.objects.create(journal_entry=entry, account=cash_account, label=instance.description[:200], debit=0, credit=instance.amount)
                        cash_account.current_balance -= instance.amount
                        cash_account.save(update_fields=["current_balance"])
                else:
                    if cash_account:
                        JournalItem.objects.create(journal_entry=entry, account=cash_account, label=instance.description[:200], debit=instance.amount, credit=0)
                        cash_account.current_balance += instance.amount
                        cash_account.save(update_fields=["current_balance"])
                    if expense_account and expense_account != cash_account:
                        JournalItem.objects.create(journal_entry=entry, account=expense_account, label=instance.description[:200], debit=0, credit=instance.amount)
                        expense_account.current_balance -= instance.amount
                        expense_account.save(update_fields=["current_balance"])

            instance.status = "posted"
            instance.save(update_fields=["status"])
        return Response(CashWorkspaceTransactionSerializer(instance).data)


# ──────────────────────────────────────────────────────────────────────────────
# Contra Entries
# ──────────────────────────────────────────────────────────────────────────────

class ContraEntryViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = ContraEntry.objects.select_related("created_by", "from_account", "to_account").all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["entry_number", "reference"]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        if self.request.method in ("POST", "PUT", "PATCH"):
            return ContraEntryWriteSerializer
        return ContraEntrySerializer

    @action(detail=False, methods=["post"], url_path="create")
    def create_entry(self, request):
        serializer = ContraEntryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(created_by=request.user, status="draft")
        return Response(
            ContraEntrySerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_entry(self, request, pk=None):
        instance = self.get_object()
        if instance.status == "posted":
            return Response({"detail": "Already posted."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            from accounting.models import Journal, JournalEntry, JournalItem
            journal = Journal.objects.filter(journal_type="bank").first() or Journal.objects.filter(journal_type="cash").first() or Journal.objects.filter(journal_type="general").first()
            if journal:
                entry = JournalEntry.objects.create(
                    journal=journal,
                    date=instance.date,
                    reference=f"Contra: {instance.entry_number}",
                    status="posted",
                    total_debit=instance.amount,
                    total_credit=instance.amount,
                    posted_by=request.user,
                    posted_at=timezone.now(),
                )
                # Use FK accounts directly
                from_acc = instance.from_account
                to_acc = instance.to_account
                if from_acc:
                    JournalItem.objects.create(journal_entry=entry, account=from_acc, label=instance.description[:200] or "Contra transfer", debit=0, credit=instance.amount)
                    from_acc.current_balance -= instance.amount
                    from_acc.save(update_fields=["current_balance"])
                if to_acc:
                    JournalItem.objects.create(journal_entry=entry, account=to_acc, label=instance.description[:200] or "Contra transfer", debit=instance.amount, credit=0)
                    to_acc.current_balance += instance.amount
                    to_acc.save(update_fields=["current_balance"])

            instance.status = "posted"
            instance.save(update_fields=["status"])
        return Response(ContraEntrySerializer(instance).data)


# ──────────────────────────────────────────────────────────────────────────────
# Expense Entries
# ──────────────────────────────────────────────────────────────────────────────

class ExpenseEntryViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = ExpenseEntry.objects.select_related("created_by", "category").all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["entry_number", "employee", "reference"]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        if self.request.method in ("POST", "PUT", "PATCH"):
            return ExpenseEntryWriteSerializer
        return ExpenseEntrySerializer

    @action(detail=False, methods=["post"], url_path="create")
    def create_entry(self, request):
        serializer = ExpenseEntryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(created_by=request.user, status="submitted")
        return Response(
            ExpenseEntrySerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_entry(self, request, pk=None):
        instance = self.get_object()
        if instance.status == "posted":
            return Response({"detail": "Already posted."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            from accounting.models import Journal, JournalEntry, JournalItem
            journal = Journal.objects.filter(journal_type="general").first() or Journal.objects.filter(journal_type="purchase").first()
            if journal:
                entry = JournalEntry.objects.create(
                    journal=journal,
                    date=instance.date,
                    reference=f"Expense: {instance.entry_number}",
                    status="posted",
                    total_debit=instance.amount,
                    total_credit=instance.amount,
                    posted_by=request.user,
                    posted_at=timezone.now(),
                )
                # Use FK account directly
                expense_account = instance.category
                if not expense_account:
                    from accounting.models import Account
                    expense_account = Account.objects.filter(account_type__classification="expense").first()
                cash_account = None
                if expense_account:
                    from accounting.models import Account
                    cash_account = Account.objects.filter(name__icontains="cash").first() or Account.objects.filter(code__startswith="101").first()
                if expense_account:
                    JournalItem.objects.create(journal_entry=entry, account=expense_account, label=instance.description[:200] or f"Expense entry", debit=instance.amount, credit=0)
                    expense_account.current_balance += instance.amount
                    expense_account.save(update_fields=["current_balance"])
                if cash_account:
                    JournalItem.objects.create(journal_entry=entry, account=cash_account, label=instance.description[:200] or f"Expense entry", debit=0, credit=instance.amount)
                    cash_account.current_balance -= instance.amount
                    cash_account.save(update_fields=["current_balance"])

            instance.status = "posted"
            instance.save(update_fields=["status"])
        return Response(ExpenseEntrySerializer(instance).data)


# ──────────────────────────────────────────────────────────────────────────────
# Payroll Entries
# ──────────────────────────────────────────────────────────────────────────────

class PayrollEntryViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = PayrollEntry.objects.select_related("created_by").all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["entry_number", "payroll_cycle", "funding_source"]
    ordering_fields = ["date", "gross_amount", "created_at"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        if self.request.method in ("POST", "PUT", "PATCH"):
            return PayrollEntryWriteSerializer
        return PayrollEntrySerializer

    @action(detail=False, methods=["post"], url_path="create")
    def create_entry(self, request):
        serializer = PayrollEntryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(created_by=request.user, status="draft")
        return Response(
            PayrollEntrySerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_entry(self, request, pk=None):
        instance = self.get_object()
        if instance.status == "posted":
            return Response({"detail": "Already posted."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            from accounting.models import Journal, JournalEntry, JournalItem, Account
            journal = Journal.objects.filter(journal_type="general").first() or Journal.objects.filter(journal_type="purchase").first()
            if journal:
                entry = JournalEntry.objects.create(
                    journal=journal,
                    date=instance.date,
                    reference=f"Payroll: {instance.entry_number}",
                    status="posted",
                    total_debit=instance.gross_amount,
                    total_credit=instance.gross_amount,
                    posted_by=request.user,
                    posted_at=timezone.now(),
                )
                # Use FK if set, otherwise fuzzy fallback
                expense_account = instance.expense_account
                if not expense_account:
                    expense_account = Account.objects.filter(name__icontains="salary").first() or Account.objects.filter(name__icontains="wage").first() or Account.objects.filter(account_type__classification="expense").first()
                if expense_account:
                    JournalItem.objects.create(journal_entry=entry, account=expense_account, label=f"Payroll: {instance.payroll_cycle}", debit=instance.gross_amount, credit=0)
                    expense_account.current_balance += instance.gross_amount
                    expense_account.save(update_fields=["current_balance"])
                # Use FK if set, otherwise fuzzy fallback
                cash_account = instance.bank_account
                if not cash_account:
                    cash_account = Account.objects.filter(name__icontains="cash").first() or Account.objects.filter(code__startswith="101").first()
                if cash_account:
                    JournalItem.objects.create(journal_entry=entry, account=cash_account, label=f"Payroll: {instance.payroll_cycle}", debit=0, credit=instance.net_amount)
                    cash_account.current_balance -= instance.net_amount
                    cash_account.save(update_fields=["current_balance"])
                if instance.liability_amount > 0:
                    # Use FK if set, otherwise fuzzy fallback
                    liability_account = instance.liability_account
                    if not liability_account:
                        liability_account = Account.objects.filter(name__icontains="payable").first() or Account.objects.filter(account_type__classification="liability").first()
                    if liability_account:
                        JournalItem.objects.create(journal_entry=entry, account=liability_account, label=f"Payroll deductions: {instance.payroll_cycle}", debit=0, credit=instance.liability_amount)
                        liability_account.current_balance += instance.liability_amount
                        liability_account.save(update_fields=["current_balance"])

            instance.status = "posted"
            instance.save(update_fields=["status"])
        return Response(PayrollEntrySerializer(instance).data)


# ──────────────────────────────────────────────────────────────────────────────
# Inventory Entries
# ──────────────────────────────────────────────────────────────────────────────

class InventoryEntryViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = InventoryEntry.objects.select_related("created_by").all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["entry_number", "warehouse", "item_reference", "procurement_reference"]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        if self.request.method in ("POST", "PUT", "PATCH"):
            return InventoryEntryWriteSerializer
        return InventoryEntrySerializer

    @action(detail=False, methods=["post"], url_path="create")
    def create_entry(self, request):
        serializer = InventoryEntryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(created_by=request.user, status="draft")
        return Response(
            InventoryEntrySerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_entry(self, request, pk=None):
        instance = self.get_object()
        if instance.status == "posted":
            return Response({"detail": "Already posted."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            from accounting.models import Journal, JournalEntry, JournalItem, Account
            journal = Journal.objects.filter(journal_type="general").first() or Journal.objects.filter(journal_type="purchase").first()
            if journal:
                entry = JournalEntry.objects.create(
                    journal=journal,
                    date=instance.date,
                    reference=f"Inventory: {instance.entry_number}",
                    status="posted",
                    total_debit=instance.amount,
                    total_credit=instance.amount,
                    posted_by=request.user,
                    posted_at=timezone.now(),
                )
                # Use FK if set, otherwise fuzzy fallback
                inventory_account = instance.inventory_account
                if not inventory_account:
                    inventory_account = Account.objects.filter(name__icontains="inventory").first() or Account.objects.filter(name__icontains="stock").first() or Account.objects.filter(account_type__classification="asset", account_type__liquidity_type="current").first()
                if inventory_account:
                    JournalItem.objects.create(journal_entry=entry, account=inventory_account, label=f"Inventory: {instance.item_reference}", debit=instance.amount, credit=0)
                    inventory_account.current_balance += instance.amount
                    inventory_account.save(update_fields=["current_balance"])
                # Use FK if set, otherwise fuzzy fallback
                cogs_account = instance.cogs_account
                if not cogs_account:
                    cogs_account = Account.objects.filter(name__icontains="cost of goods").first() or Account.objects.filter(name__icontains="cogs").first() or Account.objects.filter(account_type__classification="expense").first()
                if cogs_account:
                    JournalItem.objects.create(journal_entry=entry, account=cogs_account, label=f"Inventory: {instance.item_reference}", debit=0, credit=instance.amount)
                    cogs_account.current_balance -= instance.amount
                    cogs_account.save(update_fields=["current_balance"])

            instance.status = "posted"
            instance.save(update_fields=["status"])
        return Response(InventoryEntrySerializer(instance).data)
