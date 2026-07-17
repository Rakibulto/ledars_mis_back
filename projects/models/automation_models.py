"""ClickUp-style automation engine models."""

from django.db import models
from authentication.models import User
from .space_models import Space


class Automation(models.Model):
    TRIGGER_CHOICES = (
        ("status_changed", "When status changes"),
        ("task_created", "When task is created"),
        ("task_assigned", "When task is assigned"),
        ("tag_added", "When tag is added"),
        ("due_date_passed", "When due date passes"),
        ("priority_changed", "When priority changes"),
        ("scheduled", "Every day at a specific time"),
        ("moved_to_list", "When moved to a list"),
        ("task_completed", "When task is completed"),
        ("comment_added", "When comment is added"),
    )

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name="automations",
        null=True,
        blank=True,
    )

    trigger_type = models.CharField(max_length=30, choices=TRIGGER_CHOICES)
    trigger_config = models.JSONField(default=dict, blank=True)
    conditions = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True)
    runs = models.IntegerField(default=0)
    last_run = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class AutomationAction(models.Model):
    ACTION_CHOICES = (
        ("change_status", "Change Status"),
        ("assign_user", "Assign to User"),
        ("add_tag", "Add Tag"),
        ("remove_tag", "Remove Tag"),
        ("set_priority", "Set Priority"),
        ("send_notification", "Send Notification"),
        ("move_to_list", "Move to List"),
        ("create_subtask", "Create Subtask"),
        ("add_comment", "Add Comment"),
        ("set_due_date", "Set Due Date"),
        ("send_email", "Send Email"),
    )

    automation = models.ForeignKey(
        Automation, on_delete=models.CASCADE, related_name="actions"
    )
    action_type = models.CharField(max_length=30, choices=ACTION_CHOICES)
    action_config = models.JSONField(default=dict, blank=True)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"{self.automation.name} → {self.action_type}"


class AutomationLog(models.Model):
    STATUS_CHOICES = (
        ("success", "Success"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
    )

    automation = models.ForeignKey(
        Automation, on_delete=models.CASCADE, related_name="logs"
    )
    task = models.ForeignKey(
        "projects.Task", on_delete=models.SET_NULL, null=True, blank=True
    )
    trigger_type = models.CharField(max_length=30)
    actions_executed = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="success")
    error_message = models.TextField(null=True, blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-executed_at"]
