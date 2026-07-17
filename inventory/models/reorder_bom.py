from django.db import models
from .product import Product
from .warehouse import Warehouse


class ReorderRule(models.Model):
    TRIGGER_CHOICES = (
        ("automatic", "Automatic"),
        ("manual", "Manual"),
    )

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reorder_rules"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True
    )
    min_qty = models.DecimalField(max_digits=12, decimal_places=2)
    max_qty = models.DecimalField(max_digits=12, decimal_places=2)
    reorder_qty = models.DecimalField(max_digits=12, decimal_places=2)
    lead_time_days = models.PositiveIntegerField(default=7)
    trigger = models.CharField(
        max_length=20, choices=TRIGGER_CHOICES, default="automatic"
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product.name} - min:{self.min_qty} max:{self.max_qty}"


class KittingBOM(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="boms")
    description = models.TextField(null=True, blank=True)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    assembly_time_minutes = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Kitting / BOM"
        verbose_name_plural = "Kitting / BOMs"

    def __str__(self):
        return f"{self.name} ({self.code})"


class KittingBOMLine(models.Model):
    bom = models.ForeignKey(
        KittingBOM, on_delete=models.CASCADE, related_name="components"
    )
    component = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.component.name} x {self.quantity}"
