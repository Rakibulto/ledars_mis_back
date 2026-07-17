from django.db import models
from django.utils import timezone


class DonorReport(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Submitted", "Submitted"),
        ("Approved", "Approved"),
        ("Overdue", "Overdue"),
    ]
    donor = models.CharField(max_length=255, null=True, blank=True)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    period = models.CharField(max_length=50, null=True, blank=True)
    beneficiaries_reached = models.PositiveIntegerField(default=0)
    target = models.PositiveIntegerField(default=0)
    achievement = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True
    )
    budget_utilized = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    budget_total = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.donor} - {self.project}"


class DuplicateRecord(models.Model):
    STATUS_CHOICES = [
        ("Pending Review", "Pending Review"),
        ("Merged", "Merged"),
        ("Not Duplicate", "Not Duplicate"),
        ("Flagged", "Flagged"),
    ]
    record_a = models.CharField(max_length=50, null=True, blank=True)
    record_b = models.CharField(max_length=50, null=True, blank=True)
    name_a = models.CharField(max_length=255, null=True, blank=True)
    name_b = models.CharField(max_length=255, null=True, blank=True)
    nid_match = models.BooleanField(default=False)
    contact_match = models.BooleanField(default=False)
    similarity_score = models.PositiveIntegerField(default=0)
    auto_detected = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Pending Review"
    )
    detected_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"Duplicate: {self.record_a} vs {self.record_b}"


class AttendanceTracker(models.Model):
    activity = models.CharField(max_length=255, null=True, blank=True)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    location = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    registered = models.PositiveIntegerField(default=0)
    attended = models.PositiveIntegerField(default=0)
    attendance_rate = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True
    )
    facilitator = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.activity} - {self.date}"


class HouseholdSurvey(models.Model):
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Completed", "Completed"),
        ("Draft", "Draft"),
    ]
    reference = models.CharField(max_length=50, unique=True, blank=True)
    survey_name = models.CharField(max_length=255)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    target_households = models.PositiveIntegerField(default=0)
    completed = models.PositiveIntegerField(default=0)
    completion_rate = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    data_quality_score = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().year
            last = (
                HouseholdSurvey.objects.filter(reference__startswith=f"HS-{year}")
                .order_by("-id")
                .first()
            )
            seq = int(last.reference.split("-")[-1]) + 1 if last else 1
            self.reference = f"HS-{year}-{str(seq).zfill(4)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.survey_name


class EligibilityScreening(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("Under Review", "Under Review"),
    ]
    applicant = models.CharField(max_length=255, null=True, blank=True)
    nid = models.CharField(max_length=50, null=True, blank=True)
    screening_date = models.DateField(null=True, blank=True)
    program = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    criteria_met = models.PositiveIntegerField(default=0)
    criteria_total = models.PositiveIntegerField(default=0)
    score = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    eligible = models.BooleanField(default=False)
    screener = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"Screening - {self.applicant}"
