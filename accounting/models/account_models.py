from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint


class AccountType(models.Model):
    """Odoo-style account type classification (Assets, Liabilities, Equity, Income, Expense)."""

    CLASSIFICATION_CHOICES = [
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("equity", "Equity"),
        ("income", "Income"),
        ("expense", "Expense"),
    ]
    LIQUIDITY_CHOICES = [
        ("current", "Current"),
        ("non_current", "Non-Current"),
        ("bank_cash", "Bank and Cash"),
        ("receivable", "Receivable"),
        ("payable", "Payable"),
        ("na", "N/A"),
    ]
    name = models.CharField(max_length=100, unique=True)
    classification = models.CharField(max_length=20, choices=CLASSIFICATION_CHOICES)
    liquidity_type = models.CharField(
        max_length=20, choices=LIQUIDITY_CHOICES, default="na"
    )
    include_initial_balance = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.name} ({self.get_classification_display()})"


class AccountGroup(models.Model):
    """Hierarchical grouping of accounts (Odoo-style account groups)."""

    name = models.CharField(max_length=200)
    code_prefix_start = models.CharField(max_length=20, blank=True)
    code_prefix_end = models.CharField(max_length=20, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    account_type = models.ForeignKey(
        AccountType, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["code_prefix_start"]

    def __str__(self):
        return (
            f"{self.code_prefix_start} - {self.name}"
            if self.code_prefix_start
            else self.name
        )


class Account(models.Model):
    """
    Chart of Accounts ledger.

    - ngo_project set → project-owned account (each project has its own CoA)
    - ngo_project null → global account (used for shared Bank/Cash ledgers)
    """

    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    ngo_project = models.ForeignKey(
        "project_managements.ProjectManagementProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chart_accounts",
        help_text="Null = global (shared bank/cash). Set = project-scoped CoA.",
    )
    account_type = models.ForeignKey(
        AccountType, on_delete=models.SET_NULL, null=True, blank=True, related_name="accounts"
    )
    account_group = models.ForeignKey(
        AccountGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounts",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_accounts",
    )
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True
    )
    description = models.TextField(blank=True)
    is_reconcilable = models.BooleanField(default=False)
    is_deprecated = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_contra = models.BooleanField(default=False)
    allow_journal_entries = models.BooleanField(default=True)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounting_accounts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            UniqueConstraint(
                fields=["code"],
                condition=Q(ngo_project__isnull=True),
                name="uniq_account_code_global",
            ),
            UniqueConstraint(
                fields=["ngo_project", "code"],
                condition=Q(ngo_project__isnull=False),
                name="uniq_account_code_per_project",
            ),
        ]

    def clean(self):
        super().clean()
        if self.parent_id:
            parent = self.parent
            if parent is None and self.parent_id:
                parent = Account.objects.filter(pk=self.parent_id).first()
            if parent and parent.ngo_project_id != self.ngo_project_id:
                raise ValidationError(
                    {
                        "parent": (
                            "Parent account must belong to the same project "
                            "(or both must be global)."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        if not self.pk and not self.code:
            qs = Account.objects.filter(code__regex=r"^ACC-\d+$")
            if self.ngo_project_id:
                qs = qs.filter(ngo_project_id=self.ngo_project_id)
            else:
                qs = qs.filter(ngo_project__isnull=True)
            existing_nums = list(qs.values_list("code", flat=True))
            nums = [int(c.split("-")[1]) for c in existing_nums if c]
            next_num = max(nums) + 1 if nums else 1
            self.code = f"ACC-{next_num:04d}"
        if self.parent_id:
            parent_project_id = (
                Account.objects.filter(pk=self.parent_id)
                .values_list("ngo_project_id", flat=True)
                .first()
            )
            if parent_project_id != self.ngo_project_id:
                raise ValidationError(
                    "Parent account must belong to the same project "
                    "(or both must be global)."
                )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"


class AccountTag(models.Model):
    """Tags for account categorization and reporting."""

    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default="#6366F1")
    accounts = models.ManyToManyField(Account, blank=True, related_name="tags")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
