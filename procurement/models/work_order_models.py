from decimal import Decimal, InvalidOperation
from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.utils import timezone


class WOSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class WorkOrder(models.Model):
    """Purchase/Work order issued to a vendor after award acceptance."""

    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Pending Approval", "Pending Approval"),
        ("Approved", "Approved"),
        ("Sent to Vendor", "Sent to Vendor"),
        ("Accepted by Vendor", "Accepted by Vendor"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    ]

    APPROVAL_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending-approval", "Pending Approval"),
        ("pending-committee", "Pending Committee"),
        ("fully-approved", "Fully Approved"),
        ("rejected", "Rejected"),
    ]

    VENDOR_STATUS_CHOICES = [
        ("not-sent", "Not Sent"),
        ("sent", "Sent"),
        ("pending-acceptance", "Pending Acceptance"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    DELIVERY_STATUS_CHOICES = [
        ("not-started", "Not Started"),
        ("in-progress", "In Progress"),
        ("partial", "Partial"),
        ("completed", "Completed"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("not-started", "Not Started"),
        ("partial", "Partial"),
        ("paid", "Paid"),
    ]

    wo_number = models.CharField(max_length=50, unique=True, blank=True)
    award = models.ForeignKey(
        "procurement.Award",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="work_orders",
    )
    vendor = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="work_orders",
    )

    # Descriptive fields
    title = models.CharField(max_length=500, null=True, blank=True)
    category = models.CharField(max_length=255, null=True, blank=True)

    # Dates
    order_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)  # delivery deadline
    delivery_address = models.TextField(null=True, blank=True)

    # Payment & warranty
    payment_terms = models.CharField(max_length=500, null=True, blank=True)
    warranty_period = models.CharField(max_length=100, null=True, blank=True)
    acceptance_deadline = models.DateField(null=True, blank=True)
    tc_template = models.CharField(max_length=100, null=True, blank=True)

    # Financial
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # T&C / notes stored as text
    terms_and_conditions = models.TextField(null=True, blank=True)
    special_instructions = models.TextField(null=True, blank=True)

    # Status fields
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="Draft")
    approval_status = models.CharField(
        max_length=30, choices=APPROVAL_STATUS_CHOICES, default="draft"
    )
    vendor_status = models.CharField(
        max_length=25, choices=VENDOR_STATUS_CHOICES, default="not-sent"
    )
    vendor_acceptance_date = models.DateField(null=True, blank=True)
    delivery_status = models.CharField(
        max_length=20, choices=DELIVERY_STATUS_CHOICES, default="not-started"
    )
    payment_status = models.CharField(
        max_length=15, choices=PAYMENT_STATUS_CHOICES, default="not-started"
    )

    # Metadata
    auto_generated = models.BooleanField(default=False)
    approval_level = models.CharField(
        max_length=20, null=True, blank=True
    )  # e.g. "3/3"
    notification_sent = models.BooleanField(default=False)
    notification_channel = models.CharField(max_length=100, null=True, blank=True)

    approver = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_work_orders_to_approve",
        help_text="Designated user who has permission to approve this work order.",
    )
    approved_by = models.ForeignKey(
        "employee.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_work_orders",
        help_text="Auto-set to the employee who clicked approve.",
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_work_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def calculate_total_amount(self):
        total = Decimal("0.00")
        award = self.award
        award_items = award.items if award and award.items else []

        if not award_items and award and getattr(award, "comparative_statement", None):
            cs = award.comparative_statement
            direct_quote = (
                cs.quotations.filter(is_direct_evaluation=True).order_by("-id").first()
            )
            if direct_quote is None:
                direct_quote = (
                    cs.quotations.filter(vendor__isnull=True).order_by("-id").first()
                )
            if direct_quote is not None:
                award_items = [
                    {
                        "quantity": getattr(item, "quantity", 0),
                        "unitPrice": getattr(item, "unit_price", 0),
                        "unit_price": getattr(item, "unit_price", 0),
                        "total": getattr(item, "total", None),
                    }
                    for item in direct_quote.quotation_items.all()
                ]

        for award_item in award_items or []:
            if not isinstance(award_item, dict):
                continue
            item_total = award_item.get("total")
            if item_total is None:
                quantity = award_item.get("quantity") or 0
                unit_price = award_item.get("unitPrice")
                if unit_price is None:
                    unit_price = award_item.get("unit_price")
                try:
                    item_total = Decimal(str(quantity)) * Decimal(str(unit_price))
                except (TypeError, ValueError, InvalidOperation):
                    item_total = Decimal("0.00")
            try:
                total += Decimal(str(item_total))
            except (TypeError, ValueError, InvalidOperation):
                continue
        self.total_amount = total
        self.save(update_fields=["total_amount"])

    def save(self, *args, **kwargs):
        if not self.wo_number:
            current_year = timezone.now().year
            with transaction.atomic():
                sequence, _ = WOSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])
                self.wo_number = f"WO-{current_year}-{sequence.last_number:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.wo_number}"


