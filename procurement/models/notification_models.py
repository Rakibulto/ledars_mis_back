from django.db import models


class ProcurementNotification(models.Model):
    """Notification system for procurement events."""

    TYPE_CHOICES = [
        ("Requisition", "Requisition"),
        ("RFQ", "RFQ"),
        ("Quotation", "Quotation"),
        ("Comparative", "Comparative Statement"),
        ("Award", "Award"),
        ("Work Order", "Work Order"),
        ("GRN", "GRN"),
        ("Payment", "Payment"),
        ("Treasury", "Treasury"),
        ("Approval", "Approval"),
        ("System", "System"),
    ]

    PRIORITY_CHOICES = [
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
        ("Urgent", "Urgent"),
    ]

    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="Medium"
    )
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    reference_type = models.CharField(max_length=50, null=True, blank=True)
    link = models.CharField(max_length=500, null=True, blank=True)

    recipient = models.ForeignKey(
        "authentication.User",
        on_delete=models.CASCADE,
        related_name="procurement_notifications",
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_type} - {self.title}"
