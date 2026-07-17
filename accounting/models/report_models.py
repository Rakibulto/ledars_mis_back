from django.db import models


class FinancialReportTemplate(models.Model):
    """Templates for financial reports (Balance Sheet, P&L, Cash Flow, Trial Balance)."""

    TYPE_CHOICES = [
        ("balance_sheet", "Balance Sheet"),
        ("profit_loss", "Profit & Loss"),
        ("cash_flow", "Cash Flow Statement"),
        ("trial_balance", "Trial Balance"),
        ("general_ledger", "General Ledger"),
        ("aged_payable", "Aged Payable"),
        ("aged_receivable", "Aged Receivable"),
        ("budget_vs_actual", "Budget vs Actual"),
        ("custom", "Custom Report"),
    ]
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ReportLine(models.Model):
    """Line definitions within a report template."""

    COMPUTATION_CHOICES = [
        ("sum_of_accounts", "Sum of Accounts"),
        ("sum_of_lines", "Sum of Lines"),
        ("formula", "Formula"),
        ("total", "Total"),
    ]
    template = models.ForeignKey(
        FinancialReportTemplate, on_delete=models.CASCADE, related_name="lines"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, blank=True)
    sequence = models.IntegerField(default=10)
    computation_type = models.CharField(
        max_length=20, choices=COMPUTATION_CHOICES, default="sum_of_accounts"
    )
    formula = models.CharField(max_length=500, blank=True)
    account_codes = models.CharField(max_length=500, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    is_bold = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)
    indent_level = models.IntegerField(default=0)

    class Meta:
        ordering = ["template", "sequence"]

    def __str__(self):
        return f"{self.template.name} - {self.name}"


class GeneratedReport(models.Model):
    """Saved generated financial reports."""

    STATUS_CHOICES = [
        ("generating", "Generating"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    template = models.ForeignKey(
        FinancialReportTemplate,
        on_delete=models.CASCADE,
        related_name="generated_reports",
    )
    title = models.CharField(max_length=255)
    fiscal_year = models.ForeignKey(
        "accounting.FiscalYear", on_delete=models.SET_NULL, null=True, blank=True
    )
    period_from = models.DateField()
    period_to = models.DateField()
    comparison_from = models.DateField(null=True, blank=True)
    comparison_to = models.DateField(null=True, blank=True)
    cost_center = models.ForeignKey(
        "accounting.CostCenter", on_delete=models.SET_NULL, null=True, blank=True
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default="generating"
    )
    generated_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to="accounting/reports/%Y/%m/", blank=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return self.title


class GeneratedReportData(models.Model):
    """Data rows for generated reports."""

    report = models.ForeignKey(
        GeneratedReport, on_delete=models.CASCADE, related_name="data_rows"
    )
    report_line = models.ForeignKey(
        ReportLine, on_delete=models.SET_NULL, null=True, blank=True
    )
    label = models.CharField(max_length=255)
    current_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    comparison_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    variance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    variance_percent = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    sequence = models.IntegerField(default=0)
    indent_level = models.IntegerField(default=0)
    is_bold = models.BooleanField(default=False)

    class Meta:
        ordering = ["report", "sequence"]

    def __str__(self):
        return f"{self.label}: {self.current_amount}"
