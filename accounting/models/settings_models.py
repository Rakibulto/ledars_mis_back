from django.db import models
from django.utils import timezone


class AccountingSettings(models.Model):
    """Global accounting configuration — singleton-style."""

    company_name = models.CharField(max_length=255, default="LEDARS")
    base_currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    default_journal = models.ForeignKey(
        "accounting.Journal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    default_receivable_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    default_payable_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    current_fiscal_year = models.ForeignKey(
        "accounting.FiscalYear",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    auto_post_vouchers = models.BooleanField(default=False)
    require_voucher_approval = models.BooleanField(default=True)
    use_ngo_project_required = models.BooleanField(
        default=False,
        help_text="When True, vouchers must have an NGO project (project_managements) before posting.",
    )
    lock_date = models.DateField(null=True, blank=True)
    tax_lock_date = models.DateField(null=True, blank=True)
    enable_budget_control = models.BooleanField(default=True)
    enable_analytic_accounting = models.BooleanField(default=True)
    enable_multi_currency = models.BooleanField(default=False)
    decimal_precision = models.IntegerField(default=2)
    # Print template fields
    print_logo = models.ImageField(upload_to='print_logos/', null=True, blank=True)
    print_company_name = models.CharField(max_length=255, blank=True)
    print_company_address = models.TextField(blank=True)
    print_company_tagline = models.CharField(max_length=255, blank=True)
    print_company_phone = models.CharField(max_length=50, blank=True)
    print_company_email = models.EmailField(blank=True)
    print_company_website = models.CharField(max_length=255, blank=True)
    print_header_alignment = models.CharField(
        max_length=10,
        choices=[('left', 'Left'), ('center', 'Center'), ('right', 'Right')],
        default='left',
    )
    print_primary_color = models.CharField(max_length=7, default='#000000')
    print_accent_color = models.CharField(max_length=7, default='#cccccc')
    print_show_divider = models.BooleanField(default=True)
    print_footer_left = models.CharField(max_length=255, blank=True)
    print_footer_center = models.CharField(max_length=255, blank=True)
    print_footer_right = models.CharField(max_length=255, blank=True)
    print_show_page_numbers = models.BooleanField(default=True)
    print_show_date = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Accounting Settings"
        verbose_name_plural = "Accounting Settings"

    def __str__(self):
        return "Accounting Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class NumberSequence(models.Model):
    """Auto-numbering configuration for different document types."""

    document_type = models.CharField(max_length=50, unique=True)
    prefix = models.CharField(max_length=20)
    padding = models.IntegerField(default=5)
    next_number = models.IntegerField(default=1)
    reset_yearly = models.BooleanField(default=True)
    current_year = models.IntegerField(default=2026)

    def __str__(self):
        return f"{self.document_type}: {self.prefix}-{self.next_number}"

    def get_next(self):
        year = timezone.now().year
        if self.reset_yearly and self.current_year != year:
            self.current_year = year
            self.next_number = 1
        number = f"{self.prefix}-{year}-{self.next_number:0{self.padding}d}"
        self.next_number += 1
        self.save(update_fields=["next_number", "current_year"])
        return number


class ApprovalRule(models.Model):
    """Approval workflow rules for accounting documents."""

    DOCUMENT_TYPE_CHOICES = [
        ("voucher", "Voucher"),
        ("bill", "Bill"),
        ("invoice", "Invoice"),
        ("payment", "Payment"),
        ("journal_entry", "Journal Entry"),
        ("budget_transfer", "Budget Transfer"),
    ]
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    level = models.IntegerField(default=1)
    min_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    max_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    approver = models.ForeignKey(
        "authentication.User",
        on_delete=models.CASCADE,
        related_name="accounting_approval_rules",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["document_type", "level"]

    def __str__(self):
        return f"{self.document_type} L{self.level}: {self.approver}"


class ApprovalWorkflow(models.Model):
    """Rich multi-level approval workflow definition for the frontend workspace."""

    DOCUMENT_TYPE_CHOICES = [
        ("journal_entry", "Journal Entry"),
        ("invoice", "Invoice"),
        ("payment", "Payment"),
        ("expense", "Expense"),
        ("budget", "Budget"),
    ]

    name = models.CharField(max_length=255)
    document_type = models.CharField(
        max_length=20, choices=DOCUMENT_TYPE_CHOICES, default="payment"
    )
    threshold = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    escalation = models.CharField(max_length=255, blank=True)
    delegation = models.CharField(max_length=255, blank=True)
    journal_scope = models.CharField(max_length=100, blank=True, default="General Journal")
    company_scope = models.CharField(max_length=100, blank=True, default="All entities")
    amount_condition = models.CharField(max_length=255, blank=True)
    role_assignment = models.CharField(max_length=500, blank=True)
    # Stored as JSON array of {role, condition} objects
    levels = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PostingRule(models.Model):
    """Conditional accounting posting logic with transaction routing and amount-band governance."""

    TRANSACTION_TYPE_CHOICES = [
        ("invoice", "Invoice"),
        ("payment", "Payment"),
        ("expense", "Expense"),
        ("payroll", "Payroll"),
        ("inventory", "Inventory"),
    ]

    name = models.CharField(max_length=255)
    transaction_type = models.CharField(
        max_length=20, choices=TRANSACTION_TYPE_CHOICES, default="invoice"
    )
    debit_account = models.CharField(max_length=255, blank=True)
    credit_account = models.CharField(max_length=255, blank=True)
    condition = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    amount_band = models.CharField(max_length=100, blank=True, default="All amounts")
    preview_result = models.TextField(blank=True)
    journal_scope = models.CharField(max_length=100, blank=True, default="General Journal")
    document_condition = models.CharField(
        max_length=255, blank=True, default="Approved source document"
    )
    company_scope = models.CharField(max_length=100, blank=True, default="All entities")
    approval_requirement = models.TextField(blank=True, default="Controller review not required")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class IntegrationRule(models.Model):
    """Cross-module event flow and sync configuration for accounting automation."""

    SYNC_FREQUENCY_CHOICES = [
        ("Real time", "Real time"),
        ("Hourly", "Hourly"),
        ("Daily", "Daily"),
        ("Payroll close", "Payroll close"),
    ]
    RULE_MODE_CHOICES = [
        ("Document mapping", "Document mapping"),
        ("Milestone trigger", "Milestone trigger"),
        ("Batch import", "Batch import"),
        ("Webhook event", "Webhook event"),
    ]
    TEST_STATUS_CHOICES = [
        ("passed", "Passed"),
        ("warning", "Warning"),
        ("failed", "Failed"),
        ("not-tested", "Not tested"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True, default="solar:plug-circle-bold-duotone")
    connected = models.BooleanField(default=False)
    sync_frequency = models.CharField(
        max_length=50, choices=SYNC_FREQUENCY_CHOICES, default="Daily"
    )
    owner = models.CharField(max_length=255, blank=True)
    endpoint = models.CharField(max_length=255, blank=True)
    rule_mode = models.CharField(
        max_length=50, choices=RULE_MODE_CHOICES, default="Document mapping"
    )
    mapping_summary = models.TextField(blank=True)
    webhook_trigger = models.CharField(max_length=255, blank=True)
    app_connection = models.CharField(max_length=255, blank=True)
    auth_mode = models.CharField(max_length=100, blank=True)
    retry_policy = models.TextField(blank=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(
        max_length=20, choices=TEST_STATUS_CHOICES, default="not-tested"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    """Accounting audit trail."""

    ACTION_CHOICES = [
        ("create", "Created"),
        ("update", "Updated"),
        ("delete", "Deleted"),
        ("post", "Posted"),
        ("approve", "Approved"),
        ("reject", "Rejected"),
        ("cancel", "Cancelled"),
        ("reconcile", "Reconciled"),
    ]
    model_name = models.CharField(max_length=100)
    object_id = models.IntegerField()
    action = models.CharField(max_length=15, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)
    changes = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["model_name", "object_id"]),
        ]

    def __str__(self):
        return f"{self.model_name}#{self.object_id}: {self.action} by {self.user}"


class LockDate(models.Model):
    """Period-close controls with soft, tax, and hard lock governance."""

    TYPE_CHOICES = [
        ("soft", "Soft"),
        ("tax", "Tax"),
        ("hard", "Hard"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="soft")
    lock_date = models.DateField()
    scope = models.CharField(max_length=255, default="Accounting period")
    applies_to = models.CharField(max_length=255, default="All accountants")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lock Date"
        verbose_name_plural = "Lock Dates"

    def __str__(self):
        return f"{self.name} ({self.type}) – {self.lock_date}"
