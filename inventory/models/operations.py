from django.db import transaction
from django.utils import timezone
from django.db import models
from authentication.models import User
from .product import Product
from .warehouse import Warehouse


# ─────────────────────────────────────────────────────────────
#  GRN (Goods Receipt Note)
# ─────────────────────────────────────────────────────────────
class GRNSequence(models.Model):
    year = models.IntegerField(unique=True, null=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class GRN(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Pending Quality Check", "Pending Quality Check"),
        ("Pending Approval", "Pending Approval"),
        ("Approved", "Approved"),
        ("Verified", "Verified"),
        ("Posted to Stock", "Posted to Stock"),
    ]

    grn_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    po_number = models.ForeignKey(
        "procurement.PurchaseOrder", on_delete=models.SET_NULL, null=True, blank=True
    )
    supplier = models.ForeignKey(
        "vendorportal.VendorProfile", on_delete=models.SET_NULL, null=True, blank=True
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True
    )
    receive_date = models.DateField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Draft")
    received_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    challan_number = models.CharField(max_length=100, blank=True, null=True)
    vehicle_number = models.CharField(max_length=100, blank=True, null=True)
    approval_level = models.PositiveIntegerField(default=0)
    total_levels = models.PositiveIntegerField(default=1)
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.grn_number:
            current_year = timezone.now().year
            with transaction.atomic():
                sequence, _ = GRNSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])
                self.grn_number = f"GRN-{current_year}-{sequence.last_number:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.grn_number


class GRNLineItem(models.Model):
    grn = models.ForeignKey(GRN, related_name="line_items", on_delete=models.CASCADE)
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    item_code = models.CharField(max_length=100, blank=True, null=True)
    item_name = models.CharField(max_length=255, blank=True, null=True)
    ordered_qty = models.FloatField(blank=True, null=True)
    received_qty = models.FloatField(blank=True, null=True)
    accepted_qty = models.FloatField(blank=True, null=True)
    rejected_qty = models.FloatField(blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    batch_number = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.item_name} ({self.grn.grn_number})"


# ─────────────────────────────────────────────────────────────
#  GIN (Goods Issue Note)
# ─────────────────────────────────────────────────────────────
class GINSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)


class GIN(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Pending Approval", "Pending Approval"),
        ("Approved", "Approved"),
        ("Issued", "Issued"),
        ("Cancelled", "Cancelled"),
    ]

    gin_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    issue_date = models.DateField()
    issued_to = models.CharField(max_length=200, null=True, blank=True)
    issue_from = models.CharField(max_length=200, null=True, blank=True)
    department = models.CharField(max_length=200, null=True, blank=True)
    project = models.CharField(max_length=200, null=True, blank=True)
    project_fk = models.ForeignKey(
        "project_managements.ProjectManagementProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gin_project_issues",
    )
    purpose = models.TextField(null=True, blank=True)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True
    )
    office_location = models.ForeignKey(
        "procurement.OfficeManagement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gin_issues",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gin_requests",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gin_approvals",
    )
    issued_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gin_issues",
    )
    approval_level = models.PositiveIntegerField(default=0)
    total_levels = models.PositiveIntegerField(default=2)
    approval_log = models.JSONField(default=list, blank=True)

    # Transport / dispatch details (filled when marking as Issued)
    transport_person = models.CharField(max_length=200, blank=True, null=True)
    transport_phone = models.CharField(max_length=50, blank=True, null=True)
    transport_address = models.TextField(blank=True, null=True)
    vehicle_number = models.CharField(max_length=100, blank=True, null=True)
    dispatch_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.gin_number:
            current_year = timezone.now().year
            with transaction.atomic():
                seq, _ = GINSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                seq.last_number += 1
                seq.save(update_fields=["last_number"])
                self.gin_number = f"GIN-{current_year}-{seq.last_number:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.gin_number


class GINLineItem(models.Model):
    gin = models.ForeignKey(GIN, related_name="line_items", on_delete=models.CASCADE)
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    item_code = models.CharField(max_length=100)
    item_name = models.CharField(max_length=255)
    requested_qty = models.FloatField()
    issued_qty = models.FloatField()
    unit = models.CharField(max_length=50)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.item_name} ({self.gin.gin_number})"


# ─────────────────────────────────────────────────────────────
#  STOCK TRANSFER
# ─────────────────────────────────────────────────────────────
class StockTransferSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)


