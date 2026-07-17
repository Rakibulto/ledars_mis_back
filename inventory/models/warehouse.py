from django.db import models
from .core import Category
from .product import Product


class Warehouse(models.Model):
    TYPE_CHOICES = (
        ("Central", "Central Warehouse"),
        ("Regional", "Regional Warehouse"),
        ("Field", "Field Warehouse"),
        ("Transit", "Transit Hub"),
    )

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField(null=True, blank=True)
    manager = models.CharField(max_length=150, null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    warehouse_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default="Central"
    )
    capacity_sqft = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class StorageLocation(models.Model):
    TYPE_CHOICES = (
        ("view", "View"),
        ("internal", "Internal Location"),
        ("supplier", "Supplier Location"),
        ("customer", "Customer Location"),
        ("production", "Production"),
        ("transit", "Transit Location"),
        ("scrap", "Scrap"),
    )

    name = models.CharField(max_length=200)
    # Unified location: points to an OfficeManagement record whose type is
    # either 'office' or 'warehouse'.
    office = models.ForeignKey(
        "procurement.OfficeManagement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storage_locations",
    )
    location_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default="internal"
    )
    barcode = models.CharField(max_length=100, null=True, blank=True)
    is_scrap = models.BooleanField(default=False)
    is_return = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        prefix = self.office.code if self.office else "NO-OFFICE"
        return f"{prefix}/{self.name}"


class PutawayRule(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="putaway_rules",
    )
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, null=True, blank=True
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    location = models.ForeignKey(StorageLocation, on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sequence"]

    def __str__(self):
        target = self.product or self.category
        return f"{target} → {self.location}"


class RemovalStrategy(models.Model):
    STRATEGY_CHOICES = (
        ("fifo", "First In, First Out (FIFO)"),
        ("lifo", "Last In, First Out (LIFO)"),
        ("fefo", "First Expiry, First Out (FEFO)"),
        ("closest", "Closest Location"),
    )

    name = models.CharField(max_length=100)
    strategy = models.CharField(max_length=10, choices=STRATEGY_CHOICES, default="fifo")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="removal_strategies"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Removal Strategies"

    def __str__(self):
        return f"{self.name} ({self.get_strategy_display()})"


class OperationType(models.Model):
    TYPE_CHOICES = (
        ("incoming", "Receipts"),
        ("outgoing", "Delivery Orders"),
        ("internal", "Internal Transfers"),
        ("returns", "Returns"),
        ("scrap", "Scrap"),
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    operation_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="operation_types"
    )
    default_source = models.ForeignKey(
        StorageLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    default_destination = models.ForeignKey(
        StorageLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Route(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(null=True, blank=True)
    steps = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ShippingMethod(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    carrier = models.CharField(max_length=100, null=True, blank=True)
    cost_per_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_days = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
