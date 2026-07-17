from django.db import models
from django.utils import timezone


class ExitGraduation(models.Model):

    STATUS_CHOICES = [
        ("Graduated", "Graduated"),
        ("Ready for Exit", "Ready for Exit"),
        ("In Progress", "In Progress"),
    ]
    OUTCOME_CHOICES = [
        ("Employed", "Employed"),
        ("Self-sufficient", "Self-sufficient"),
        ("Business Owner", "Business Owner"),
        ("Pending", "Pending"),
    ]
    graduation_code = models.CharField(
        max_length=60, unique=True, blank=True, null=True
    )
    beneficiary = models.ForeignKey(
        "beneficiary.Beneficiary", on_delete=models.SET_NULL, null=True, blank=True
    )

    program = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    entry_date = models.DateField(null=True, blank=True)
    exit_date = models.DateField(null=True, blank=True)
    duration = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="In Progress",
        null=True,
        blank=True,
    )
    outcome = models.CharField(
        max_length=30, choices=OUTCOME_CHOICES, default="Pending", null=True, blank=True
    )
    satisfaction = models.PositiveIntegerField(
        null=True, blank=True, help_text="Rating from 1 to 5"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def save(self, *args, **kwargs):

        if not self.graduation_code:
            year = timezone.now().year

            last_record = (
                ExitGraduation.objects.filter(
                    graduation_code__startswith=f"GRAD-{year}"
                )
                .order_by("-id")
                .first()
            )

            if last_record:
                last_seq = int(last_record.graduation_code.split("-")[-1])
                sequence = str(last_seq + 1).zfill(4)
            else:
                sequence = "0001"

            self.graduation_code = f"GRAD-{year}-{sequence}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.graduation_code or self.pk} - {self.beneficiary or self.pk}"


class GraduationCriteria(models.Model):
    STATUS_CHOICES = [("Active", "Active"), ("Inactive", "Inactive")]
    program = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    criteria = models.CharField(max_length=255)
    weight = models.PositiveIntegerField(default=0)
    indicator = models.CharField(max_length=255, null=True, blank=True)
    measurement = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.criteria}"


class AlumniTracking(models.Model):
    STATUS_CHOICES = [
        ("Employed", "Employed"),
        ("Self-employed", "Self-employed"),
        ("Unemployed", "Unemployed"),
        ("In Training", "In Training"),
    ]
    beneficiary = models.ForeignKey(
        "beneficiary.Beneficiary", on_delete=models.SET_NULL, null=True, blank=True
    )
    graduation_date = models.DateField(null=True, blank=True)
    program = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    current_status = models.CharField(
        max_length=50, choices=STATUS_CHOICES, null=True, blank=True
    )
    income_change = models.CharField(max_length=50, null=True, blank=True)
    last_contact = models.DateField(null=True, blank=True)
    follow_up_interval = models.CharField(max_length=50, null=True, blank=True)
    needs_support = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"Alumni - {self.beneficiary}"


class ProgressTracking(models.Model):
    beneficiary = models.ForeignKey(
        "beneficiary.Beneficiary", on_delete=models.SET_NULL, null=True, blank=True
    )
    program = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    enrolled_date = models.DateField(null=True, blank=True)
    milestones_total = models.PositiveIntegerField(default=0)
    milestones_completed = models.PositiveIntegerField(default=0)
    progress = models.PositiveIntegerField(default=0, help_text="Percentage 0-100")
    current_phase = models.CharField(max_length=100, null=True, blank=True)
    next_milestone = models.CharField(max_length=255, null=True, blank=True)
    target_graduation = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"Progress - {self.beneficiary} ({self.progress}%)"
