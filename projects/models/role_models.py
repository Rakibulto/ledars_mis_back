from django.db import models
from authentication.models import User


class PMRole(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)

    # Permissions
    can_create_tasks = models.BooleanField(default=True)
    can_edit_tasks = models.BooleanField(default=True)
    can_delete_tasks = models.BooleanField(default=False)
    can_manage_sprints = models.BooleanField(default=False)
    can_manage_members = models.BooleanField(default=False)
    can_manage_spaces = models.BooleanField(default=False)
    can_manage_automations = models.BooleanField(default=False)
    can_manage_custom_fields = models.BooleanField(default=False)
    can_manage_settings = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=True)
    can_manage_goals = models.BooleanField(default=False)
    can_manage_docs = models.BooleanField(default=True)
    can_track_time = models.BooleanField(default=True)
    can_export_data = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PMUserRole(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pm_user_roles"
    )
    role = models.ForeignKey(
        PMRole, on_delete=models.CASCADE, related_name="pm_role_users"
    )

    class Meta:
        unique_together = ["user", "role"]

    def __str__(self):
        return f"{self.user} - {self.role.name}"
