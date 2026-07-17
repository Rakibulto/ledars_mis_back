from django.db import models
from authentication.models import User


class Dashboard(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pm_dashboards"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DashboardWidget(models.Model):
    WIDGET_TYPE_CHOICES = (
        ("task_status", "Task Status Chart"),
        ("task_priority", "Task Priority Chart"),
        ("sprint_burndown", "Sprint Burndown"),
        ("sprint_velocity", "Sprint Velocity"),
        ("team_workload", "Team Workload"),
        ("time_tracking", "Time Tracking"),
        ("overdue_tasks", "Overdue Tasks"),
        ("recent_activity", "Recent Activity"),
        ("goal_progress", "Goal Progress"),
        ("milestone_timeline", "Milestone Timeline"),
        ("custom", "Custom Widget"),
    )

    dashboard = models.ForeignKey(
        Dashboard, on_delete=models.CASCADE, related_name="widgets"
    )
    widget_type = models.CharField(max_length=30, choices=WIDGET_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    config = models.JSONField(default=dict, blank=True)
    position_x = models.IntegerField(default=0)
    position_y = models.IntegerField(default=0)
    width = models.IntegerField(default=6)
    height = models.IntegerField(default=4)

    class Meta:
        ordering = ["position_y", "position_x"]
