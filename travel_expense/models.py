import os
from django.conf import settings
from django.db import models


def travel_expense_upload_to(instance, filename):
    return f"travel_expense/attachments/{filename}"


class TravelExpenseAttachment(models.Model):
    travel_expense = models.ForeignKey(
        'TravelExpense',
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    row_index = models.IntegerField(default=0)
    file = models.FileField(upload_to=travel_expense_upload_to, blank=True, null=True)
    original_name = models.CharField(max_length=255, blank=True, default='')
    file_size = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['row_index', 'uploaded_at']

    def __str__(self):
        return f"Attachment for row {self.row_index}: {self.original_name}"


class TravelExpense(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
    ]

    project = models.CharField(max_length=255, blank=True, null=True)
    date_of_submission = models.DateField(blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    designation = models.CharField(max_length=255, blank=True, null=True)
    purpose = models.TextField(blank=True, null=True)

    expense_rows = models.JSONField(default=list, blank=True, null=True)

    total_travel_fare = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True, null=True)
    total_food = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True, null=True)
    total_lodging = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True, null=True)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True, null=True)

    note = models.TextField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    prepared_received_signature = models.JSONField(null=True, blank=True)
    checked_by_signature = models.JSONField(null=True, blank=True)
    accountant_signature = models.JSONField(null=True, blank=True)
    approved_by_signature = models.JSONField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_travel_expenses',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.project or 'N/A'}"
