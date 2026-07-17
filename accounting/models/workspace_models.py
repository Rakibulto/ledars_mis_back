"""
Transaction workspace models for Customer Receipts, Bank Deposits, and Supplier Payments.
These are dedicated workspace-level models for the accounting-finance transaction pages.
"""
from django.db import models
from django.db import transaction as db_transaction
from django.utils import timezone


class CustomerReceipt(models.Model):
    """Customer cash receipt with allocation tracking."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("pending", "Pending"),
    ]
    ALLOCATION_STATUS = [
        ("unallocated", "Unallocated"),
        ("partially_allocated", "Partially Allocated"),
        ("fully_allocated", "Fully Allocated"),
    ]

    receipt_number = models.CharField(max_length=50, unique=True, blank=True)
    customer = models.ForeignKey(
        "accounting.Customer",
        on_delete=models.PROTECT,
        related_name="workspace_receipts",
    )
    donor = models.ForeignKey(
        "donor.Donor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workspace_receipts",
        help_text="Direct link to Donor for CustomerInvoice receipts.",
    )
    date = models.DateField()
    method = models.CharField(max_length=50, blank=True)
    bank_account_name = models.CharField(max_length=100, blank=True)
    bank_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_receipts",
        help_text="COA account where received money is deposited.",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    unapplied_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    allocation_status = models.CharField(
        max_length=25, choices=ALLOCATION_STATUS, default="unallocated"
    )
    reference = models.CharField(max_length=200, blank=True)
    collection_owner = models.CharField(max_length=100, blank=True)
    remittance_advice = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_receipts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.receipt_number or f"RCPT-{self.id}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            year = timezone.now().year
            with db_transaction.atomic():
                count = CustomerReceipt.objects.filter(created_at__year=year).count() + 1
                self.receipt_number = f"RCPT-{year}-{count:03d}"
        super().save(*args, **kwargs)


class CustomerReceiptAllocation(models.Model):
    """Allocation of a customer receipt to an invoice via GenericForeignKey."""

    receipt = models.ForeignKey(
        CustomerReceipt, on_delete=models.CASCADE, related_name="allocations"
    )
    invoice_number = models.CharField(max_length=50, blank=True, default="")
    invoice_content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    invoice_object_id = models.PositiveIntegerField(null=True, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.receipt.receipt_number} -> {self.invoice_number or self.invoice_object_id}: {self.amount}"


class BankDeposit(models.Model):
    """Treasury bank deposit with slip tracking and reconciliation status."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("posted", "Posted"),
    ]
    RECON_STATUS = [
        ("pending", "Pending"),
        ("reconciled", "Reconciled"),
    ]

    deposit_number = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField()
    bank_account_name = models.CharField(max_length=100, blank=True)
    bank_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_deposits",
        help_text="COA bank account receiving the deposit.",
    )
    source = models.CharField(max_length=100, blank=True)
    deposit_method = models.CharField(max_length=50, blank=True)
    deposit_slip_ref = models.CharField(max_length=100, blank=True)
    prepared_by = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    reconciliation_status = models.CharField(
        max_length=15, choices=RECON_STATUS, default="pending"
    )
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_deposits_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.deposit_number or f"DEP-{self.id}"

    def save(self, *args, **kwargs):
        if not self.deposit_number:
            year = timezone.now().year
            with db_transaction.atomic():
                count = BankDeposit.objects.filter(created_at__year=year).count() + 1
                self.deposit_number = f"DEP-{year}-{count:03d}"
        super().save(*args, **kwargs)


