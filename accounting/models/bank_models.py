from django.db import models


class BankAccount(models.Model):
    """Organization's bank accounts."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("closed", "Closed"),
    ]
    name = models.CharField(max_length=200)
    bank_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50, unique=True)
    branch = models.CharField(max_length=200, blank=True)
    routing_number = models.CharField(max_length=50, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_accounts",
    )
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True
    )
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    last_reconciled_date = models.DateField(null=True, blank=True)
    last_reconciled_balance = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    # Extended fields for treasury workspace
    overdraft_limit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    feed_status = models.CharField(
        max_length=20,
        choices=[("healthy", "Healthy"), ("warning", "Warning"), ("manual", "Manual")],
        default="manual",
    )
    last_sync_at = models.DateTimeField(null=True, blank=True)
    owner = models.CharField(max_length=200, blank=True)
    journal_name = models.CharField(max_length=200, blank=True, default="Bank Journal")
    feed_provider = models.CharField(max_length=200, blank=True)
    statement_frequency = models.CharField(max_length=20, blank=True, default="Daily")
    account_type = models.CharField(
        max_length=10,
        choices=[("bank", "Bank"), ("cash", "Cash")],
        default="bank",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"


class BankTransaction(models.Model):
    """Bank statement line items for reconciliation."""

    TYPE_CHOICES = [
        ("credit", "Credit (Deposit)"),
        ("debit", "Debit (Withdrawal)"),
    ]
    STATUS_CHOICES = [
        ("unreconciled", "Unreconciled"),
        ("reconciled", "Reconciled"),
        ("excluded", "Excluded"),
    ]
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="transactions"
    )
    date = models.DateField()
    description = models.CharField(max_length=500)
    reference = models.CharField(max_length=100, blank=True)
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    running_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default="unreconciled"
    )
    journal_item = models.ForeignKey(
        "accounting.JournalItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_transactions",
    )
    statement_line = models.CharField(max_length=255, blank=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.date}: {self.description} ({self.amount})"


class BankReconciliation(models.Model):
    """Bank reconciliation session."""

    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="reconciliations"
    )
    statement_date = models.DateField()
    statement_balance = models.DecimalField(max_digits=18, decimal_places=2)
    book_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    difference = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default="in_progress"
    )
    notes = models.TextField(blank=True)
    reconciled_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-statement_date"]

    def __str__(self):
        return f"Recon: {self.bank_account} @ {self.statement_date}"


class BankReconciliationLine(models.Model):
    """Individual matched lines in a reconciliation."""

    reconciliation = models.ForeignKey(
        BankReconciliation, on_delete=models.CASCADE, related_name="lines"
    )
    bank_transaction = models.ForeignKey(BankTransaction, on_delete=models.CASCADE)
    journal_item = models.ForeignKey(
        "accounting.JournalItem", on_delete=models.SET_NULL, null=True, blank=True
    )
    is_matched = models.BooleanField(default=False)
    difference = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    def __str__(self):
        return f"Line: {self.bank_transaction}"


class CashRegister(models.Model):
    """Petty cash or cash register management."""

    name = models.CharField(max_length=200)
    account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_registers",
    )
    custodian = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_registers",
    )
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    max_limit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class CashTransaction(models.Model):
    """Cash register transactions."""

    TYPE_CHOICES = [
        ("receipt", "Receipt"),
        ("payment", "Payment"),
        ("replenishment", "Replenishment"),
    ]
    cash_register = models.ForeignKey(
        CashRegister, on_delete=models.CASCADE, related_name="transactions"
    )
    date = models.DateField()
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.CharField(max_length=500)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    balance_after = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    voucher = models.ForeignKey(
        "accounting.Voucher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_transactions",
    )
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.date}: {self.description} ({self.amount})"
