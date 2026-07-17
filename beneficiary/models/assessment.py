from django.db import models
from django.utils import timezone


class VulnerabilityAssessment(models.Model):

    RISK_LEVEL_CHOICES = (
        ("Critical", "Critical"),
        ("High", "High"),
        ("Medium", "Medium"),
        ("Low", "Low"),
    )

    assessment_code = models.CharField(max_length=20, unique=True, blank=True)
    beneficiary = models.ForeignKey(
        "beneficiary.Beneficiary", on_delete=models.SET_NULL, null=True, blank=True
    )
    assessment_date = models.DateField(null=True, blank=True)
    assessor = models.CharField(max_length=255, null=True, blank=True)
    overall_score = models.PositiveIntegerField(null=True, blank=True)
    risk_level = models.CharField(
        max_length=10, choices=RISK_LEVEL_CHOICES, null=True, blank=True
    )

    # Category Scores
    food = models.PositiveIntegerField(null=True, blank=True)
    shelter = models.PositiveIntegerField(null=True, blank=True)
    health = models.PositiveIntegerField(null=True, blank=True)
    protection = models.PositiveIntegerField(null=True, blank=True)
    education = models.PositiveIntegerField(null=True, blank=True)
    livelihood = models.PositiveIntegerField(null=True, blank=True)

    recommendations = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def save(self, *args, **kwargs):

        if not self.assessment_code:
            year = timezone.now().year

            last_record = (
                VulnerabilityAssessment.objects.filter(
                    assessment_code__startswith=f"VA-{year}"
                )
                .order_by("-id")
                .first()
            )

            if last_record:
                last_number = int(last_record.assessment_code.split("-")[-1])
                new_number = str(last_number + 1).zfill(4)
            else:
                new_number = "0001"

            self.assessment_code = f"VA-{year}-{new_number}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.assessment_code} - {self.beneficiary}"


class ImpactMeasurement(models.Model):
    MONTH_CHOICES = [
        ("Jan", "January"),
        ("Feb", "February"),
        ("Mar", "March"),
        ("Apr", "April"),
        ("May", "May"),
        ("Jun", "June"),
        ("Jul", "July"),
        ("Aug", "August"),
        ("Sep", "September"),
        ("Oct", "October"),
        ("Nov", "November"),
        ("Dec", "December"),
    ]
    month = models.CharField(max_length=3, choices=MONTH_CHOICES)
    education = models.IntegerField()
    health = models.IntegerField()
    livelihood = models.IntegerField()
    wash = models.IntegerField()
    year = models.IntegerField(default=2026)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.month} - {self.year}"


class OutcomeIndicator(models.Model):
    STATUS = [
        ("Draft", "Draft"),
        ("Completed", "Completed"),
        ("Active", "Active"),
        ("Inactive", "Inactive"),
    ]

    indicator = models.CharField(max_length=255)
    baseline = models.DecimalField(max_digits=10, decimal_places=2)
    current = models.DecimalField(max_digits=10, decimal_places=2)
    target = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20)
    status = models.CharField(max_length=30, choices=STATUS, default="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.indicator


class NeedsAssessment(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Reviewed", "Reviewed"),
    ]
    reference = models.CharField(max_length=50, unique=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    assessor = models.CharField(max_length=255, null=True, blank=True)
    population = models.PositiveIntegerField(default=0)
    priority_needs = models.JSONField(default=list, blank=True)
    gap_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    recommendations = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().year
            last = (
                NeedsAssessment.objects.filter(reference__startswith=f"NA-{year}")
                .order_by("-id")
                .first()
            )
            seq = int(last.reference.split("-")[-1]) + 1 if last else 1
            self.reference = f"NA-{year}-{str(seq).zfill(4)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.reference
