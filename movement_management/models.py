from django.conf import settings
from django.db import models


class MovementManagement(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
    ]

    name = models.CharField(max_length=255)
    designation = models.CharField(max_length=255)
    grade = models.CharField(max_length=100, blank=True, default='')
    purpose_of_travel = models.TextField()
    project_name = models.JSONField(default=list, blank=True)

    schedule_rows = models.JSONField(default=list, blank=True)

    subtotal_travel = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    subtotal_food = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    subtotal_lodging = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    subtotal_others = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    submitted_by_signature = models.JSONField(null=True, blank=True)
    checked_supervised_signature = models.JSONField(null=True, blank=True)
    approved_by_signature = models.JSONField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_movements',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        projects = self.project_name
        if isinstance(projects, list):
            return f"{self.name} - {', '.join(projects) if projects else 'No Project'}"
        return f"{self.name} - {projects or 'No Project'}"
