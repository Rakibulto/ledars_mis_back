from django.db import models


class PaymentMethod(models.Model):
    """Payment methods — Cash, Bank Transfer, Cheque, Mobile Banking, etc."""

    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    payment_type = models.CharField(
        max_length=20,
        choices=[
            ("cash", "Cash"),
            ("bank", "Bank"),
            ("cheque", "Cheque"),
            ("mobile", "Mobile"),
            ("other", "Other"),
        ],
        default="bank",
    )
    journal = models.ForeignKey(
        "accounting.Journal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_methods",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Payment(models.Model):
    """Unified payment record — inbound (receipt) or outbound (payment)."""

    DIRECTION_CHOICES = [
        ("inbound", "Inbound (Receipt)"),
        ("outbound", "Outbound (Payment)"),
        ("internal", "Internal Transfer"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("posted", "Posted"),
        ("reconciled", "Reconciled"),
        ("cancelled", "Cancelled"),
    ]
    reference = models.CharField(max_length=100, unique=True, blank=True)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT)
    journal = models.ForeignKey(
        "accounting.Journal", on_delete=models.PROTECT, related_name="payments"
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    partner_type = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ("customer", "Customer"),
            ("vendor", "Vendor"),
            ("employee", "Employee"),
        ],
    )
    partner_id = models.IntegerField(null=True, blank=True)
    partner_name = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True
    )
    date = models.DateField()
    memo = models.TextField(blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    bank_account = models.ForeignKey(
        "accounting.BankAccount", on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.reference or f"PAY-{self.id}"


class PaymentAllocation(models.Model):
    """Allocates a payment to invoices or bills."""

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="allocations"
    )
    document_type = models.CharField(
        max_length=20,
        choices=[
            ("invoice", "Invoice"),
            ("bill", "Bill"),
            ("debit_note", "Debit Note"),
            ("credit_note", "Credit Note"),
        ],
    )
    document_id = models.IntegerField()
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.payment.reference} -> {self.document_type}#{self.document_id}: {self.allocated_amount}"
