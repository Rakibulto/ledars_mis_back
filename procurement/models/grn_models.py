from django.db import models, transaction
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.utils import timezone


class GRNSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class GoodsReceiptNote(models.Model):
    """Record of goods received against a work order/purchase order."""

    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Pending Verification", "Pending Verification"),
        ("Partially Verified", "Partially Verified"),
        ("Verified", "Verified"),
        ("Rejected", "Rejected"),
    ]

    grn_number = models.CharField(max_length=50, unique=True, blank=True)
    work_order = models.ForeignKey(
        "procurement.WorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grn_records",
    )
    purchase_order = models.ForeignKey(
        "procurement.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grn_records",
    )
    direct_purchase = models.ForeignKey(
        "procurement.DirectPurchase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grn_records",
    )
    supplier = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grn_records",
    )
    # Direct evaluation fallback — used when supplier FK is null (bypassed-pipeline GRN)
    direct_vendor_name = models.CharField(max_length=255, null=True, blank=True)
    direct_vendor_email = models.EmailField(null=True, blank=True)
    direct_vendor_phone = models.CharField(max_length=50, null=True, blank=True)
    direct_vendor_address = models.TextField(null=True, blank=True)
    receipt_date = models.DateField(null=True, blank=True)
    delivery_note_number = models.CharField(max_length=100, null=True, blank=True)
    invoice_number = models.CharField(max_length=100, null=True, blank=True)
    invoice_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_received_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=0
    )
    remarks = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="Draft")

    received_by = models.ForeignKey(
        "employee.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_grns",
    )
    receive_location = models.ForeignKey(
        "procurement.OfficeManagement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_grns",
    )
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_grns",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def calculate_total_received(self):
        total = (
            self.grn_items.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("received_quantity") * F("unit_price"),
                        output_field=DecimalField(max_digits=15, decimal_places=2),
                    )
                )
            )["total"]
            or 0
        )
        self.total_received_value = total
        self.save(update_fields=["total_received_value"])

    def save(self, *args, **kwargs):
        if not self.grn_number:
            current_year = timezone.now().year
            with transaction.atomic():
                sequence, _ = GRNSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])
                self.grn_number = f"GRN-{current_year}-{sequence.last_number:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.grn_number}"


class GRNItem(models.Model):
    """Individual item received in a GRN."""

    CONDITION_CHOICES = [
        ("Good", "Good"),
        ("Damaged", "Damaged"),
        ("Partial", "Partial"),
    ]

    grn = models.ForeignKey(
        GoodsReceiptNote, on_delete=models.CASCADE, related_name="grn_items"
    )
    item = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True)
    ordered_quantity = models.PositiveIntegerField(default=0)
    received_quantity = models.PositiveIntegerField(default=0)
    accepted_quantity = models.PositiveIntegerField(default=0)
    rejected_quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    batch_number = models.CharField(max_length=100, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    condition = models.CharField(
        max_length=20, choices=CONDITION_CHOICES, default="Good"
    )
    remarks = models.TextField(null=True, blank=True)

    @property
    def total_value(self):
        return self.received_quantity * self.unit_price

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.grn:
            self.grn.calculate_total_received()

    def delete(self, *args, **kwargs):
        grn = self.grn
        super().delete(*args, **kwargs)
        if grn:
            grn.calculate_total_received()

    def __str__(self):
        return f"{self.grn.grn_number} - {self.item}"


class GRNVerification(models.Model):
    """Quality verification record for items received."""

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Passed", "Passed"),
        ("Failed", "Failed"),
        ("Conditional", "Conditional"),
    ]

    grn = models.ForeignKey(
        GoodsReceiptNote, on_delete=models.CASCADE, related_name="verifications"
    )
    grn_item = models.ForeignKey(
        GRNItem, on_delete=models.CASCADE, related_name="verifications"
    )
    inspection_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    findings = models.TextField(null=True, blank=True)

    verified_by = models.ForeignKey(
        "employee.Employee", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Verify - {self.grn.grn_number} - {self.status}"
