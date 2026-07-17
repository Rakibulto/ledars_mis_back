from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone
from inventory.models.core import Category
 

class RFQVendorInvitation(models.Model):

    INVITE_STATUS_CHOICES = (
        ("sent", "Sent"),
        ("viewed", "Viewed"),
        ("submitted", "Submitted"),
        ("declined", "Declined"),
    )

    EMAIL_STATUS_CHOICES = (
        ("bounced", "Bounced"),
        ("delivered", "Delivered"),
    )

    rfq = models.ForeignKey(
        "procurement.RFQ", on_delete=models.CASCADE, related_name="vendor_invitations"
    )
    vendor = models.ForeignKey(
        "vendorportal.VendorProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="rfq_invitations"
    )
    invite_status = models.CharField(
        max_length=20, choices=INVITE_STATUS_CHOICES, default="sent"
    )
    submitted_status= models.BooleanField(default=False)
    email_status = models.CharField(
        max_length=20, choices=EMAIL_STATUS_CHOICES, null=True, blank=True
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("rfq", "vendor")]
        ordering = ["-invited_at"]

    def __str__(self):
        return f"{self.rfq or self.pk} - {self.vendor or self.pk} "


# RFQ Attachment model to store files related to RFQs
class RFQAttachment(models.Model):
    rfq = models.ForeignKey(
        "procurement.RFQ", on_delete=models.SET_NULL, null=True, blank=True, related_name="rfq_attachment"
    )
    files = models.FileField(upload_to="rfq_attachments/", null=True, blank=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at= models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class RFQ(models.Model):

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("published", "Published"),
        ("open", "Open"),
        ("under_evaluation", "Under Evaluation"),
        ("closed", "Closed"),
        ("awarded", "Awarded"),
        ("cancelled", "Cancelled"),
    )

    URGENCY_CHOICES = (
        ("normal", "Normal"),
        ("urgent", "Urgent"),
        ("critical", "Critical"),
    )


    rfq_number = models.CharField(
        max_length=50, unique=True, editable=False, null=True, blank=True
    )

    requisitions = models.ManyToManyField(
        "procurement.MaterialRequisition", related_name="rfq_links", blank=True
    )
    rfq_category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True
    )
    rfq_title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    submission_deadline = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default="Normal")
    items = models.ManyToManyField("inventory.Item", related_name="rfqs", blank=True)
    invited_vendors = models.ManyToManyField(
        "vendorportal.VendorProfile", related_name="rfqs", blank=True, through="RFQVendorInvitation"
    )
    required_documents = models.JSONField(default=list, blank=True)
    published_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    payment_terms = models.CharField(max_length=5000, null=True, blank=True)
    incoterm = models.CharField(max_length=50, null=True, blank=True)
    tax_terms = models.TextField(null=True, blank=True)
    delivery_commitment_days = models.PositiveIntegerField(null=True, blank=True)
    rfq_attachments = models.ManyToManyField(RFQAttachment, related_name="rfq_attachments", blank=True)
    vendors_count = models.PositiveIntegerField(default=0)
    responses_received = models.PositiveIntegerField(default=0)
    total_estimated_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=0
    )

    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_rfqs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def items_count(self):
        return self.line_items.count()

    def sync_inventory_items(self):
        inventory_item_ids = self.line_items.exclude(item_id__isnull=True).values_list(
            "item_id", flat=True
        )
        self.items.set(inventory_item_ids)

    def sync_total_estimated_value(self):
        total = Decimal("0")
        for line in self.line_items.all():
            unit_price = line.estimated_unit_price or Decimal("0")
            total += Decimal(str(line.quantity or 0)) * Decimal(str(unit_price))

        RFQ.objects.filter(pk=self.pk).update(total_estimated_value=total)

    def sync_vendors_count(self):
        RFQ.objects.filter(pk=self.pk).update(
            vendors_count=self.invited_vendors.count()
        )

    def sync_aggregates(self):
        self.sync_inventory_items()
        self.sync_total_estimated_value()
        self.sync_vendors_count()

    def save(self, *args, **kwargs):
        if not self.rfq_number:
            current_year = timezone.now().year

            # Get last RFQ of current year
            with transaction.atomic():
                last_rfq = (
                    RFQ.objects.select_for_update()
                    .filter(rfq_number__startswith=f"RFQ-{current_year}")
                    .order_by("-id")
                    .first()
                )

            if last_rfq:
                try:
                    last_number = int(last_rfq.rfq_number.split("-")[-1])
                except (IndexError, ValueError):
                    last_number = 0
            else:
                last_number = 0

            new_number = last_number + 1

            self.rfq_number = f"RFQ-{current_year}-{new_number:03d}"

        if self.status and self.status.lower() in {"published", "open", "awarded"} and not self.published_at:
            self.published_at = timezone.now()

        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.rfq_number} - {self.rfq_title}"


class RFQLineItem(models.Model):
    rfq = models.ForeignKey(
        "procurement.RFQ", on_delete=models.CASCADE, related_name="line_items"
    )
    requisition = models.ForeignKey(
        "procurement.MaterialRequisition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rfq_line_items",
    )
    source_material_item = models.ForeignKey(
        "procurement.MaterialItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rfq_line_items",
    )
    item = models.ForeignKey(
        "inventory.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rfq_line_items",
    )
    item_name = models.CharField(max_length=255)
    specification = models.TextField(null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit = models.CharField(max_length=100, null=True, blank=True)
    estimated_unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    @property
    def estimated_total(self):
        return Decimal(str(self.quantity or 0)) * Decimal(
            str(self.estimated_unit_price or Decimal("0"))
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.rfq_id:
            self.rfq.sync_aggregates()

    def delete(self, *args, **kwargs):
        rfq = self.rfq
        super().delete(*args, **kwargs)
        if rfq:
            rfq.sync_aggregates()

    def __str__(self):
        return f"{self.rfq} - {self.item_name}"


