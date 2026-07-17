from django.db import models

from authentication.models import User


class Notification(models.Model):
    NOTIFICATION_TYPE = (
        ("attendance", "Attendance"),
        ("leave", "Leave"),
        ("attendance_adjustment", "Attendance Adjustment"),
        ("probation_period", "Probation Period"),
        ("payroll", "Payroll"),
    )
    STATUS = (
        ("Read", "Read"),
        ("Unread", "Unread"),
    )
    title = models.CharField(max_length=255, null=True, blank=True)
    notification_id = models.IntegerField(null=True, blank=True)
    type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE, default="leave")
    status = models.CharField(max_length=50, choices=STATUS, default="Unread")
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications_receiver",
        null=True,
        blank=True,
    )
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.type
