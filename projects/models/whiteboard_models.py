from django.db import models
from authentication.models import User
from .space_models import Space


class Whiteboard(models.Model):
    name = models.CharField(max_length=255)
    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name="whiteboards",
        null=True,
        blank=True,
    )
    content = models.JSONField(default=dict, blank=True)
    thumbnail = models.ImageField(upload_to="pm/whiteboards/", null=True, blank=True)
    collaborators = models.ManyToManyField(
        User, blank=True, related_name="pm_whiteboards"
    )
    elements_count = models.IntegerField(default=0)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pm_whiteboards_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name
