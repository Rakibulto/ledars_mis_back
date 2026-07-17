from django.db import models


class CostCenter(models.Model):
    """Cost centers for expense tracking and allocation."""

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    manager = models.CharField(max_length=200, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cost_centers",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cost_centers",
    )
    budget = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    spent = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class AnalyticPlan(models.Model):
    """Odoo-style analytic plans (dimensions) with governance rules."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default="#2563eb")
    level = models.IntegerField(default=1)
    hierarchy_label = models.CharField(max_length=100, blank=True)
    mandatory_dimensions = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated list, e.g. Project, Partner",
    )
    applicability = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated list, e.g. Journal items, Vendor bills",
    )
    governance_owner = models.CharField(max_length=200, blank=True)
    approval_mode = models.CharField(
        max_length=100, blank=True, default="Review on exceptions"
    )
    default_policy = models.TextField(blank=True)
    parent_plan = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_plans",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["level", "name"]

    def __str__(self):
        return self.name


class AnalyticAccount(models.Model):
    """Odoo-style analytic accounts for multi-dimensional accounting."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    group = models.CharField(max_length=100, blank=True)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytic_accounts",
    )
    partner_type = models.CharField(
        max_length=20,
        blank=True,
        choices=[("customer", "Customer"), ("vendor", "Vendor"), ("donor", "Donor")],
    )
    partner_id = models.IntegerField(null=True, blank=True)
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True
    )
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    plan = models.ForeignKey(
        AnalyticPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytic_accounts",
    )
    partner = models.CharField(max_length=200, blank=True)
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    distribution_method = models.CharField(
        max_length=30,
        blank=True,
        default="fixed_ratio",
        choices=[
            ("fixed_ratio", "Fixed Ratio"),
            ("manual_split", "Manual Split"),
        ],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class AnalyticLine(models.Model):
    """Analytic entries linked to journal items."""

    analytic_account = models.ForeignKey(
        AnalyticAccount, on_delete=models.CASCADE, related_name="lines"
    )
    journal_item = models.ForeignKey(
        "accounting.JournalItem",
        on_delete=models.CASCADE,
        related_name="analytic_lines",
    )
    date = models.DateField()
    name = models.CharField(max_length=500, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    unit_amount = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.SET_NULL, null=True, blank=True
    )
    tag = models.ForeignKey(
        "accounting.AnalyticTag", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.analytic_account.code}: {self.name} ({self.amount})"


class AnalyticTag(models.Model):
    """Tags for analytic lines."""

    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default="#6366F1")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
