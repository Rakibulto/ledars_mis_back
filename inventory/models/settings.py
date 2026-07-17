from django.db import models
from .warehouse import Warehouse


class InventorySettings(models.Model):
    company_name = models.CharField(max_length=200, default="LEDARS")
    default_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True
    )
    default_valuation_method = models.CharField(max_length=20, default="average")
    enable_lot_tracking = models.BooleanField(default=True)
    enable_expiry_tracking = models.BooleanField(default=True)
    enable_quality_control = models.BooleanField(default=True)
    enable_barcode = models.BooleanField(default=True)
    low_stock_threshold = models.PositiveIntegerField(default=10)
    auto_reorder = models.BooleanField(default=False)
    fiscal_year_start = models.PositiveIntegerField(default=7)

    class Meta:
        verbose_name_plural = "Inventory Settings"

    def __str__(self):
        return f"Settings - {self.company_name}"
