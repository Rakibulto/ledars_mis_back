from django.db import models
from django.utils import timezone


class HouseholdProfiling(models.Model):
    SHELTER_TYPE = (
        ("Temporary", "Temporary"),
        ("Semi-permanent", "Semi-permanent"),
        ("Permanent", "Permanent"),
    )

    household_code = models.CharField(max_length=20, unique=True, blank=True)
    head_of_household = models.CharField(max_length=255, null=True, blank=True)
    members = models.PositiveIntegerField(null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    block = models.CharField(max_length=10, null=True, blank=True)

    shelter = models.CharField(
        max_length=20, choices=SHELTER_TYPE, null=True, blank=True
    )
    RISK_LEVELS = (
        ("High", "High"),
        ("Medium", "Medium"),
        ("Low", "Low"),
    )
    risk = models.CharField(max_length=20, choices=RISK_LEVELS, null=True, blank=True)
    income = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    vulnerable_members = models.PositiveIntegerField(default=0, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if not self.household_code:
            year = timezone.now().year

            last_record = (
                HouseholdProfiling.objects.filter(
                    household_code__startswith=f"HH-{year}"
                )
                .order_by("-id")
                .first()
            )

            if last_record:
                last_number = int(last_record.household_code.split("-")[-1])
                new_number = str(last_number + 1).zfill(4)
            else:
                new_number = "0001"

            self.household_code = f"HH-{year}-{new_number}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.household_code} - {self.head_of_household}"


class CoverageArea(models.Model):
    division = models.CharField(max_length=100)
    districts = models.JSONField(default=list, blank=True)
    beneficiaries = models.PositiveIntegerField(default=0)
    projects = models.PositiveIntegerField(default=0)
    field_offices = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.division
