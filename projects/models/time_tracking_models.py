from django.db import models
from authentication.models import User


class TimeEntry(models.Model):
    task = models.ForeignKey(
        "projects.Task", on_delete=models.CASCADE, related_name="time_entries"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pm_time_entries"
    )
    description = models.TextField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0, help_text="Duration in minutes")
    date = models.DateField(null=True, blank=True)
    is_billable = models.BooleanField(default=False)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_running = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.task.task_id} ({self.duration}min)"

    @property
    def cost(self):
        if self.hourly_rate and self.duration:
            return float(self.hourly_rate) * (self.duration / 60)
        return 0
