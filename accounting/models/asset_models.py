from django.db import models


class AssetCategory(models.Model):
    """Asset categories with depreciation defaults (Odoo-style)."""

    DEPRECIATION_METHOD_CHOICES = [
        ("straight_line", "Straight Line"),
        ("declining_balance", "Declining Balance"),
        ("sum_of_years", "Sum of Years' Digits"),
        ("units_of_production", "Units of Production"),
    ]
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, blank=True)
    depreciation_method = models.CharField(
        max_length=25,
        choices=DEPRECIATION_METHOD_CHOICES,
        default="straight_line",
    )
    useful_life = models.IntegerField(default=60, help_text="In months")
    salvage_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    asset_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_category_asset",
    )
    depreciation_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_category_depreciation",
    )
    expense_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_category_expense",
    )
    journal = models.ForeignKey(
        "accounting.Journal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Asset Categories"

    def __str__(self):
        return self.name


class Asset(models.Model):
    """Fixed asset register (Odoo-style)."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("running", "Running"),
        ("fully_depreciated", "Fully Depreciated"),
        ("disposed", "Disposed"),
        ("closed", "Closed"),
    ]
    CONDITION_CHOICES = [
        ("new", "New"),
        ("good", "Good"),
        ("fair", "Fair"),
        ("poor", "Poor"),
        ("retired", "Retired"),
    ]
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True, blank=True)
    category = models.ForeignKey(
        AssetCategory,
        on_delete=models.PROTECT,
        related_name="assets",
    )
    purchase_date = models.DateField()
    purchase_cost = models.DecimalField(max_digits=18, decimal_places=2)
    salvage_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    current_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    depreciation_method = models.CharField(
        max_length=25,
        choices=AssetCategory.DEPRECIATION_METHOD_CHOICES,
        default="straight_line",
    )
    useful_life = models.IntegerField(default=60, help_text="In months")
    depreciation_start_date = models.DateField(null=True, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=255, blank=True)
    custodian = models.CharField(max_length=255, blank=True)
    condition = models.CharField(
        max_length=10, choices=CONDITION_CHOICES, default="good"
    )
    project_name = models.CharField(max_length=255, blank=True)
    schedule_revision = models.IntegerField(default=1)
    description = models.TextField(blank=True)
    vendor = models.ForeignKey(
        "accounting.Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    cost_center = models.ForeignKey(
        "accounting.CostCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-purchase_date"]

    def __str__(self):
        return f"{self.code} - {self.name}" if self.code else self.name


class AssetDepreciation(models.Model):
    """Depreciation schedule lines for an asset."""

    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("posted", "Posted"),
        ("skipped", "Skipped"),
    ]
    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="depreciation_lines"
    )
    date = models.DateField()
    period = models.IntegerField(help_text="Period number")
    depreciation_amount = models.DecimalField(max_digits=18, decimal_places=2)
    accumulated_depreciation = models.DecimalField(max_digits=18, decimal_places=2)
    remaining_value = models.DecimalField(max_digits=18, decimal_places=2)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="planned")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["asset", "period"]

    def __str__(self):
        return f"{self.asset.name} - Period {self.period}"


class AssetDisposal(models.Model):
    """Asset disposal records."""

    METHOD_CHOICES = [
        ("sale", "Sale"),
        ("scrap", "Scrap"),
        ("donation", "Donation"),
        ("write_off", "Write-Off"),
    ]
    asset = models.OneToOneField(
        Asset, on_delete=models.CASCADE, related_name="disposal"
    )
    disposal_date = models.DateField()
    disposal_method = models.CharField(max_length=15, choices=METHOD_CHOICES)
    sale_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    gain_loss = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    buyer = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.asset.name} - {self.disposal_method}"


class AssetImpairment(models.Model):
    """Records of impairment charges against an asset."""

    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="impairments"
    )
    date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reason = models.TextField()
    reviewer = models.CharField(max_length=255, blank=True, default="Finance Controller")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.asset.code} impairment {self.date} – {self.amount}"


class AssetTransfer(models.Model):
    """Internal asset transfer / location or custodian reassignment."""

    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="transfers"
    )
    date = models.DateField()
    from_location = models.CharField(max_length=255)
    to_location = models.CharField(max_length=255)
    assignee = models.CharField(max_length=255)
    reason = models.TextField(blank=True)
    from_cost_center = models.ForeignKey(
        "accounting.CostCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_transfers_from",
    )
    to_cost_center = models.ForeignKey(
        "accounting.CostCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_transfers_to",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.asset.code} transfer {self.date}: {self.from_location} → {self.to_location}"
