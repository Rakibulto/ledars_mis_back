from django.db import models
from django.db import transaction as db_transaction
from django.utils import timezone


class Vendor(models.Model):
    """Accounting vendor (may link to procurement Supplier)."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("blocked", "Blocked"),
    ]
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    payable_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_payable",
    )
    payment_terms_days = models.IntegerField(default=30)
    credit_limit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_payable = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True
    )
    supplier = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounting_vendor",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}" if self.code else self.name

    def save(self, *args, **kwargs):
        if not self.code:
            year = timezone.now().year
            count = Vendor.objects.filter(created_at__year=year).count() + 1
            self.code = f"VND-{year}-{count:04d}"
        super().save(*args, **kwargs)


class Bill(models.Model):
    """Accounts Payable — vendor bills/invoices (Odoo-style)."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("posted", "Posted"),
        ("partial", "Partially Paid"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]
    bill_number = models.CharField(max_length=50, unique=True, blank=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="bills")
    vendor_reference = models.CharField(max_length=100, blank=True)
    journal = models.ForeignKey(
        "accounting.Journal", on_delete=models.PROTECT, related_name="bills"
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bills",
    )
    bill_date = models.DateField()
    due_date = models.DateField()
    fiscal_period = models.ForeignKey(
        "accounting.FiscalPeriod", on_delete=models.SET_NULL, null=True, blank=True
    )
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True
    )
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bills",
    )
    cost_center = models.ForeignKey(
        "accounting.CostCenter", on_delete=models.SET_NULL, null=True, blank=True
    )
    payment_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bills_payment",
        help_text="Cash/Bank account from which payment will be made",
    )
    purchase_order = models.ForeignKey(
        "procurement.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bills",
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    # Workspace UI fields
    dispute_flag = models.BooleanField(default=False)
    match_status = models.CharField(max_length=50, blank=True, default="Awaiting receipt")
    payment_proposal = models.CharField(max_length=200, blank=True)
    approval_route = models.CharField(max_length=100, blank=True)
    goods_receipt_ref = models.CharField(max_length=100, blank=True)
    work_order = models.ForeignKey(
        "procurement.WorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_bills",
    )
    primary_grn = models.ForeignKey(
        "procurement.GoodsReceiptNote",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_vendor_bills",
    )
    grns = models.ManyToManyField(
        "procurement.GoodsReceiptNote",
        blank=True,
        related_name="linked_vendor_bills",
    )
    source_bank_account = models.ForeignKey(
        "accounting.BankAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_bills",
        help_text="Treasury bank account selected for payment",
    )
    source_cheque = models.ForeignKey(
        "accounting.Check",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_bills",
        help_text="Cheque selected for payment",
    )
    invoice_file = models.FileField(
        upload_to="accounting/vendor_bills/invoices/%Y/%m/",
        blank=True,
        null=True,
    )
    mushuk_file = models.FileField(
        upload_to="accounting/vendor_bills/mushuk/%Y/%m/",
        blank=True,
        null=True,
    )
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-bill_date", "-id"]

    def __str__(self):
        return self.bill_number or f"BILL-{self.id}"

    def save(self, *args, **kwargs):
        if not self.bill_number:
            import datetime
            date_val = self.bill_date
            if isinstance(date_val, str):
                try:
                    date_val = datetime.date.fromisoformat(date_val)
                except (ValueError, TypeError):
                    date_val = None
            year = date_val.year if date_val else timezone.now().year
            with db_transaction.atomic():
                # Use select_for_update to prevent race conditions
                last_bill = (
                    Bill.objects
                    .filter(bill_number__startswith=f"BILL-{year}-")
                    .order_by("-bill_number")
                    .first()
                )
                if last_bill and last_bill.bill_number:
                    try:
                        last_num = int(last_bill.bill_number.split("-")[-1])
                    except (ValueError, IndexError):
                        last_num = 0
                    next_num = last_num + 1
                else:
                    next_num = 1
                self.bill_number = f"BILL-{year}-{next_num:05d}"
        self.amount_due = max(0, self.total_amount - self.amount_paid)
        super().save(*args, **kwargs)


class BillLine(models.Model):
    """Line items of a vendor bill."""

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey("accounting.Account", on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax = models.ForeignKey(
        "accounting.Tax", on_delete=models.SET_NULL, null=True, blank=True
    )
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    analytic_account = models.ForeignKey(
        "accounting.AnalyticAccount", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.description} ({self.total})"

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        self.total = self.subtotal + self.tax_amount
        super().save(*args, **kwargs)


class BillPayment(models.Model):
    """Links payments to bills."""

    bill = models.ForeignKey(
        Bill, on_delete=models.CASCADE, related_name="bill_payments"
    )
    payment = models.ForeignKey(
        "accounting.Payment", on_delete=models.CASCADE, related_name="bill_payments"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bill.bill_number} <- {self.payment.reference}: {self.amount}"


class DebitNote(models.Model):
    """Debit notes against vendor bills."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("applied", "Applied"),
        ("cancelled", "Cancelled"),
    ]
    debit_note_number = models.CharField(max_length=50, unique=True, blank=True)
    vendor = models.ForeignKey(
        Vendor, on_delete=models.PROTECT, related_name="debit_notes"
    )
    original_bill = models.ForeignKey(
        Bill,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debit_notes",
    )
    journal = models.ForeignKey(
        "accounting.Journal", on_delete=models.PROTECT, related_name="debit_notes"
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debit_notes",
    )
    date = models.DateField()
    reason = models.TextField()
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    # Workspace UI fields
    bill_ref = models.CharField(max_length=100, blank=True)  # free-text reference; FK resolved separately via original_bill
    adjustment_type = models.CharField(max_length=100, blank=True)
    approval_route = models.CharField(max_length=100, blank=True)
    dispute_reference = models.CharField(max_length=100, blank=True)
    application_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.debit_note_number or f"DN-{self.id}"

    def save(self, *args, **kwargs):
        if not self.debit_note_number:
            import datetime
            date_val = self.date
            if isinstance(date_val, str):
                try:
                    date_val = datetime.date.fromisoformat(date_val)
                except (ValueError, TypeError):
                    date_val = None
            year = date_val.year if date_val else timezone.now().year
            with db_transaction.atomic():
                count = DebitNote.objects.filter(date__year=year).count() + 1
                self.debit_note_number = f"DN-{year}-{count:05d}"
        super().save(*args, **kwargs)


class DebitNoteLine(models.Model):
    """Line items of a debit note."""

    debit_note = models.ForeignKey(
        DebitNote, on_delete=models.CASCADE, related_name="lines"
    )
    account = models.ForeignKey("accounting.Account", on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.description} ({self.total})"


class VendorCredit(models.Model):
    """Vendor credit balance tracking."""

    vendor = models.OneToOneField(
        Vendor, on_delete=models.CASCADE, related_name="credit"
    )
    credit_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vendor.name}: {self.credit_balance}"
