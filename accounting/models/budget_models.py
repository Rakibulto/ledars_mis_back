from django.db import models


class BudgetCategory(models.Model):
    """Budget categories for classification."""

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "Budget categories"

    def __str__(self):
        return f"{self.code} - {self.name}"


class Budget(models.Model):
    """Budget periods with allocated amounts (Odoo-style)."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("pending_approval", "Pending Approval"),
        ("confirmed", "Confirmed"),
        ("validated", "Validated"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]
    name = models.CharField(max_length=200)
    fiscal_year = models.ForeignKey(
        "accounting.FiscalYear", on_delete=models.CASCADE, related_name="budgets"
    )
    fiscal_period = models.ForeignKey(
        "accounting.FiscalPeriod", on_delete=models.SET_NULL, null=True, blank=True
    )
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounting_budgets",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="budgets",
    )
    cost_center = models.ForeignKey(
        "accounting.CostCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="budgets",
    )
    # Workspace fields
    owner = models.CharField(max_length=200, default="Budget Controller", blank=True)
    department_label = models.CharField(max_length=200, blank=True)
    warning_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=85)
    critical_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=95)
    total_planned = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_actual = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_committed = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_encumbrance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_available = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    allow_overbudget = models.BooleanField(default=False)
    overbudget_tolerance_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounting_budgets_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class BudgetLine(models.Model):
    """Individual budget allocations per account."""

    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey("accounting.Account", on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(
        BudgetCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    owner = models.CharField(max_length=200, blank=True, default="Budget Controller")
    planned_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    actual_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    committed_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    encumbrance_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    available_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ["budget", "account"]

    def __str__(self):
        return f"{self.budget.name} - {self.account.code}: {self.planned_amount}"

    def save(self, *args, **kwargs):
        self.available_amount = (
            self.planned_amount
            - self.actual_amount
            - self.committed_amount
            - self.encumbrance_amount
        )
        super().save(*args, **kwargs)


class BudgetTransfer(models.Model):
    """Transfer budget between lines."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    from_line = models.ForeignKey(
        BudgetLine, on_delete=models.CASCADE, related_name="transfers_out"
    )
    to_line = models.ForeignKey(
        BudgetLine, on_delete=models.CASCADE, related_name="transfers_in"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    requested_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="budget_transfer_requests",
    )
    approved_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="budget_transfer_approvals",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Transfer {self.amount} from {self.from_line} to {self.to_line}"

class BudgetAmendment(models.Model):
    """Budget amendment requests — line-level amount changes requiring approval."""

    STATUS_CHOICES = [
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    budget = models.ForeignKey(
        Budget, on_delete=models.CASCADE, related_name="amendments"
    )
    target_line = models.ForeignKey(
        BudgetLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="amendments",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    reason = models.TextField()
    effective_period = models.CharField(max_length=20, blank=True)
    requested_by = models.CharField(max_length=200, blank=True, default="Budget Controller")
    approved_by = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_approval")
    created_at = models.DateTimeField(auto_now_add=True)
    acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Amendment {self.amount} on {self.budget.name}"