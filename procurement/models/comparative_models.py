from django.db import models, transaction
from django.utils import timezone


class CSSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class ComparativeStatement(models.Model):
    """Comparative analysis of vendor quotations for an RFQ."""

    STATUS_CHOICES = [
        ("under_review", "Under Review"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    cs_number = models.CharField(max_length=50, unique=True, blank=True)
    rfq = models.ForeignKey(
        "procurement.RFQ",
        on_delete=models.CASCADE,
        related_name="comparative_statements",
    )
    title = models.CharField(max_length=255, null=True, blank=True)
    quotations = models.ManyToManyField(
        "procurement.VendorQuotation", blank=True, related_name="comparative_statements"
    )
    recommended_vendor = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommended_in_cs",
    )
    description = models.TextField(null=True, blank=True)
    justification = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_approval", null=True, blank=True)

    # Audit / auto-extraction info
    auto_extracted = models.BooleanField(default=False)
    extraction_date = models.DateTimeField(null=True, blank=True)
    extraction_source = models.TextField(null=True, blank=True)

    # Meta overrides (auto-populated from RFQ/requisition when blank)
    budget_code = models.CharField(max_length=100, null=True, blank=True)
    project = models.CharField(max_length=255, null=True, blank=True)
    office = models.CharField(max_length=255, null=True, blank=True)

    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prepared_comparatives",
    )
    approved_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_comparatives",
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.cs_number:
            current_year = timezone.now().year
            with transaction.atomic():
                sequence, _ = CSSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])
                self.cs_number = f"CS-{current_year}-{sequence.last_number:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cs_number} - {self.title}"


class ComparativeApprovalWorkflow(models.Model):
    """Multi-level approval workflow for a comparative statement."""

    STATUS_CHOICES = [
        ("approved", "Approved"),
        ("pending", "Pending"),
        ("not_started", "Not Started"),
        ("rejected", "Rejected"),
    ]

    comparative = models.ForeignKey(
        ComparativeStatement,
        on_delete=models.CASCADE,
        related_name="approval_workflow",
    )
    level = models.PositiveIntegerField()
    role = models.CharField(max_length=255)
    approver_name = models.CharField(max_length=255, null=True, blank=True)
    designation = models.CharField(max_length=255, null=True, blank=True)
    approver = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cs_approvals",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="not_started")
    date = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    notification_sent = models.BooleanField(default=False)
    notification_date = models.DateTimeField(null=True, blank=True)
    members = models.JSONField(default=list, blank=True, null=True)

    class Meta:
        ordering = ["level"]
        unique_together = [("comparative", "level")]

    def __str__(self):
        return f"{self.comparative.cs_number} - Level {self.level}"


class ComparativeNote(models.Model):
    """Free-text note on a comparative statement."""

    comparative = models.ForeignKey(
        ComparativeStatement,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    author = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cs_notes",
    )
    role = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    text = models.TextField()

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.comparative.cs_number} - Note by {self.author}"


class ComparativeVendorEvaluation(models.Model):
    """Technical score for a vendor in a comparative statement."""

    comparative = models.ForeignKey(
        ComparativeStatement,
        on_delete=models.CASCADE,
        related_name="vendor_evaluations",
    )
    vendor = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.CASCADE,
        related_name="cs_evaluations",
    )
    total_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_recommended = models.BooleanField(default=False)

    class Meta:
        unique_together = [("comparative", "vendor")]
        ordering = ["-total_score"]

    def __str__(self):
        return f"{self.comparative.cs_number} - {self.vendor} ({self.total_score})"


class ComparativeVendorScoreCriteria(models.Model):
    """Individual scoring criteria for a vendor evaluation."""

    evaluation = models.ForeignKey(
        ComparativeVendorEvaluation,
        on_delete=models.CASCADE,
        related_name="criteria",
    )
    name = models.CharField(max_length=255)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.evaluation} - {self.name}"


class ComparativeVendorFinancial(models.Model):
    """Financial summary for one vendor's bid in a comparative statement."""

    comparative = models.ForeignKey(
        ComparativeStatement,
        on_delete=models.CASCADE,
        related_name="vendor_financials",
    )
    vendor = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.CASCADE,
        related_name="cs_financials",
    )
    quotation = models.ForeignKey(
        "procurement.VendorQuotation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cs_financials",
    )
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ait = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    delivery = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        unique_together = [("comparative", "vendor")]
        ordering = ["grand_total"]

    def __str__(self):
        return f"{self.comparative.cs_number} - {self.vendor} financial"


class ComparativeLineItem(models.Model):
    """Per-item, per-vendor price comparison in a comparative statement."""

    comparative = models.ForeignKey(
        ComparativeStatement, on_delete=models.CASCADE, related_name="line_items"
    )
    item = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True)
    vendor = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cs_line_items",
    )
    quotation = models.ForeignKey(
        "procurement.VendorQuotation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    quoted_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_lowest = models.BooleanField(default=False)
    is_recommended = models.BooleanField(default=False)
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["item", "quoted_price"]

    def save(self, *args, **kwargs):
        self.total_price = self.quoted_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.comparative.cs_number} - {self.item} - {self.vendor}"


class ComparativeNotificationLog(models.Model):
    """Notification/event log for a comparative statement."""

    comparative = models.ForeignKey(
        ComparativeStatement,
        on_delete=models.CASCADE,
        related_name="notification_logs",
    )
    date = models.DateTimeField(auto_now_add=True)
    event = models.CharField(max_length=255)
    recipients = models.CharField(max_length=500, null=True, blank=True)
    channel = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.comparative.cs_number} - {self.event}"
