from django.db import models
from authentication.models import User
from .space_models import Space


class Doc(models.Model):
    title = models.CharField(max_length=500)
    content = models.TextField(null=True, blank=True)
    space = models.ForeignKey(
        Space, on_delete=models.CASCADE, related_name="docs", null=True, blank=True
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sub_pages",
    )
    is_favorite = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(
        User, blank=True, related_name="pm_shared_docs"
    )

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="pm_docs_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    @property
    def pages_count(self):
        return self.sub_pages.count()
