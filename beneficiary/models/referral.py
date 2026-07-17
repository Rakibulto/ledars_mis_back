from django.db import models
from django.utils import timezone


class Referral(models.Model):

    STATUS_CHOICES = (
        ("Pending", "Pending"),
        ("Accepted", "Accepted"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
    )

    PRIORITY_CHOICES = (
        ("Critical", "Critical"),
        ("High", "High"),
        ("Medium", "Medium"),
        ("Low", "Low"),
    )

    referral_code = models.CharField(max_length=20, unique=True, blank=True)
    beneficiary = models.ForeignKey(
        "beneficiary.Beneficiary", on_delete=models.SET_NULL, null=True, blank=True
    )
    referred_to = models.CharField(max_length=255, null=True, blank=True)
    service = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Pending", null=True, blank=True
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="Medium", null=True, blank=True
    )

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.referral_code:
            year = timezone.now().year

            last_record = (
                Referral.objects.filter(referral_code__startswith=f"REF-{year}")
                .order_by("-id")
                .first()
            )

            if last_record:
                last_number = int(last_record.referral_code.split("-")[-1])
                new_number = str(last_number + 1).zfill(4)
            else:
                new_number = "0001"

            self.referral_code = f"REF-{year}-{new_number}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.referral_code or self.pk} - {self.beneficiary or self.pk}"


class ReferralNetworkPartner(models.Model):
    STATUS_CHOICES = [("Active", "Active"), ("Inactive", "Inactive")]
    organization = models.CharField(max_length=255)
    type = models.CharField(max_length=100, null=True, blank=True)
    services = models.JSONField(default=list, blank=True)
    coverage = models.CharField(max_length=255, null=True, blank=True)
    contact = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    referrals_made = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.organization