class WorkOrderItem(models.Model):
    """Line item in a work order."""

    ITEM_DELIVERY_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("partial", "Partial"),
        ("completed", "Completed"),
    ]

    work_order = models.ForeignKey(
        WorkOrder, on_delete=models.CASCADE, related_name="work_order_items"
    )
    item = models.ForeignKey(
        "procurement.Award", on_delete=models.SET_NULL, null=True, blank=True
    )

    # Free-text fields so items can be entered without a linked inventory Item
    description = models.CharField(max_length=500, null=True, blank=True)
    specification = models.TextField(null=True, blank=True)

    delivered = models.PositiveIntegerField(default=0)
    item_delivery_status = models.CharField(
        max_length=20, choices=ITEM_DELIVERY_STATUS_CHOICES, default="pending"
    )

    @property
    def total_price(self):
        award = self.item
        if award and award.items:
            for award_item in award.items or []:
                if not isinstance(award_item, dict):
                    continue
                if self.description and self.description == award_item.get(
                    "description"
                ):
                    quantity = award_item.get("quantity") or 0
                    unit_price = (
                        award_item.get("unitPrice")
                        if award_item.get("unitPrice") is not None
                        else award_item.get("unit_price")
                    )
                    try:
                        return Decimal(str(quantity)) * Decimal(str(unit_price))
                    except (TypeError, ValueError, InvalidOperation):
                        return Decimal("0.00")
        return Decimal("0.00")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.work_order_id:
            self.work_order.calculate_total_amount()

    def delete(self, *args, **kwargs):
        wo = self.work_order
        super().delete(*args, **kwargs)
        if wo:
            wo.calculate_total_amount()

    def __str__(self):
        return f"{self.work_order.wo_number} - {self.description or self.item}"


class WorkOrderApprovalHistory(models.Model):
    """Approval trail for a work order."""

    work_order = models.ForeignKey(
        WorkOrder, on_delete=models.CASCADE, related_name="approval_history"
    )
    approver = models.CharField(max_length=255)
    role = models.CharField(max_length=255, null=True, blank=True)
    action = models.CharField(max_length=100)
    date = models.CharField(
        max_length=100, null=True, blank=True
    )  # stored as display string
    comments = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.work_order.wo_number} - {self.approver} ({self.action})"


class WorkOrderNotificationLog(models.Model):
    """Notification log entry for a work order."""

    work_order = models.ForeignKey(
        WorkOrder, on_delete=models.CASCADE, related_name="notification_log"
    )
    channel = models.CharField(max_length=100)
    date = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    recipient = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.work_order.wo_number} - {self.channel}"


class WorkOrderAttachment(models.Model):
    """File attachment for a work order."""

    DOCUMENT_TYPE_CHOICES = [
        ("general", "General"),
        ("delivery_note", "Delivery Note"),
        ("invoice", "Invoice"),
        ("quality_certificate", "Quality Certificate"),
        ("photo", "Photo"),
    ]

    work_order = models.ForeignKey(
        WorkOrder, on_delete=models.CASCADE, related_name="attachments"
    )
    document_type = models.CharField(
        max_length=30, choices=DOCUMENT_TYPE_CHOICES, default="general"
    )
    name = models.CharField(max_length=255)
    file = models.FileField(
        upload_to="work_order_attachments/",
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "xls",
                    "xlsx",
                    "csv",
                    "doc",
                    "docx",
                    "txt",
                    "png",
                    "jpg",
                    "jpeg",
                    "gif",
                    "svg",
                    "webp",
                    "bmp",
                    "ppt",
                    "pptx",
                    "zip",
                    "rar",
                    "odt",
                    "ods",
                    "odp",
                ]
            )
        ],
    )
    upload_date = models.DateField(auto_now_add=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["upload_date"]

    def __str__(self):
        return f"{self.work_order.wo_number} - {self.name}"


class VendorAcceptance(models.Model):
    """Vendor's formal acceptance or rejection of a work order."""

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Accepted", "Accepted"),
        ("Rejected", "Rejected"),
        ("Negotiation", "Negotiation"),
    ]

    work_order = models.OneToOneField(
        WorkOrder, on_delete=models.CASCADE, related_name="vendor_acceptance"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    response_date = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    attachment = models.FileField(upload_to="vendor_acceptance/", null=True, blank=True)
    rejected_vendor = models.JSONField(
        null=True, blank=True,
        help_text="Vendor details when rejected: {id, name, email}"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.work_order.wo_number} - {self.status}"
