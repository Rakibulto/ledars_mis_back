from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

# ── Currency & Exchange Rate ──────────────────────────────────────────────────


class Currency(models.Model):
    """Currencies supported by the procurement module."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    code = models.CharField(max_length=10, unique=True)  # BDT, USD, EUR …
    name = models.CharField(max_length=100)  # Bangladeshi Taka
    symbol = models.CharField(max_length=10)  # ৳, $, €
    is_base = models.BooleanField(default=False)  # Only one base allowed
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    notes = models.TextField(null=True, blank=True)

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_base", "code"]
        verbose_name_plural = "Currencies"

    def clean(self):
        if self.is_base:
            existing = Currency.objects.filter(is_base=True).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError("Only one base currency is allowed.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def latest_rate(self):
        """Return the most recent ExchangeRate for this currency (or None for base)."""
        if self.is_base:
            return None
        return self.exchange_rates.order_by("-effective_date").first()

    def __str__(self):
        return f"{self.code} – {self.name}"


class ExchangeRate(models.Model):
    """Historical snapshot: 1 unit of `currency` = `rate` units of the base currency."""

    currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name="exchange_rates",
        limit_choices_to={"is_base": False},
    )
    # Rate: 1 FCY = X BDT  (or whatever base currency)
    rate = models.DecimalField(max_digits=18, decimal_places=6)
    effective_date = models.DateField(default=timezone.now)
    source = models.CharField(
        max_length=100, null=True, blank=True
    )  # "manual", "CBR", …
    notes = models.TextField(null=True, blank=True)

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date", "currency__code"]
        unique_together = [["currency", "effective_date"]]
        verbose_name = "Exchange Rate"
        verbose_name_plural = "Exchange Rates"

    def clean(self):
        if self.rate is not None and self.rate <= 0:
            raise ValidationError({"rate": "Exchange rate must be a positive number."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def currency_code(self):
        return self.currency.code

    @property
    def inverse_rate(self):
        """1 BDT = X FCY"""
        if self.rate:
            return round(1 / float(self.rate), 6)
        return None

    def __str__(self):
        return f"{self.currency.code} @ {self.rate} ({self.effective_date})"


# ─────────────────────────────────────────────────────────────────────────────


class ApprovalMatrix(models.Model):
    """Configurable approval workflow matrix for procurement, inventory, and other modules."""

    MODULE_CHOICES = [
        ("Material Requisition", "Material Requisition"),
        ("Purchase Requisition", "Purchase Requisition"),
        ("RFQ", "RFQ"),
        ("Comparative Statement", "Comparative Statement"),
        ("Award", "Award"),
        ("Work Order", "Work Order"),
        ("Payment Requisition", "Payment Requisition"),
        ("GRN", "GRN"),
        # Inventory modules
        ("good_receipt_note", "Good Receipt Note"),
        ("good_issue_note", "Good Issue Note"),
        ("internal_transfers", "Internal Transfers"),
        ("stock_adjustment", "Stock Adjustment"),
        ("scrap_management", "Scrap Management"),
    ]

    TYPE_CHOICES = [
        ("procurement", "Procurement"),
        ("inventory", "Inventory"),
        ("beneficiary", "Beneficiary"),
    ]

    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="procurement",
        help_text="Module type this approval rule belongs to.",
    )

    module = models.CharField(max_length=50, choices=MODULE_CHOICES)
    approval_level = models.PositiveIntegerField(default=1)
    min_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    max_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    approver_role = models.CharField(max_length=100, null=True, blank=True)
    approver = models.ForeignKey(
        "employee.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_matrix_entries",
    )
    approvers = models.ManyToManyField(
        "employee.Employee",
        blank=True,
        related_name="approval_matrix_entries_m2m",
    )
    department = models.ForeignKey(
        "employee.Department", on_delete=models.SET_NULL, null=True, blank=True
    )
    APPROVAL_MODE_CHOICES = [
        (
            "any_approver",
            "Independent Approval",
        ),  # any single approver's action finalises the level
        (
            "all_approvers",
            "Unanimous Approval",
        ),  # every assigned approver must approve before advancing
    ]

    approval_mode = models.CharField(
        max_length=20,
        choices=APPROVAL_MODE_CHOICES,
        default="all_approvers",
        help_text=(
            "Independent Approval: the first approver to act (approve or reject) "
            "immediately finalises this level. "
            "Unanimous Approval: all approvers must approve before the level advances."
        ),
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["module", "approval_level"]
        verbose_name_plural = "Approval Matrix"

    def __str__(self):
        return f"{self.module} - Level {self.approval_level}"


class EmailTemplate(models.Model):
    """Email templates for procurement communications."""

    MODULE_CHOICES = [
        ("Requisition", "Requisition"),
        ("RFQ", "RFQ"),
        ("Award", "Award"),
        ("Work Order", "Work Order"),
        ("Payment", "Payment"),
        ("Vendor", "Vendor"),
        ("GRN", "GRN"),
        ("General", "General"),
    ]

    name = models.CharField(max_length=255, unique=True)
    module = models.CharField(max_length=20, choices=MODULE_CHOICES)
    subject = models.CharField(max_length=500)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    variables = models.JSONField(
        default=list,
        blank=True,
        help_text='Available template variables, e.g. ["vendor_name", "po_number"]',
    )

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["module", "name"]

    def __str__(self):
        return f"{self.module} - {self.name}"


class ProcurementRole(models.Model):
    """Custom roles and permissions within procurement module."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)

    can_create_requisition = models.BooleanField(default=False)
    can_approve_requisition = models.BooleanField(default=False)
    can_create_rfq = models.BooleanField(default=False)
    can_manage_vendors = models.BooleanField(default=False)
    can_create_comparative = models.BooleanField(default=False)
    can_approve_comparative = models.BooleanField(default=False)
    can_create_award = models.BooleanField(default=False)
    can_create_work_order = models.BooleanField(default=False)
    can_approve_work_order = models.BooleanField(default=False)
    can_create_grn = models.BooleanField(default=False)
    can_create_payment = models.BooleanField(default=False)
    can_approve_payment = models.BooleanField(default=False)
    can_process_treasury = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    can_manage_settings = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProcurementUserRole(models.Model):
    """Assign procurement-specific roles to users."""

    user = models.ForeignKey(
        "authentication.User",
        on_delete=models.CASCADE,
        related_name="procurement_roles",
    )
    role = models.ForeignKey(
        ProcurementRole, on_delete=models.CASCADE, related_name="user_assignments"
    )

    class Meta:
        unique_together = ["user", "role"]

    def __str__(self):
        return f"{self.user} - {self.role}"


