from django.db import models
from django.db import transaction
from django.utils import timezone


class VoucherSequence(models.Model):
    """Auto-numbering for vouchers."""

    voucher_type = models.CharField(max_length=20)
    year = models.IntegerField()
    last_number = models.IntegerField(default=0)

    class Meta:
        unique_together = ["voucher_type", "year"]

    def __str__(self):
        return f"{self.voucher_type}-{self.year}: {self.last_number}"


class Voucher(models.Model):
    """Voucher management — Payment, Receipt, Journal, Contra vouchers."""

    TYPE_CHOICES = [
        ("payment", "Payment Voucher"),
        ("receipt", "Receipt Voucher"),
        ("journal", "Journal Voucher"),
        ("contra", "Contra Voucher"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("posted", "Posted"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    voucher_number = models.CharField(max_length=50, unique=True, blank=True)
    voucher_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    journal = models.ForeignKey(
        "accounting.Journal", on_delete=models.PROTECT, related_name="vouchers"
    )
    journal_entry = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voucher",
    )
    date = models.DateField()
    narration = models.TextField(blank=True)
    payee = models.CharField(max_length=255, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vouchers",
    )
    ngo_project = models.ForeignKey(
        "project_managements.ProjectManagementProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounting_vouchers",
    )
    cost_center = models.ForeignKey(
        "accounting.CostCenter", on_delete=models.SET_NULL, null=True, blank=True
    )
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True
    )
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_vouchers",
    )
    approved_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_vouchers",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.voucher_number or f"V-{self.id}"

    def save(self, *args, **kwargs):
        if not self.voucher_number:
            year = self.date.year if self.date else timezone.now().year
            prefix_map = {
                "payment": "PV",
                "receipt": "RV",
                "journal": "JV",
                "contra": "CV",
            }
            prefix = prefix_map.get(self.voucher_type, "V")
            with transaction.atomic():
                seq, _ = VoucherSequence.objects.select_for_update().get_or_create(
                    voucher_type=self.voucher_type,
                    year=year,
                    defaults={"last_number": 0},
                )
                seq.last_number += 1
                seq.save(update_fields=["last_number"])
                self.voucher_number = f"{prefix}-{year}-{seq.last_number:05d}"
        super().save(*args, **kwargs)


class VoucherLine(models.Model):
    """Individual debit/credit entries in a voucher."""

    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey("accounting.Account", on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=500, blank=True)
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax = models.ForeignKey(
        "accounting.Tax", on_delete=models.SET_NULL, null=True, blank=True
    )
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    analytic_account = models.ForeignKey(
        "accounting.AnalyticAccount", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.account.code}: Dr {self.debit} / Cr {self.credit}"


class VoucherApproval(models.Model):
    """Approval workflow for vouchers."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    voucher = models.ForeignKey(
        Voucher, on_delete=models.CASCADE, related_name="approvals"
    )
    approver = models.ForeignKey("authentication.User", on_delete=models.CASCADE)
    level = models.IntegerField(default=1)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    remarks = models.TextField(blank=True)
    acted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["level"]

    def __str__(self):
        return f"{self.voucher} - Level {self.level}: {self.status}"


class VoucherAttachment(models.Model):
    """Supporting documents attached to vouchers."""

    voucher = models.ForeignKey(
        Voucher, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to="accounting/voucher_attachments/%Y/%m/")
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(default=0)
    uploaded_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name
