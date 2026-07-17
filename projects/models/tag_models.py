from django.db import models
from authentication.models import User
from .space_models import Space


class Tag(models.Model):
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=20, default="#94a3b8")
    space = models.ForeignKey(
        Space, on_delete=models.CASCADE, related_name="tags", null=True, blank=True
    )

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TaskTag(models.Model):
    task = models.ForeignKey(
        "projects.Task", on_delete=models.CASCADE, related_name="task_tags"
    )
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="tagged_tasks")

    class Meta:
        unique_together = ["task", "tag"]
