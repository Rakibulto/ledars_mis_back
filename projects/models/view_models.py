from django.db import models
from authentication.models import User


class SavedView(models.Model):
    VIEW_TYPE_CHOICES = (
        ("list", "List"),
        ("board", "Board"),
        ("table", "Table"),
        ("calendar", "Calendar"),
        ("gantt", "Gantt"),
        ("timeline", "Timeline"),
    )

    name = models.CharField(max_length=255)
    view_type = models.CharField(
        max_length=20, choices=VIEW_TYPE_CHOICES, default="list"
    )
    filters = models.JSONField(default=dict, blank=True)
    sort = models.JSONField(default=dict, blank=True)
    group_by = models.CharField(max_length=50, null=True, blank=True)
    columns = models.JSONField(default=list, blank=True)
    is_default = models.BooleanField(default=False)
    is_shared = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pm_saved_views"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.view_type})"