class SupplierPayment(models.Model):
    """Supplier payment run record with release queue controls."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("pending", "Pending"),
    ]
    RELEASE_STATUS = [
        ("queued", "Queued"),
        ("released", "Released"),
        ("blocked", "Blocked"),
    ]

    payment_number = models.CharField(max_length=50, unique=True, blank=True)
    vendor = models.ForeignKey(
        "accounting.Vendor",
        on_delete=models.PROTECT,
        related_name="supplier_payments",
    )
    date = models.DateField()
    method = models.CharField(max_length=50, blank=True)
    bank_account_name = models.CharField(max_length=100, blank=True)
    bank_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_payments",
        help_text="COA bank account from which payment is made.",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    release_status = models.CharField(
        max_length=15, choices=RELEASE_STATUS, default="queued"
    )
    payment_run = models.CharField(max_length=50, blank=True)
    bill_refs = models.JSONField(default=list)
    approval_route = models.CharField(max_length=100, blank=True)
    settlement_reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_payments_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.payment_number or f"SPAY-{self.id}"

    def save(self, *args, **kwargs):
        if not self.payment_number:
            year = timezone.now().year
            with db_transaction.atomic():
                count = SupplierPayment.objects.filter(created_at__year=year).count() + 1
                self.payment_number = f"SPAY-{year}-{count:03d}"
        super().save(*args, **kwargs)


# ──────────────────────────────────────────────────────────────────────────────
# Additional workspace transaction models
# ──────────────────────────────────────────────────────────────────────────────

class CashWorkspaceTransaction(models.Model):
    """Petty cash inflow/outflow workspace entries."""

    DIRECTION_CHOICES = [("inflow", "Inflow"), ("outflow", "Outflow")]
    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    transaction_number = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField()
    account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_workspace_transactions",
    )
    counterparty = models.CharField(max_length=200)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default="outflow")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    payment_method = models.CharField(max_length=100, blank=True)
    reference = models.CharField(max_length=200, blank=True)
    description = models.TextField()
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.transaction_number or f"CASH-{self.id}"

    def save(self, *args, **kwargs):
        if not self.transaction_number:
            import datetime
            date_val = self.date
            if isinstance(date_val, str):
                try:
                    date_val = datetime.date.fromisoformat(date_val)
                except (ValueError, TypeError):
                    date_val = None
            year = date_val.year if date_val else timezone.now().year
            with db_transaction.atomic():
                count = CashWorkspaceTransaction.objects.filter(date__year=year).count() + 1
                self.transaction_number = f"CASH-{year}-{count:05d}"
        super().save(*args, **kwargs)


class ContraEntry(models.Model):
    """Internal bank-to-cash / cash-to-bank transfer entries."""

    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    entry_number = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField()
    from_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contra_entries_from",
    )
    to_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contra_entries_to",
    )
    transfer_channel = models.CharField(max_length=100, blank=True)
    treasury_owner = models.CharField(max_length=200, blank=True)
    reference = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    description = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.entry_number or f"CONTRA-{self.id}"

    def save(self, *args, **kwargs):
        if not self.entry_number:
            import datetime
            date_val = self.date
            if isinstance(date_val, str):
                try:
                    date_val = datetime.date.fromisoformat(date_val)
                except (ValueError, TypeError):
                    date_val = None
            year = date_val.year if date_val else timezone.now().year
            with db_transaction.atomic():
                count = ContraEntry.objects.filter(date__year=year).count() + 1
                self.entry_number = f"CONTRA-{year}-{count:05d}"
        super().save(*args, **kwargs)


class ExpenseEntry(models.Model):
    """Operational expense entry workspace."""

    STATUS_CHOICES = [("submitted", "Submitted"), ("posted", "Posted")]

    entry_number = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField()
    category = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_entries",
    )
    employee = models.CharField(max_length=200)
    cost_center = models.CharField(max_length=100, blank=True)
    approval_route = models.CharField(max_length=200, blank=True)
    reference = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    description = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="submitted")
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.entry_number or f"EXP-{self.id}"

    def save(self, *args, **kwargs):
        if not self.entry_number:
            import datetime
            date_val = self.date
            if isinstance(date_val, str):
                try:
                    date_val = datetime.date.fromisoformat(date_val)
                except (ValueError, TypeError):
                    date_val = None
            year = date_val.year if date_val else timezone.now().year
            with db_transaction.atomic():
                count = ExpenseEntry.objects.filter(date__year=year).count() + 1
                self.entry_number = f"EXP-{year}-{count:05d}"
        super().save(*args, **kwargs)


class PayrollEntry(models.Model):
    """Payroll batch posting workspace entry."""

    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    entry_number = models.CharField(max_length=50, unique=True, blank=True)
    payroll_cycle = models.CharField(max_length=200)
    date = models.DateField()
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    employee_count = models.IntegerField(default=0)
    gross_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    liability_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    expense_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_expense_entries",
        help_text="COA account for salary/wage expense.",
    )
    bank_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_bank_entries",
        help_text="COA bank/cash account for net payment.",
    )
    liability_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_liability_entries",
        help_text="COA account for payroll deductions/payable.",
    )
    approval_route = models.CharField(max_length=200, blank=True)
    funding_source = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.entry_number or f"PAYROLL-{self.id}"

    def save(self, *args, **kwargs):
        import datetime
        if not self.entry_number:
            date_val = self.date
            if isinstance(date_val, str):
                try:
                    date_val = datetime.date.fromisoformat(date_val)
                except (ValueError, TypeError):
                    date_val = None
            year = date_val.year if date_val else timezone.now().year
            with db_transaction.atomic():
                count = PayrollEntry.objects.filter(date__year=year).count() + 1
                self.entry_number = f"PAYROLL-{year}-{count:05d}"
        # auto-compute liability
        self.liability_amount = max(
            float(self.gross_amount or 0) - float(self.net_amount or 0), 0
        )
        super().save(*args, **kwargs)


class InventoryEntry(models.Model):
    """Stock accounting journal entry workspace."""

    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    entry_number = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField()
    warehouse = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=100, blank=True)
    movement_type = models.CharField(max_length=50, blank=True)
    item_reference = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    inventory_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_asset_entries",
        help_text="COA asset account for inventory/stock.",
    )
    cogs_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_cogs_entries",
        help_text="COA expense account for cost of goods sold.",
    )
    procurement_reference = models.CharField(max_length=200, blank=True)
    description = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.entry_number or f"INVJ-{self.id}"

    def save(self, *args, **kwargs):
        import datetime
        if not self.entry_number:
            date_val = self.date
            if isinstance(date_val, str):
                try:
                    date_val = datetime.date.fromisoformat(date_val)
                except (ValueError, TypeError):
                    date_val = None
            year = date_val.year if date_val else timezone.now().year
            with db_transaction.atomic():
                count = InventoryEntry.objects.filter(date__year=year).count() + 1
                self.entry_number = f"INVJ-{year}-{count:05d}"
        # auto-compute amount
        self.amount = float(self.quantity or 0) * float(self.unit_cost or 0)
        super().save(*args, **kwargs)
