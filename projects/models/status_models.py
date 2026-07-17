from django.db import models
from authentication.models import User
from .space_models import Space


class StatusGroup(models.Model):
    """Groups like 'active', 'done', 'closed'."""

    name = models.CharField(max_length=50)
    label = models.CharField(max_length=100)
    color = models.CharField(max_length=20, default="#6366f1")
    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name="status_groups",
        null=True,
        blank=True,
    )
    is_default = models.BooleanField(default=False)
    position = models.IntegerField(default=0)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return self.label


class Status(models.Model):
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=20, default="#94a3b8")
    group = models.ForeignKey(
        StatusGroup, on_delete=models.CASCADE, related_name="statuses"
    )
    space = models.ForeignKey(
        Space, on_delete=models.CASCADE, related_name="statuses", null=True, blank=True
    )
    position = models.IntegerField(default=0)
    is_default = models.BooleanField(default=False)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return self.name