class StockTransfer(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("In Transit", "In Transit"),
        ("Received", "Received"),
        ("Cancelled", "Cancelled"),
    ]

    transfer_number = models.CharField(
        max_length=50, unique=True, null=True, blank=True
    )
    transfer_date = models.DateField()
    from_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outgoing_transfers",
    )
    to_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_transfers",
    )
    from_location = models.CharField(max_length=200, null=True, blank=True)
    to_location = models.CharField(max_length=200, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    sent_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_transfers",
    )
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_transfers",
    )
    vehicle_number = models.CharField(max_length=100, null=True, blank=True)
    driver_name = models.CharField(max_length=150, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.transfer_number:
            current_year = timezone.now().year
            with transaction.atomic():
                (
                    seq,
                    _,
                ) = StockTransferSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                seq.last_number += 1
                seq.save(update_fields=["last_number"])
                self.transfer_number = f"ST-{current_year}-{seq.last_number:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.transfer_number


class StockTransferLine(models.Model):
    transfer = models.ForeignKey(
        StockTransfer, related_name="lines", on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    item_code = models.CharField(max_length=100)
    item_name = models.CharField(max_length=255)
    quantity = models.FloatField()
    unit = models.CharField(max_length=50)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.item_name} x {self.quantity}"


# ─────────────────────────────────────────────────────────────
#  INTERNAL TRANSFER  (office / warehouse based, with real stock movement)
# ─────────────────────────────────────────────────────────────
class InternalTransferSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class InternalTransfer(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Pending Transit Approval", "Pending Transit Approval"),
        ("In Transit", "In Transit"),
        ("Back Transit", "Back Transit"),
        ("Received", "Received"),
        ("Back Received", "Back Received"),
        ("Cancelled", "Cancelled"),
    ]

    transfer_number = models.CharField(
        max_length=50, unique=True, null=True, blank=True
    )
    transfer_date = models.DateField()

    # Source and destination — point to OfficeManagement (type='office' or 'warehouse')
    from_office = models.ForeignKey(
        "procurement.OfficeManagement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outgoing_internal_transfers",
    )
    to_office = models.ForeignKey(
        "procurement.OfficeManagement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_internal_transfers",
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Draft")
    notes = models.TextField(null=True, blank=True)

    # Transport / dispatch details (filled when dispatching to In Transit)
    transport_person = models.CharField(max_length=200, blank=True, null=True)
    transport_phone = models.CharField(max_length=50, blank=True, null=True)
    transport_address = models.TextField(blank=True, null=True)
    vehicle_number = models.CharField(max_length=100, blank=True, null=True)
    dispatch_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_internal_transfers",
    )

    # Internal flags that guard against double stock movements
    stock_deducted = models.BooleanField(
        default=False,
        help_text="True once stock has been deducted from source products.",
    )
    stock_received = models.BooleanField(
        default=False,
        help_text="True once stock has been added to destination products.",
    )

    approval_level = models.PositiveIntegerField(default=0)
    status_log = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.transfer_number:
            current_year = timezone.now().year
            with transaction.atomic():
                seq, _ = InternalTransferSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                seq.last_number += 1
                seq.save(update_fields=["last_number"])
                self.transfer_number = f"IT-{current_year}-{seq.last_number:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.transfer_number or f"InternalTransfer-{self.pk}"


class InternalTransferLine(models.Model):
    transfer = models.ForeignKey(
        InternalTransfer, related_name="lines", on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="internal_transfer_lines",
        help_text="The source Product record (must belong to from_office).",
    )
    # Snapshot fields so the line remains readable even if the product changes
    product_name = models.CharField(max_length=255, blank=True)
    product_code = models.CharField(max_length=50, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit = models.CharField(max_length=50, blank=True)
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Snapshot of product cost at the time of transfer."
    )
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.product_name or 'Item'} × {self.quantity}"


# ─────────────────────────────────────────────────────────────
#  STOCK ADJUSTMENT
# ─────────────────────────────────────────────────────────────
class StockAdjustmentSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)