class NotificationSetting(models.Model):
    """Notification preferences per module."""

    MODULE_CHOICES = [
        ("Requisition", "Requisition"),
        ("RFQ", "RFQ"),
        ("Quotation", "Quotation"),
        ("Comparative", "Comparative"),
        ("Award", "Award"),
        ("Work Order", "Work Order"),
        ("GRN", "GRN"),
        ("Payment", "Payment"),
        ("Treasury", "Treasury"),
    ]

    module = models.CharField(max_length=20, choices=MODULE_CHOICES)
    event_name = models.CharField(max_length=100)
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["module", "event_name"]
        unique_together = ["module", "event_name"]

    def __str__(self):
        return f"{self.module} - {self.event_name}"


class UserManagement(models.Model):
    """Extended user profile managed through procurement module."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("suspended", "Suspended"),
    ]

    user = models.OneToOneField(
        "authentication.User",
        on_delete=models.CASCADE,
        related_name="user_management_profile",
        null=True,
        blank=True,
    )

    # Cached auth fields for reference
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)

    # Extended profile fields
    name = models.CharField(max_length=255, blank=True, null=True)
    role = models.ForeignKey(
        "authentication.Role", on_delete=models.SET_NULL, blank=True, null=True
    )
    department = models.ForeignKey(
        "employee.Department", on_delete=models.SET_NULL, blank=True, null=True
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "User Management"
        verbose_name_plural = "User Management"

    def __str__(self):
        return self.username
