from django.db import models
from django.utils import timezone
from project_managements.models import Currency, ProjectManagementProject

#add donor
class Donor(models.Model):
    TYPE_CHOICES = [
        ("individual", "Individual"),
        ("organization", "Organization"),
        ("government", "Government"),
        ("ngo", "NGO"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("suspended", "Suspended"),
    ]

    donor_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    email = models.CharField(max_length=254, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    organization_name = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    total_donated_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="donors",
    )
    last_donation_date = models.DateField(blank=True, null=True)
    description = models.TextField(null=True, blank=True)
    document = models.FileField(upload_to="donor/documents/%Y/%m/", blank=True, null=True)
    photo = models.FileField(upload_to="donor/photos/%Y/%m/", blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_name = models.CharField(max_length=255, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=40, blank=True, null=True)
    preferred_language = models.CharField(max_length=50, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    national_id_number = models.CharField(max_length=100, blank=True, null=True)
    registration_number = models.CharField(max_length=100, blank=True, null=True)
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ("email", "Email"),
            ("phone", "Phone"),
            ("whatsapp", "WhatsApp"),
            ("sms", "SMS"),
        ],
        blank=True,
        null=True,
    )

    created_by = models.ForeignKey("authentication.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["donor_code"]

    def __str__(self):
        return f"{self.donor_code} - {self.name}"

    @classmethod
    def generate_donor_code(cls):
        year = timezone.now().year
        prefix = f"DON-{year}-"
        last = cls.objects.filter(donor_code__startswith=prefix).order_by("donor_code").last()
        if last:
            try:
                last_num = int(last.donor_code.split("-")[-1])
            except (ValueError, IndexError):
                last_num = 0
            next_num = last_num + 1
        else:
            next_num = 1
        return f"{prefix}{next_num:04d}"

    def save(self, *args, **kwargs):
        if not self.donor_code:
            self.donor_code = self.generate_donor_code()
        super().save(*args, **kwargs)


class DonorLedger(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ("donation", "Donation"),
        ("refund", "Refund"),
        ("adjustment", "Adjustment"),
        ("credit", "Credit"),
        ("debit", "Debit"),
    ]

    donor = models.ForeignKey(Donor, related_name="donor_ledgers", on_delete=models.CASCADE)
    ledger_code = models.CharField(max_length=50, unique=True, blank=True)
    transaction_date = models.DateField(default=timezone.now)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, default="donation")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="USD")
    reference = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    related_project = models.ForeignKey(ProjectManagementProject, on_delete=models.SET_NULL, blank=True, null=True, related_name="donor_ledgers")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_reconciled = models.BooleanField(default=False)

    created_by = models.ForeignKey("authentication.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-transaction_date", "-created_at"]

    def __str__(self):
        return f"{self.ledger_code} - {self.donor.name}"

    @classmethod
    def generate_ledger_code(cls):
        year = timezone.now().year
        prefix = f"DL-{year}-"
        last = cls.objects.filter(ledger_code__startswith=prefix).order_by("ledger_code").last()
        if last:
            try:
                last_num = int(last.ledger_code.split("-")[-1])
            except (ValueError, IndexError):
                last_num = 0
            next_num = last_num + 1
        else:
            next_num = 1
        return f"{prefix}{next_num:04d}"

    def save(self, *args, **kwargs):
        if not self.ledger_code:
            self.ledger_code = self.generate_ledger_code()
        super().save(*args, **kwargs)
