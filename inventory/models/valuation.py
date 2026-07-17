from django.db import models
from .product import Product
from .warehouse import Warehouse
from .operations import GRN


class InventoryValuation(models.Model):
    METHOD_CHOICES = (
        ("fifo", "FIFO"),
        ("average", "Average Cost"),
        ("standard", "Standard Cost"),
    )

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="valuations"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True
    )
    on_hand = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="average")
    last_updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.total_value = self.on_hand * self.unit_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.total_value}"


class LandedCost(models.Model):
    SPLIT_CHOICES = (
        ("by_value", "By Value"),
        ("by_quantity", "By Quantity"),
        ("equal", "Equal Split"),
    )

    reference = models.CharField(max_length=50, unique=True)
    grn = models.ForeignKey(GRN, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    freight_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    customs_duty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    insurance_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    handling_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_landed_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    split_method = models.CharField(
        max_length=15, choices=SPLIT_CHOICES, default="by_value"
    )
    status = models.CharField(max_length=20, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.total_landed_cost = (
            self.freight_cost
            + self.customs_duty
            + self.insurance_cost
            + self.handling_cost
            + self.other_cost
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.reference
