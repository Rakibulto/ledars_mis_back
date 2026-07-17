from django.db import models


class TaxGroup(models.Model):
    """Tax group categorization (Odoo-style)."""

    name = models.CharField(max_length=100, unique=True)
    country = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Tax(models.Model):
    """Tax definitions (VAT, SD, WHT, etc.) — Odoo-style."""

    TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("fixed", "Fixed Amount"),
    ]
    SCOPE_CHOICES = [
        ("sales", "Sales"),
        ("purchase", "Purchase"),
        ("both", "Both"),
    ]
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    tax_group = models.ForeignKey(
        TaxGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="taxes"
    )
    tax_type = models.CharField(
        max_length=15, choices=TYPE_CHOICES, default="percentage"
    )
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default="both")
    rate = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    fixed_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    is_inclusive = models.BooleanField(default=False)
    account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tax_accounts",
    )
    refund_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tax_refund_accounts",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Taxes"

    def __str__(self):
        return f"{self.code} - {self.name} ({self.rate}%)"


class TaxRule(models.Model):
    """Automatic tax application rules."""

    name = models.CharField(max_length=200)
    tax = models.ForeignKey(Tax, on_delete=models.CASCADE, related_name="rules")
    partner_type = models.CharField(
        max_length=20,
        blank=True,
        choices=[("customer", "Customer"), ("vendor", "Vendor")],
    )
    account = models.ForeignKey(
        "accounting.Account", on_delete=models.SET_NULL, null=True, blank=True
    )
    min_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    max_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class WithholdingTax(models.Model):
    """Withholding tax / TDS configuration."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    rate = models.DecimalField(max_digits=8, decimal_places=4)
    threshold_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wht_accounts",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name} ({self.rate}%)"
