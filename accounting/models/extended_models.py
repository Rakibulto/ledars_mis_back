from django.db import models
from django.utils import timezone


class PaymentTerm(models.Model):
    """Payment terms — Net 30, 2/10 Net 30, etc. (Odoo-style)."""

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, blank=True)
    due_days = models.IntegerField(default=30, help_text="Days until due")
    discount_days = models.IntegerField(default=0, help_text="Days for early discount")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def generate_code(self):
        if self.code:
            return self.code

        year = timezone.now().year
        prefix = f"PY-{year}-"
        max_sequence = 0
        for code in PaymentTerm.objects.filter(code__startswith=prefix).values_list("code", flat=True):
            try:
                sequence = int(code.replace(prefix, ""))
                max_sequence = max(max_sequence, sequence)
            except (TypeError, ValueError):
                continue

        self.code = f"{prefix}{max_sequence + 1:04d}"
        return self.code

    def save(self, *args, **kwargs):
        if not self.code:
            self.generate_code()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class FiscalPosition(models.Model):
    """Fiscal positions — tax & account mappings for different regions (Odoo-style)."""

    name = models.CharField(max_length=200, unique=True)
    country = models.CharField(max_length=100, blank=True)
    zip_from = models.CharField(max_length=20, blank=True)
    zip_to = models.CharField(max_length=20, blank=True)
    auto_apply = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FiscalPositionTaxMapping(models.Model):
    """Tax mapping rules within a fiscal position."""

    fiscal_position = models.ForeignKey(
        FiscalPosition, on_delete=models.CASCADE, related_name="tax_mappings"
    )
    source_tax = models.ForeignKey(
        "accounting.Tax",
        on_delete=models.CASCADE,
        related_name="fp_source_mappings",
    )
    destination_tax = models.ForeignKey(
        "accounting.Tax",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fp_destination_mappings",
    )

    def __str__(self):
        return f"{self.fiscal_position}: {self.source_tax} → {self.destination_tax}"


class FiscalPositionAccountMapping(models.Model):
    """Account mapping rules within a fiscal position."""

    fiscal_position = models.ForeignKey(
        FiscalPosition, on_delete=models.CASCADE, related_name="account_mappings"
    )
    source_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.CASCADE,
        related_name="fp_source_mappings",
    )
    destination_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.CASCADE,
        related_name="fp_destination_mappings",
    )

    def __str__(self):
        return f"{self.fiscal_position}: {self.source_account} → {self.destination_account}"


class Incoterm(models.Model):
    """International commercial terms (Odoo-style)."""

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class ReconciliationModel(models.Model):
    """Automatic reconciliation rule models (Odoo-style)."""

    TYPE_CHOICES = [
        ("writeoff", "Write-Off"),
        ("invoice_matching", "Invoice Matching"),
        ("manual", "Manual"),
    ]
    name = models.CharField(max_length=200)
    model_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="writeoff")
    match_journal = models.ForeignKey(
        "accounting.Journal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    match_label = models.CharField(
        max_length=20,
        choices=[("contains", "Contains"), ("is", "Is"), ("starts_with", "Starts With")],
        default="contains",
    )
    match_label_value = models.CharField(max_length=255, blank=True)
    match_amount = models.CharField(
        max_length=20,
        choices=[("lower", "Lower"), ("greater", "Greater"), ("between", "Between")],
        blank=True,
    )
    match_amount_min = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    match_amount_max = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    auto_validate = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class BankStatement(models.Model):
    """Bank account statements (Odoo-style)."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("imported", "Imported"),
        ("in_progress", "In Progress"),
        ("confirmed", "Confirmed"),
        ("completed", "Completed"),
        ("reconciled", "Reconciled"),
    ]
    bank_account = models.ForeignKey(
        "accounting.BankAccount",
        on_delete=models.CASCADE,
        related_name="statements",
    )
    name = models.CharField(max_length=100, blank=True)
    date = models.DateField()
    period_start = models.DateField()
    period_end = models.DateField()
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_credits = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_debits = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField(blank=True)
    # Extended workspace fields
    period = models.CharField(max_length=50, blank=True)
    source = models.CharField(max_length=100, blank=True)
    parser = models.CharField(max_length=100, blank=True)
    mapping_profile = models.CharField(max_length=200, blank=True)
    feed_batch = models.CharField(max_length=100, blank=True)
    last_import_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.bank_account} - {self.date}"


class BankStatementLine(models.Model):
    """Individual line items within a bank statement."""

    LINE_TYPE_CHOICES = [("credit", "Credit"), ("debit", "Debit")]
    LINE_STATUS_CHOICES = [
        ("unmatched", "Unmatched"),
        ("matched", "Matched"),
        ("suggested", "Suggested"),
        ("writeoff", "Write-Off"),
        ("counterpart_created", "Counterpart Created"),
        ("duplicate", "Duplicate"),
    ]

    statement = models.ForeignKey(
        BankStatement, on_delete=models.CASCADE, related_name="lines"
    )
    date = models.DateField()
    description = models.CharField(max_length=500)
    reference = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    partner = models.CharField(max_length=255, blank=True)
    bank_transaction = models.ForeignKey(
        "accounting.BankTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    # Reconciliation workspace fields
    line_type = models.CharField(
        max_length=10, choices=LINE_TYPE_CHOICES, default="credit"
    )
    line_status = models.CharField(
        max_length=30, choices=LINE_STATUS_CHOICES, default="unmatched"
    )
    recommendation = models.CharField(max_length=500, blank=True)
    recommendation_type = models.CharField(max_length=30, blank=True)
    confidence = models.IntegerField(default=0)
    rule_id = models.IntegerField(null=True, blank=True)
    counterpart_label = models.CharField(max_length=200, blank=True)
    note = models.CharField(max_length=500, blank=True)
    match_reference = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.statement} - {self.description[:50]}"


class Check(models.Model):
    """Check/cheque management (Odoo-style)."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("prepared", "Prepared"),
        ("issued", "Issued"),
        ("deposited", "Deposited"),
        ("cleared", "Cleared"),
        ("bounced", "Bounced"),
        ("cancelled", "Cancelled"),
        ("voided", "Voided"),
    ]
    DIRECTION_CHOICES = [
        ("outgoing", "Outgoing (Issued)"),
        ("incoming", "Incoming (Received)"),
    ]
    check_number = models.CharField(max_length=50)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default="outgoing")
    bank_account = models.ForeignKey(
        "accounting.BankAccount",
        on_delete=models.CASCADE,
        related_name="checks",
    )
    date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    payee = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    memo = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="prepared")
    cleared_date = models.DateField(null=True, blank=True)
    bounced_date = models.DateField(null=True, blank=True)
    payment = models.ForeignKey(
        "accounting.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checks",
    )
    # Extended treasury fields
    owner = models.CharField(max_length=200, blank=True)
    print_status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("printed", "Printed")],
        default="pending",
    )
    print_count = models.IntegerField(default=0)
    last_action_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Check #{self.check_number} - {self.payee}"


