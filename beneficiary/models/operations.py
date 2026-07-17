from django.db import models
from django.utils import timezone


class TargetingCriteria(models.Model):
    TYPE_CHOICES = [
        ("Economic", "Economic"),
        ("Demographic", "Demographic"),
        ("Social", "Social"),
        ("Geographic", "Geographic"),
        ("Vulnerability", "Vulnerability"),
    ]
    STATUS_CHOICES = [("Active", "Active"), ("Inactive", "Inactive")]
    program = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    criterion = models.CharField(max_length=255)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, null=True, blank=True)
    weight = models.PositiveIntegerField(default=0)
    measurement = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.criterion


class DistributionPlan(models.Model):
    STATUS_CHOICES = [
        ("Planning", "Planning"),
        ("Approved", "Approved"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    ]
    reference = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    location = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    beneficiaries_targeted = models.PositiveIntegerField(default=0)
    items = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Planning")
    coordinator = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().year
            last = (
                DistributionPlan.objects.filter(reference__startswith=f"DP-{year}")
                .order_by("-id")
                .first()
            )
            seq = int(last.reference.split("-")[-1]) + 1 if last else 1
            self.reference = f"DP-{year}-{str(seq).zfill(4)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} - {self.name}"


class ServiceCalendarEvent(models.Model):
    STATUS_CHOICES = [
        ("Scheduled", "Scheduled"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    ]
    title = models.CharField(max_length=255)
    date = models.DateField(null=True, blank=True)
    type = models.CharField(max_length=100, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    beneficiaries = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Scheduled"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.title


class CaseWorkerAssignment(models.Model):
    case_worker = models.ForeignKey(
        "employee.Employee", on_delete=models.SET_NULL, null=True, blank=True
    )
    designation = models.CharField(max_length=100, null=True, blank=True)
    area = models.CharField(max_length=255, null=True, blank=True)
    active_cases = models.PositiveIntegerField(default=0)
    max_capacity = models.PositiveIntegerField(default=30)
    specialization = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.case_worker} - {self.area}"


class FollowUpSchedule(models.Model):
    TYPE_CHOICES = [
        ("Home Visit", "Home Visit"),
        ("Phone Call", "Phone Call"),
        ("Office Visit", "Office Visit"),
        ("Group Session", "Group Session"),
    ]
    STATUS_CHOICES = [
        ("Scheduled", "Scheduled"),
        ("Completed", "Completed"),
        ("Missed", "Missed"),
        ("Rescheduled", "Rescheduled"),
    ]
    PRIORITY_CHOICES = [
        ("Critical", "Critical"),
        ("High", "High"),
        ("Medium", "Medium"),
        ("Low", "Low"),
    ]
    beneficiary = models.ForeignKey(
        "beneficiary.Beneficiary", on_delete=models.SET_NULL, null=True, blank=True
    )
    case_worker = models.ForeignKey(
        "employee.Employee", on_delete=models.SET_NULL, null=True, blank=True
    )
    follow_up_date = models.DateField(null=True, blank=True)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, null=True, blank=True)
    purpose = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Scheduled"
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="Medium"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"Follow-up {self.beneficiary} - {self.follow_up_date}"
