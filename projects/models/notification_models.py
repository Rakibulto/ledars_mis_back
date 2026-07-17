from django.db import models
from authentication.models import User


class PMNotification(models.Model):
    TYPE_CHOICES = (
        ("task_assigned", "Task Assigned"),
        ("task_completed", "Task Completed"),
        ("comment_added", "Comment Added"),
        ("mention", "Mentioned"),
        ("due_date", "Due Date Reminder"),
        ("overdue", "Task Overdue"),
        ("status_changed", "Status Changed"),
        ("sprint_started", "Sprint Started"),
        ("sprint_ended", "Sprint Ended"),
        ("goal_updated", "Goal Updated"),
        ("approval", "Approval Required"),
    )

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pm_notifications"
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    link = models.CharField(max_length=500, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # Generic reference
    reference_type = models.CharField(max_length=50, null=True, blank=True)
    reference_id = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_type}: {self.title}"
