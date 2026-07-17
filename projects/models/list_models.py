from django.db import models
from authentication.models import User
from .space_models import Space


class List(models.Model):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="lists")
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    color = models.CharField(max_length=20, null=True, blank=True)
    position = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="pm_lists"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return self.name

    @property
    def tasks_count(self):
        return self.tasks.count()
