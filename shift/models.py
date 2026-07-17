from django.db import models

# Create your models here.


class Shift(models.Model):
    """Stores shift timings for employees."""

    name = models.CharField(max_length=100, unique=True)
    office_start_time = models.TimeField(null=True, blank=True)
    office_end_time = models.TimeField(null=True, blank=True)
    office_start_time_consideration = models.IntegerField(
        null=True, blank=True, default=10
    )
    office_end_time_consideration = models.IntegerField(
        null=True, blank=True, default=10
    )

    check_in_start_time = models.TimeField(null=True, blank=True)
    check_in_end_time = models.TimeField(null=True, blank=True)
    check_out_start_time = models.TimeField(null=True, blank=True)
    check_out_end_time = models.TimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return f" {self.name} ({self.office_start_time} - {self.office_end_time})"
