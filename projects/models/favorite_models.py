from django.db import models
from authentication.models import User


class Favorite(models.Model):
    TYPE_CHOICES = (
        ("space", "Space"),
        ("list", "List"),
        ("task", "Task"),
        ("doc", "Doc"),
        ("dashboard", "Dashboard"),
        ("view", "View"),
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pm_favorites"
    )
    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    item_id = models.IntegerField()
    name = models.CharField(max_length=255, null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "item_type", "item_id"]
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user} ★ {self.item_type}:{self.item_id}"
