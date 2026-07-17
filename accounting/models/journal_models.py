from django.db import models
from django.db import transaction
from django.utils import timezone


class Journal(models.Model):
    """Odoo-style accounting journals (Sales, Purchase, Bank, Cash, Miscellaneous)."""

    TYPE_CHOICES = [
        ("sales", "Sales"),
        ("purchase", "Purchase"),
        ("bank", "Bank"),
        ("cash", "Cash"),
        ("general", "General / Miscellaneous"),
    ]
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10, unique=True)
    journal_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    default_debit_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_debit_journals",
    )
    default_credit_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_credit_journals",
    )
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True
    )
    bank_account = models.ForeignKey(
        "accounting.BankAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journals",
    )
    sequence_prefix = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    allow_multi_currency = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def generate_code(self):
        if self.code:
            return self.code

        year = timezone.now().year
        prefix = f"J-{year}-"
        max_sequence = 0
        for code in Journal.objects.filter(code__startswith=prefix).values_list("code", flat=True):
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
        return f"{self.code} - {self.name}"


class JournalEntry(models.Model):
    """Odoo-style account.move — the core accounting entry."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("cancelled", "Cancelled"),
    ]
    journal = models.ForeignKey(
        Journal, on_delete=models.PROTECT, related_name="entries"
    )
    reference = models.CharField(max_length=100, unique=True, blank=True)
    date = models.DateField()
    fiscal_period = models.ForeignKey(
        "accounting.FiscalPeriod", on_delete=models.SET_NULL, null=True, blank=True
    )
    narration = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    total_debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True
    )
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    is_auto_generated = models.BooleanField(default=False)
    source_document = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    posted_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posted_journal_entries",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference or f"JE-{self.id}"

    def save(self, *args, **kwargs):
        if not self.reference:
            prefix = self.journal.sequence_prefix or self.journal.code
            year = self.date.year if self.date else timezone.now().year
            with transaction.atomic():
                count = (
                    JournalEntry.objects.filter(
                        journal=self.journal, date__year=year
                    ).count()
                    + 1
                )
                self.reference = f"{prefix}/{year}/{count:05d}"
        super().save(*args, **kwargs)


class JournalItem(models.Model):
    """Odoo-style account.move.line — individual debit/credit line in a journal entry."""

    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.CASCADE, related_name="items"
    )
    account = models.ForeignKey(
        "accounting.Account", on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_items"
    )
    partner_type = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ("customer", "Customer"),
            ("vendor", "Vendor"),
            ("employee", "Employee"),
        ],
    )
    partner_id = models.IntegerField(null=True, blank=True)
    label = models.CharField(max_length=500, blank=True)
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount_currency = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True
    )
    tax = models.ForeignKey(
        "accounting.Tax", on_delete=models.SET_NULL, null=True, blank=True
    )
    analytic_account = models.ForeignKey(
        "accounting.AnalyticAccount", on_delete=models.SET_NULL, null=True, blank=True
    )
    cost_center = models.ForeignKey(
        "accounting.CostCenter", on_delete=models.SET_NULL, null=True, blank=True
    )
    is_reconciled = models.BooleanField(default=False)
    reconcile_ref = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account.code}: Dr {self.debit} / Cr {self.credit}"


class JournalEntryAttachment(models.Model):
    """File attachment linked to a JournalEntry for audit documentation."""

    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to="accounting/journal_attachments/%Y/%m/")
    name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.name


class RecurringJournalTemplate(models.Model):
    """Recurring journal entry templates for automated posting."""

    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("yearly", "Yearly"),
    ]
    name = models.CharField(max_length=200)
    journal = models.ForeignKey(
        Journal, on_delete=models.CASCADE, related_name="recurring_templates"
    )
    narration = models.TextField(blank=True)
    frequency = models.CharField(
        max_length=20, choices=FREQUENCY_CHOICES, default="monthly"
    )
    next_run_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    auto_post = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class RecurringJournalLine(models.Model):
    """Line items in a recurring journal template."""

    template = models.ForeignKey(
        RecurringJournalTemplate, on_delete=models.CASCADE, related_name="lines"
    )
    account = models.ForeignKey("accounting.Account", on_delete=models.SET_NULL, null=True, blank=True)
    label = models.CharField(max_length=500, blank=True)
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    analytic_account = models.ForeignKey(
        "accounting.AnalyticAccount", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.account.code}: Dr {self.debit} / Cr {self.credit}"
