from django.db import models
from authentication.models import User
from .space_models import Space


class Milestone(models.Model):
    STATUS_CHOICES = (
        ("upcoming", "Upcoming"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("overdue", "Overdue"),
    )

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    space = models.ForeignKey(
        Space, on_delete=models.CASCADE, related_name="milestones"
    )
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="upcoming")
    color = models.CharField(max_length=20, default="#6366f1")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["target_date"]

    def __str__(self):
        return self.name

    @property
    def tasks_count(self):
        return self.milestone_tasks.count()

    @property
    def completed_tasks_count(self):
        return self.milestone_tasks.filter(task__status__group__name="done").count()

    @property
    def progress(self):
        total = self.tasks_count
        if total == 0:
            return 0
        return int((self.completed_tasks_count / total) * 100)


class MilestoneTask(models.Model):
    milestone = models.ForeignKey(
        Milestone, on_delete=models.CASCADE, related_name="milestone_tasks"
    )
    task = models.ForeignKey(
        "projects.Task", on_delete=models.CASCADE, related_name="milestone_memberships"
    )

    class Meta:
        unique_together = ["milestone", "task"]
