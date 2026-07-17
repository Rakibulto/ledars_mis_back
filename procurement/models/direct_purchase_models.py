from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from procurement.models.office_models import OfficeManagement


class Shop(models.Model):
    """Simple shop / seller model for Direct Purchases."""

    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Shop / Seller"
        verbose_name_plural = "Shops / Sellers"

    def __str__(self):
        return self.name


class DPSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class DirectPurchase(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        # ("Pending Approval", "Pending Approval"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("Converted to GRN", "Converted to GRN"),
    ]

    PRIORITY_CHOICES = [
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
        ("Urgent", "Urgent"),
    ]

    PAYMENT_TERMS_CHOICES = [
        ("Immediate", "Immediate"),
        ("Net 15", "Net 15"),
        ("Net 30", "Net 30"),
        ("Net 45", "Net 45"),
        ("Net 60", "Net 60"),
        ("On Delivery", "On Delivery"),
    ]

    # ── Auto-generated number ──────────────────────────────────────────────
    dp_number = models.CharField(max_length=50, unique=True, null=True, blank=True)

    # ── Section 1 – Basic Information ─────────────────────────────────────
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_purchases",
    )
    project = models.ForeignKey(
        "project_managements.ProjectManagementProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_purchases",
    )
    category = models.ForeignKey(
        "inventory.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_purchases",
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="Medium", null=True, blank=True
    )
    fiscal_year = models.CharField(max_length=50, null=True, blank=True)
    purpose = models.TextField(null=True, blank=True)

    # ── Section 2 – Shop / Budget ──────────────────────────────────────────
    shop = models.ForeignKey(
        "procurement.Shop",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_purchases",
    )
    reference_number = models.CharField(max_length=100, null=True, blank=True)
    budget_code = models.ForeignKey(
        "procurement.Budget",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_purchases",
    )
    account_code = models.ForeignKey(
        "procurement.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_purchases",
    )

    # ── Section 3 – BOQ (handled via DirectPurchaseItem) ──────────────────
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # ── Section 4 – Specifications & Details ──────────────────────────────
    specifications = models.TextField(null=True, blank=True)
    preferred_brand = models.CharField(max_length=255, null=True, blank=True)
    alternative_brands = models.CharField(max_length=255, null=True, blank=True)
    warranty_period = models.CharField(max_length=100, null=True, blank=True)
    country_of_origin = models.CharField(max_length=100, null=True, blank=True)
    quality_standards = models.TextField(null=True, blank=True)

    # ── Section 5 – Delivery & Contact ────────────────────────────────────
    requesting_office = models.ForeignKey(
        OfficeManagement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requesting_direct_purchases",
    )
    delivery_location = models.ForeignKey(
        OfficeManagement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_direct_purchases",
    )
    purchase_date = models.DateField(null=True, blank=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    payment_terms = models.CharField(
        max_length=50, choices=PAYMENT_TERMS_CHOICES, null=True, blank=True
    )
    contact_person = models.CharField(max_length=100, null=True, blank=True)
    contact_phone = models.CharField(max_length=50, null=True, blank=True)
    special_instruction = models.TextField(null=True, blank=True)
    justification = models.TextField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)

    # ── Status & Workflow ──────────────────────────────────────────────────
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="Draft", null=True, blank=True
    )
    attachment = models.FileField(
        upload_to="direct_purchases/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf", "doc", "docx", "xls", "xlsx",
                    "jpg", "jpeg", "png", "svg", "gif", "webp",
                ]
            )
        ],
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_direct_purchases",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Direct Purchase"
        verbose_name_plural = "Direct Purchases"

    def __str__(self):
        return self.dp_number or f"DP-{self.pk}"

    def save(self, *args, **kwargs):
        if not self.dp_number:
            self.dp_number = self._generate_dp_number()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_dp_number(cls):
        year = timezone.now().year
        seq, _ = DPSequence.objects.get_or_create(year=year)
        seq.last_number += 1
        seq.save(update_fields=["last_number"])
        return f"DP-{year}-{seq.last_number:03d}"

    def recalculate_total(self):
        total = sum(
            (item.quantity or 0) * (item.unit_price or 0)
            for item in self.dp_items.all()
        )
        self.total_amount = total
        self.save(update_fields=["total_amount"])


class DirectPurchaseItem(models.Model):
    direct_purchase = models.ForeignKey(
        DirectPurchase,
        on_delete=models.CASCADE,
        related_name="dp_items",
    )
    item = models.ForeignKey(
        "inventory.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_purchase_items",
    )
    description = models.CharField(max_length=500)
    specification = models.TextField(null=True, blank=True)
    unit = models.CharField(max_length=50, default="Pcs")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    extended_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    remarks = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.direct_purchase} – {self.description}"

    def save(self, *args, **kwargs):
        self.extended_amount = (self.quantity or 0) * (self.unit_price or 0)
        super().save(*args, **kwargs)


class DirectPurchaseStatusLog(models.Model):
    direct_purchase = models.ForeignKey(
        DirectPurchase,
        on_delete=models.CASCADE,
        related_name="status_logs",
    )
    from_status = models.CharField(max_length=30, null=True, blank=True)
    to_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    comments = models.TextField(null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.direct_purchase} | {self.from_status} → {self.to_status}"