class StockAdjustment(models.Model):
    TYPE_CHOICES = [
        ("stock_in", "Stock In"),
        ("stock_out", "Stock Out"),
        ("correction", "Correction"),
        ("return", "Return"),
    ]
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Pending Approval", "Pending Approval"),
        ("Approved", "Approved"),
        ("Posted", "Posted"),
        ("Cancelled", "Cancelled"),
        ("Declined", "Declined"),
    ]

    adjustment_number = models.CharField(
        max_length=50, unique=True, null=True, blank=True
    )
    adjustment_date = models.DateField()
    adjustment_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True
    )
    office_location = models.ForeignKey(
        "procurement.OfficeManagement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_adjustments",
    )
    location = models.CharField(max_length=200, null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    adjusted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_adjustments",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_adjustments",
    )
    approval_level = models.PositiveIntegerField(default=0)
    approval_log = models.JSONField(default=list, blank=True)
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.adjustment_number:
            current_year = timezone.now().year
            with transaction.atomic():
                (
                    seq,
                    _,
                ) = StockAdjustmentSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                seq.last_number += 1
                seq.save(update_fields=["last_number"])
                self.adjustment_number = f"ADJ-{current_year}-{seq.last_number:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.adjustment_number


class StockAdjustmentLine(models.Model):
    adjustment = models.ForeignKey(
        StockAdjustment, related_name="lines", on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    item_code = models.CharField(max_length=100)
    item_name = models.CharField(max_length=255)
    system_qty = models.FloatField(default=0)
    counted_qty = models.FloatField(default=0)
    difference = models.FloatField(default=0)
    unit = models.CharField(max_length=50)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.item_name} diff={self.difference}"


# ─────────────────────────────────────────────────────────────
#  CYCLE COUNTING
# ─────────────────────────────────────────────────────────────
class CycleCountSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)


class CycleCount(models.Model):
    STATUS_CHOICES = [
        ("Scheduled", "Scheduled"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Reviewed", "Reviewed"),
        ("Cancelled", "Cancelled"),
    ]

    count_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True
    )
    count_type = models.CharField(max_length=120)
    scheduled_date = models.DateField()
    scope = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Scheduled"
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cycle_count_sessions",
    )
    reviewer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_cycle_counts",
    )
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.count_number:
            current_year = timezone.now().year
            with transaction.atomic():
                seq, _ = CycleCountSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                seq.last_number += 1
                seq.save(update_fields=["last_number"])
                self.count_number = f"CC-{current_year}-{seq.last_number:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.count_number or "Cycle Count"


class CycleCountLine(models.Model):
    cycle_count = models.ForeignKey(
        CycleCount, related_name="lines", on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    item_code = models.CharField(max_length=100)
    item_name = models.CharField(max_length=255)
    location = models.CharField(max_length=150, null=True, blank=True)
    system_qty = models.FloatField(default=0)
    counted_qty = models.FloatField(null=True, blank=True)
    variance = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True, default="")
    notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.counted_qty is None:
            self.variance = None
        else:
            self.variance = float(self.counted_qty or 0) - float(self.system_qty or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_name} ({self.cycle_count.count_number})"


# ─────────────────────────────────────────────────────────────
#  LOT & SERIAL TRACKING
# ─────────────────────────────────────────────────────────────
class LotSerial(models.Model):
    TYPE_CHOICES = (
        ("lot", "Lot"),
        ("serial", "Serial Number"),
    )

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="lot_serials"
    )
    number = models.CharField(max_length=100)
    lot_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="lot")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=20, default="active")
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["product", "number"]

    def __str__(self):
        return f"{self.product.code} - {self.number}"


# ─────────────────────────────────────────────────────────────
#  STOCK MOVES (audit trail)
# ─────────────────────────────────────────────────────────────
class StockMove(models.Model):
    TYPE_CHOICES = (
        ("Receipt", "Receipt"),
        ("Delivery", "Delivery"),
        ("Transfer", "Transfer"),
        ("Return", "Return"),
        ("Scrap", "Scrap"),
        ("Adjustment", "Adjustment"),
        ("Status Change", "Status Change"),
    )

    date = models.DateTimeField()
    reference = models.CharField(max_length=100)
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    source_location = models.CharField(max_length=200)
    destination_location = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    uom = models.CharField(max_length=50, null=True, blank=True)
    move_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    done_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    from_status = models.CharField(max_length=50, null=True, blank=True)
    to_status = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        audit_subject = self.product or self.to_status or "Audit entry"
        return f"{self.reference} - {audit_subject} x {self.quantity}"