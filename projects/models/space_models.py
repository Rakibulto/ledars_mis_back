from django.db import models
from authentication.models import User
from .workspace_models import Workspace


class Space(models.Model):
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="spaces"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    color = models.CharField(max_length=20, default="#6366f1")
    icon = models.CharField(max_length=50, null=True, blank=True)
    is_private = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="pm_spaces"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def lists_count(self):
        return self.lists.count()

    @property
    def tasks_count(self):
        from .task_models import Task

        return Task.objects.filter(list__space=self).count()


class SpaceMember(models.Model):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("member", "Member"),
        ("viewer", "Viewer"),
    )

    space = models.ForeignKey(
        Space, on_delete=models.CASCADE, related_name="space_members"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="space_memberships"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["space", "user"]

    def __str__(self):
        return f"{self.user} - {self.space.name}"
