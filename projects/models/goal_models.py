from django.db import models
from authentication.models import User


class Goal(models.Model):
    GOAL_TYPE_CHOICES = (
        ("company", "Company"),
        ("team", "Team"),
        ("personal", "Personal"),
    )
    TARGET_TYPE_CHOICES = (
        ("number", "Number"),
        ("percentage", "Percentage"),
        ("currency", "Currency"),
        ("boolean", "Yes/No"),
    )
    STATUS_CHOICES = (
        ("on_track", "On Track"),
        ("at_risk", "At Risk"),
        ("behind", "Behind"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="pm_goals"
    )
    goal_type = models.CharField(
        max_length=20, choices=GOAL_TYPE_CHOICES, default="team"
    )
    target_type = models.CharField(
        max_length=20, choices=TARGET_TYPE_CHOICES, default="number"
    )
    target_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    current_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="on_track")
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sub_goals",
    )

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="pm_goals_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def progress(self):
        if self.target_value == 0:
            return 0
        return min(int((self.current_value / self.target_value) * 100), 100)


class KeyResult(models.Model):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="key_results")
    name = models.CharField(max_length=255)
    target = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    current = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return self.name

    @property
    def progress(self):
        if self.target == 0:
            return 0
        return min(int((self.current / self.target) * 100), 100)
