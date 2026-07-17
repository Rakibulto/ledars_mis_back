"""Core project models — keeps the existing Project + ProjectActivity tables."""

from django.db import models, transaction
from django.utils import timezone
from authentication.models import User


class ProjectSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)


class Project(models.Model):
    STATUS_CHOICES = (
        ("Planning", "Planning"),
        ("Active", "Active"),
        ("On Hold", "On Hold"),
        ("Completed", "Completed"),
    )

    code = models.CharField(max_length=100)
    name = models.CharField(max_length=255, null=True, blank=True)
    donor = models.ForeignKey(
        "donor.Donor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )
    budget = models.ForeignKey(
        "procurement.Budget",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    manager = models.CharField(max_length=255, null=True, blank=True)

    location = models.JSONField(default=list, blank=True)
    objectives = models.JSONField(default=list, blank=True)
    activity_list = models.JSONField(default=list, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or self.code

    def save(self, *args, **kwargs):
        if not self.code:
            current_year = timezone.now().year
            with transaction.atomic():
                seq, _ = ProjectSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                seq.last_number += 1
                seq.save(update_fields=["last_number"])
                self.code = f"PRJ-{current_year}-{seq.last_number:04d}"
        super().save(*args, **kwargs)


class ProjectActivity(models.Model):
    TYPE_CHOICES = (
        ("Monthly", "Monthly"),
        ("Quarterly", "Quarterly"),
        ("Annual", "Annual"),
        ("One-time", "One-time"),
    )
    STATUS_CHOICES = (
        ("Not Started", "Not Started"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Overdue", "Overdue"),
        ("Cancelled", "Cancelled"),
    )
    PRIORITY_CHOICES = (
        ("High", "High"),
        ("Medium", "Medium"),
        ("Low", "Low"),
    )

    project = models.ForeignKey(
        Project, related_name="activities", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="Monthly")
    responsible_person = models.CharField(max_length=255, null=True, blank=True)
    department = models.ForeignKey(
        "employee.Employee", on_delete=models.SET_NULL, null=True, blank=True
    )

    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Not Started"
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="Medium"
    )
    progress = models.PositiveIntegerField(default=0)
    budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.name} - {self.title}"
