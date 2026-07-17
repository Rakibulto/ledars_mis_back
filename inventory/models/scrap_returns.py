from django.db import models
from authentication.models import User
from .product import Product
from .warehouse import Warehouse


class ScrapRecord(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True
    )
    office_location = models.ForeignKey(
        "procurement.OfficeManagement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scrap_records",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    disposal_method = models.CharField(max_length=100, null=True, blank=True)
    disposal_date = models.DateField(null=True, blank=True)
    certificate_number = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, default="pending")
    scrapped_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    approval_level = models.PositiveIntegerField(default=0)
    approval_log = models.JSONField(default=list, blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scrap_approvals",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference


class ReturnRecord(models.Model):
    TYPE_CHOICES = (
        ("customer", "Customer Return"),
        ("supplier", "Supplier Return"),
    )

    reference = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    return_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(null=True, blank=True)
    condition = models.CharField(max_length=50, default="good")
    original_reference = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, default="draft")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference