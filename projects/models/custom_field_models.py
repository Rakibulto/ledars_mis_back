from django.db import models
from authentication.models import User
from .space_models import Space


class CustomField(models.Model):
    FIELD_TYPE_CHOICES = (
        ("text", "Text"),
        ("number", "Number"),
        ("date", "Date"),
        ("dropdown", "Dropdown"),
        ("checkbox", "Checkbox"),
        ("url", "URL"),
        ("email", "Email"),
        ("phone", "Phone"),
        ("currency", "Currency"),
        ("rating", "Rating"),
        ("label", "Label"),
        ("relationship", "Relationship"),
    )

    name = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)
    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name="custom_fields",
        null=True,
        blank=True,
    )
    required = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.field_type})"


class CustomFieldOption(models.Model):
    """Options for dropdown-type custom fields."""

    field = models.ForeignKey(
        CustomField, on_delete=models.CASCADE, related_name="options"
    )
    label = models.CharField(max_length=255)
    color = models.CharField(max_length=20, null=True, blank=True)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]


class TaskCustomFieldValue(models.Model):
    """Stores the value of a custom field for a specific task."""

    task = models.ForeignKey(
        "projects.Task", on_delete=models.CASCADE, related_name="custom_field_values"
    )
    field = models.ForeignKey(CustomField, on_delete=models.CASCADE)
    value = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ["task", "field"]
