from django.db import models
from authentication.models import User
from .space_models import Space
from .list_models import List


class Form(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    space = models.ForeignKey(
        Space, on_delete=models.CASCADE, related_name="forms", null=True, blank=True
    )
    target_list = models.ForeignKey(
        List, on_delete=models.SET_NULL, null=True, blank=True, related_name="forms"
    )
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False)
    submissions_count = models.IntegerField(default=0)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class FormField(models.Model):
    FIELD_TYPE_CHOICES = (
        ("text", "Short Text"),
        ("textarea", "Long Text"),
        ("number", "Number"),
        ("date", "Date"),
        ("dropdown", "Dropdown"),
        ("checkbox", "Checkbox"),
        ("email", "Email"),
        ("url", "URL"),
        ("file", "File Upload"),
        ("rating", "Rating"),
    )

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="fields")
    label = models.CharField(max_length=255)
    field_type = models.CharField(
        max_length=20, choices=FIELD_TYPE_CHOICES, default="text"
    )
    required = models.BooleanField(default=False)
    options = models.JSONField(default=list, blank=True)
    placeholder = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]


class FormSubmission(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="submissions")
    data = models.JSONField(default=dict)
    task_created = models.ForeignKey(
        "projects.Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="form_submissions",
    )
    submitted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]
