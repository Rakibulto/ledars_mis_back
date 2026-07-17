"""CustomerInvoice transaction model.

Mirrors every field visible in the frontend customer-invoices.jsx workspace,
including dunning workflow, billing metadata, collections posture, line items,
payment allocations, file attachments, and the chatter activity log.
"""

from django.db import models
from django.utils import timezone


class CustomerInvoice(models.Model):
    """Transaction-level customer invoice matching the frontend workspace exactly.

    Fields map 1-to-1 with the frontend's MOCK_INVOICES shape and the
    Create Invoice dialog form so the UI can drive the full lifecycle without
    any field mismatch.
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("partial", "Partially Paid"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    DUNNING_CHOICES = [
        ("none", "No Dunning"),
        ("stage_1", "Stage 1"),
        ("stage_2", "Stage 2"),
        ("stage_3", "Stage 3"),
    ]

    # ── Header ─────────────────────────────────────────────────────────────
    number = models.CharField(max_length=50, unique=True, blank=True, db_index=True)
    customer = models.ForeignKey(
        "donor.Donor",
        on_delete=models.PROTECT,
        related_name="transaction_invoices",
    )
    date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")

    # ── Collections / Dunning ──────────────────────────────────────────────
    dunning_stage = models.CharField(
        max_length=10, choices=DUNNING_CHOICES, default="none"
    )
    promise_to_pay = models.DateField(null=True, blank=True)
    credit_warning = models.BooleanField(default=False)

    # ── Billing metadata ───────────────────────────────────────────────────
    payment_terms = models.CharField(max_length=50, blank=True, default="Net 30")
    service_period = models.CharField(max_length=100, blank=True)
    billing_owner = models.CharField(max_length=200, blank=True)
    billing_reference = models.CharField(max_length=100, blank=True)

    # ── Recurring ──────────────────────────────────────────────────────────
    recurring = models.BooleanField(default=False)
    recurring_label = models.CharField(max_length=200, blank=True)

    # ── Financials ─────────────────────────────────────────────────────────
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    # ── Accounting dimensions ──────────────────────────────────────────────
    journal = models.ForeignKey(
        "accounting.Journal",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_invoices",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_invoices",
    )
    cost_center = models.ForeignKey(
        "accounting.CostCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    fiscal_period = models.ForeignKey(
        "accounting.FiscalPeriod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # ── Linked journal references (JSON array of strings, e.g. ["JE-2026-031"]) ──
    linked_journals = models.JSONField(default=list, blank=True)

    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_invoices",
    )

    # ── Audit ──────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_transaction_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Customer Invoice"
        verbose_name_plural = "Customer Invoices"

    def __str__(self):
        return self.number or f"CI-{self.id}"

    def save(self, *args, **kwargs):
        if not self.number:
            year = self.date.year if self.date else timezone.now().year
            count = CustomerInvoice.objects.filter(date__year=year).count() + 1
            self.number = f"INV-{year}-{count:03d}"
        # Always keep derived fields in sync
        self.total = self.subtotal + self.tax_amount
        self.balance_due = self.total - self.paid_amount
        # Guard: if created_by is set but its PK does not resolve (e.g. anonymous
        # user injected by the view), clear it so the FK constraint cannot fail.
        if self.created_by_id is not None:
            from authentication.models import User as _User
            if not _User.objects.filter(pk=self.created_by_id).exists():
                self.created_by = None
        super().save(*args, **kwargs)


class CustomerInvoiceLine(models.Model):
    """Line item of a CustomerInvoice — mirrors the frontend `lines` array."""

    invoice = models.ForeignKey(
        CustomerInvoice, on_delete=models.CASCADE, related_name="lines"
    )
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    analytic = models.CharField(max_length=200, blank=True)
    account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    analytic_account = models.ForeignKey(
        "accounting.AnalyticAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    cost_center = models.ForeignKey(
        "accounting.CostCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.description} – {self.amount}"

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class CustomerInvoiceAllocation(models.Model):
    """Payment allocation / receipt applied to a CustomerInvoice.

    Mirrors the frontend `allocations` array:
      { date, amount, method, reference }
    """

    invoice = models.ForeignKey(
        CustomerInvoice, on_delete=models.CASCADE, related_name="allocations"
    )
    date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    method = models.CharField(max_length=100, blank=True)
    reference = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.reference}: {self.amount}"


class CustomerInvoiceAttachment(models.Model):
    """File attachment linked to a CustomerInvoice.

    Mirrors the frontend `attachments` array:
      { id, name, type }
    """

    invoice = models.ForeignKey(
        CustomerInvoice, on_delete=models.CASCADE, related_name="attachments"
    )
    name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.name


class CustomerInvoiceChatter(models.Model):
    """Chatter / activity log entry for a CustomerInvoice.

    Mirrors the frontend `chatter` array:
      { id, author, time, message }
    `time_label` stores the human-readable display string shown in the UI
    (e.g. "15 Mar, 11:08").
    """

    TYPE_CHOICES = [
        ("note", "Note"),
        ("system", "System"),
        ("approval", "Approval"),
        ("payment", "Payment"),
        ("dunning", "Dunning"),
    ]

    invoice = models.ForeignKey(
        CustomerInvoice, on_delete=models.CASCADE, related_name="chatter"
    )
    author = models.CharField(max_length=200)
    message = models.TextField()
    time_label = models.CharField(max_length=100, blank=True)
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="note")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author}: {self.message[:60]}"
