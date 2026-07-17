import uuid
from django.db import models, transaction
from django.utils import timezone
from authentication.models import User
from .list_models import List
from .status_models import Status


class TaskSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)


class Task(models.Model):
    PRIORITY_CHOICES = (
        ("urgent", "Urgent"),
        ("high", "High"),
        ("normal", "Normal"),
        ("low", "Low"),
        ("none", "None"),
    )

    task_id = models.CharField(max_length=30, unique=True, editable=False)
    title = models.CharField(max_length=500)
    description = models.TextField(null=True, blank=True)

    list = models.ForeignKey(List, on_delete=models.CASCADE, related_name="tasks")
    status = models.ForeignKey(
        Status, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks"
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="normal"
    )

    start_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    time_estimate = models.IntegerField(
        default=0, help_text="Estimated time in minutes"
    )
    story_points = models.IntegerField(default=0)
    position = models.IntegerField(default=0)

    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )

    # Recurring task support
    is_recurring = models.BooleanField(default=False)
    recurring_config = models.JSONField(null=True, blank=True)

    # Custom fields JSON store
    custom_fields = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="pm_tasks_created"
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pm_tasks_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "-created_at"]

    def __str__(self):
        return f"{self.task_id} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.task_id:
            current_year = timezone.now().year
            with transaction.atomic():
                seq, _ = TaskSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                seq.last_number += 1
                seq.save(update_fields=["last_number"])
                self.task_id = f"TASK-{seq.last_number}"
        super().save(*args, **kwargs)

    @property
    def subtask_count(self):
        return self.children.count()

    @property
    def subtask_done(self):
        return self.children.filter(status__group__name="done").count()

    @property
    def checklist_count(self):
        return ChecklistItem.objects.filter(checklist__task=self).count()

    @property
    def checklist_done(self):
        return ChecklistItem.objects.filter(checklist__task=self, is_done=True).count()

    @property
    def comment_count(self):
        return self.comments.count()

    @property
    def attachment_count(self):
        return self.attachments.count()


class TaskAssignee(models.Model):
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="task_assignees"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pm_task_assignments"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["task", "user"]

    def __str__(self):
        return f"{self.user} → {self.task.task_id}"


class TaskWatcher(models.Model):
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="task_watchers"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pm_task_watches"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["task", "user"]


class TaskDependency(models.Model):
    DEPENDENCY_TYPES = (
        ("blocking", "Blocking"),
        ("blocked_by", "Blocked By"),
        ("related", "Related"),
    )

    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="dependencies_from"
    )
    depends_on = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="dependencies_to"
    )
    dependency_type = models.CharField(
        max_length=20, choices=DEPENDENCY_TYPES, default="blocking"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["task", "depends_on"]


class Subtask(models.Model):
    """Simple inline subtask (not a full Task child, just a checklist-like item on a task)."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=500)
    is_done = models.BooleanField(default=False)
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]


class Checklist(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="checklists")
    name = models.CharField(max_length=255)
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return self.name


class ChecklistItem(models.Model):
    checklist = models.ForeignKey(
        Checklist, on_delete=models.CASCADE, related_name="items"
    )
    text = models.CharField(max_length=500)
    is_done = models.BooleanField(default=False)
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="pm/task_attachments/%Y/%m/")
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(default=0)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="pm_comments"
    )
    text = models.TextField()
    mentions = models.JSONField(default=list, blank=True)
    reactions = models.JSONField(default=list, blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment on {self.task.task_id}"


class TaskActivityLog(models.Model):
    ACTION_CHOICES = (
        ("created", "Created"),
        ("status_changed", "Status Changed"),
        ("priority_changed", "Priority Changed"),
        ("assigned", "Assigned"),
        ("unassigned", "Unassigned"),
        ("comment_added", "Comment Added"),
        ("attachment_added", "Attachment Added"),
        ("due_date_changed", "Due Date Changed"),
        ("moved", "Moved"),
        ("tag_added", "Tag Added"),
        ("tag_removed", "Tag Removed"),
        ("description_updated", "Description Updated"),
        ("title_updated", "Title Updated"),
        ("time_tracked", "Time Tracked"),
        ("checklist_updated", "Checklist Updated"),
        ("dependency_added", "Dependency Added"),
        ("completed", "Completed"),
        ("reopened", "Reopened"),
    )

    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="activity_logs"
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    field = models.CharField(max_length=100, null=True, blank=True)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} on {self.task.task_id}"