class BankTransfer(models.Model):
    """Inter-bank account transfers."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("confirmed", "Confirmed"),
        ("in_transit", "In Transit"),
        ("posted", "Posted"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    reference = models.CharField(max_length=100, blank=True)
    date = models.DateField()
    requested_date = models.DateField(null=True, blank=True)
    scheduled_date = models.DateField(null=True, blank=True)
    posted_date = models.DateField(null=True, blank=True)
    from_account = models.ForeignKey(
        "accounting.BankAccount",
        on_delete=models.CASCADE,
        related_name="transfers_out",
    )
    to_account = models.ForeignKey(
        "accounting.BankAccount",
        on_delete=models.CASCADE,
        related_name="transfers_in",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    description = models.CharField(max_length=500, blank=True)
    purpose = models.TextField(blank=True)
    owner_name = models.CharField(max_length=200, blank=True)
    approver_name = models.CharField(max_length=200, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=[("normal", "Normal"), ("high", "High"), ("critical", "Critical")],
        default="normal",
    )
    trace_code = models.CharField(max_length=100, blank=True)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_approval")
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference or 'Transfer'} - {self.amount}"


class DeferredRevenue(models.Model):
    """Deferred revenue tracking (Odoo-style)."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("running", "Running"),
        ("fully_recognized", "Fully Recognized"),
        ("cancelled", "Cancelled"),
    ]
    reference = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2)
    recognized_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    start_date = models.DateField()
    end_date = models.DateField()
    periods = models.IntegerField(default=12, help_text="Recognition periods")
    deferred_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deferred_revenue_deferred",
    )
    revenue_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deferred_revenue_income",
    )
    journal = models.ForeignKey(
        "accounting.Journal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        "accounting.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    description = models.TextField(blank=True)
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
        ordering = ["-start_date"]

    def __str__(self):
        return self.name


class DeferredExpense(models.Model):
    """Deferred/prepaid expense tracking (Odoo-style)."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("running", "Running"),
        ("fully_recognized", "Fully Recognized"),
        ("cancelled", "Cancelled"),
    ]
    reference = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2)
    recognized_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    start_date = models.DateField()
    end_date = models.DateField()
    periods = models.IntegerField(default=12, help_text="Recognition periods")
    prepaid_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deferred_expense_prepaid",
    )
    expense_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deferred_expense_expense",
    )
    journal = models.ForeignKey(
        "accounting.Journal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deferred_expenses",
    )
    vendor = models.ForeignKey(
        "accounting.Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    description = models.TextField(blank=True)
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
        ordering = ["-start_date"]

    def __str__(self):
        return self.name
