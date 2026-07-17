from django.db import models
from django.utils import timezone


class ComplaintsFeedback(models.Model):
    TYPE_CHOICES = [
        ("Complaint", "Complaint"),
        ("Feedback", "Feedback"),
        ("Suggestion", "Suggestion"),
    ]
    STATUS_CHOICES = [
        ("Open", "Open"),
        ("Closed", "Closed"),
        ("Under Review", "Under Review"),
    ]
    PRIORITY_CHOICES = [
        ("Critical", "Critical"),
        ("High", "High"),
        ("Medium", "Medium"),
        ("Low", "Low"),
    ]
    beneficiary = models.ForeignKey(
        "beneficiary.Beneficiary",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaints_feedbacks",
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, null=True, blank=True)
    category = models.CharField(max_length=255, null=True, blank=True)
    subject = models.CharField(max_length=255, null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Open")
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="Medium"
    )
    satisfaction = models.IntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.subject or self.pk}"


class GrievanceRedressal(models.Model):
    STATUS_CHOICES = [
        ("Open", "Open"),
        ("Under Investigation", "Under Investigation"),
        ("Resolved", "Resolved"),
        ("Closed", "Closed"),
    ]
    reference = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField(null=True, blank=True)
    complainant = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    assigned_to = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Open")
    resolution = models.TextField(null=True, blank=True)
    resolution_date = models.DateField(null=True, blank=True)
    days_to_resolve = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().year
            last = (
                GrievanceRedressal.objects.filter(reference__startswith=f"GR-{year}")
                .order_by("-id")
                .first()
            )
            seq = int(last.reference.split("-")[-1]) + 1 if last else 1
            self.reference = f"GR-{year}-{str(seq).zfill(4)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.reference


class SatisfactionSurvey(models.Model):
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Completed", "Completed"),
        ("Draft", "Draft"),
    ]
    survey_name = models.CharField(max_length=255)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    period = models.CharField(max_length=50, null=True, blank=True)
    respondents = models.PositiveIntegerField(default=0)
    avg_satisfaction = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True
    )
    response_rate = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    key_findings = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.survey_name
