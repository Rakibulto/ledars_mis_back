from django.db import models
from django.db import transaction as db_transaction
from django.utils import timezone


class Customer(models.Model):
    """Accounting customer for receivables."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    receivable_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_receivable",
    )
    payment_terms_days = models.IntegerField(default=30)
    credit_limit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_receivable = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}" if self.code else self.name

    def save(self, *args, **kwargs):
        if not self.code:
            year = timezone.now().year
            count = Customer.objects.filter(created_at__year=year).count() + 1
            self.code = f"CUST-{year}-{count:04d}"
        super().save(*args, **kwargs)


class Invoice(models.Model):
    """Accounts Receivable — customer invoices (Odoo-style)."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("posted", "Posted"),
        ("partial", "Partially Paid"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]
    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="invoices"
    )
    journal = models.ForeignKey(
        "accounting.Journal", on_delete=models.PROTECT, related_name="invoices"
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    invoice_date = models.DateField()
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
        related_name="invoices",
    )
    cost_center = models.ForeignKey(
        "accounting.CostCenter", on_delete=models.SET_NULL, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]

    def __str__(self):
        return self.invoice_number or f"INV-{self.id}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            year = self.invoice_date.year if self.invoice_date else timezone.now().year
            with db_transaction.atomic():
                count = Invoice.objects.filter(invoice_date__year=year).count() + 1
                self.invoice_number = f"INV-{year}-{count:05d}"
        self.amount_due = self.total_amount - self.amount_paid
        super().save(*args, **kwargs)


class InvoiceLine(models.Model):
    """Line items of a customer invoice."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey("accounting.Account", on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
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
        self.subtotal = (
            self.quantity * self.unit_price * (1 - self.discount_percent / 100)
        )
        self.total = self.subtotal + self.tax_amount
        super().save(*args, **kwargs)


class InvoicePayment(models.Model):
    """Links payments to invoices."""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="invoice_payments"
    )
    payment = models.ForeignKey(
        "accounting.Payment", on_delete=models.CASCADE, related_name="invoice_payments"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.invoice.invoice_number} <- {self.payment.reference}: {self.amount}"
        )


class CreditNote(models.Model):
    """Credit notes against customer invoices."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("applied", "Applied"),
        ("cancelled", "Cancelled"),
    ]
    credit_note_number = models.CharField(max_length=50, unique=True, blank=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="credit_notes"
    )
    original_invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_notes",
    )
    journal = models.ForeignKey(
        "accounting.Journal", on_delete=models.PROTECT, related_name="credit_notes"
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_notes",
    )
    date = models.DateField()
    reason = models.TextField()
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    # Workspace UI fields
    adjustment_type = models.CharField(max_length=100, blank=True)
    approval_route = models.CharField(max_length=100, blank=True)
    refund_reference = models.CharField(max_length=100, blank=True)
    application_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.credit_note_number or f"CN-{self.id}"

    def save(self, *args, **kwargs):
        if not self.credit_note_number:
            import datetime
            from django.db import transaction as db_transaction
            from django.utils import timezone as tz
            date_val = self.date
            if isinstance(date_val, str):
                try:
                    date_val = datetime.date.fromisoformat(date_val)
                except (ValueError, TypeError):
                    date_val = None
            year = date_val.year if date_val else tz.now().year
            with db_transaction.atomic():
                count = CreditNote.objects.filter(date__year=year).count() + 1
                self.credit_note_number = f"CN-{year}-{count:05d}"
        super().save(*args, **kwargs)


class CreditNoteLine(models.Model):
    """Line items of a credit note."""

    credit_note = models.ForeignKey(
        CreditNote, on_delete=models.CASCADE, related_name="lines"
    )
    account = models.ForeignKey("accounting.Account", on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.description} ({self.total})"
