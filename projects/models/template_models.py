from django.db import models
from authentication.models import User
from .space_models import Space


class Template(models.Model):
    CATEGORY_CHOICES = (
        ("project", "Project"),
        ("task", "Task"),
        ("checklist", "Checklist"),
        ("doc", "Document"),
    )

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="task")
    industry = models.CharField(max_length=100, null=True, blank=True)
    space = models.ForeignKey(
        Space,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="templates",
    )
    content = models.JSONField(default=dict, blank=True)
    statuses = models.JSONField(default=list, blank=True)
    lists = models.JSONField(default=list, blank=True)
    usage_count = models.IntegerField(default=0)
    is_public = models.BooleanField(default=False)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-usage_count"]

    def __str__(self):
        return self.name
