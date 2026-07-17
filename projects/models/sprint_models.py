from django.db import models
from authentication.models import User
from .space_models import Space


class Sprint(models.Model):
    STATUS_CHOICES = (
        ("planning", "Planning"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    name = models.CharField(max_length=255)
    goal = models.TextField(null=True, blank=True)
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="sprints")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planning")
    velocity = models.IntegerField(default=0)

    # Retrospective
    went_well = models.TextField(null=True, blank=True)
    to_improve = models.TextField(null=True, blank=True)
    action_items = models.TextField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def total_tasks(self):
        return self.sprint_tasks.count()

    @property
    def completed_tasks(self):
        return self.sprint_tasks.filter(task__status__group__name="done").count()

    @property
    def total_points(self):
        return sum(
            st.task.story_points for st in self.sprint_tasks.select_related("task")
        )

    @property
    def completed_points(self):
        return sum(
            st.task.story_points
            for st in self.sprint_tasks.select_related("task").filter(
                task__status__group__name="done"
            )
        )


class SprintTask(models.Model):
    sprint = models.ForeignKey(
        Sprint, on_delete=models.CASCADE, related_name="sprint_tasks"
    )
    task = models.ForeignKey(
        "projects.Task", on_delete=models.CASCADE, related_name="sprint_memberships"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["sprint", "task"]
