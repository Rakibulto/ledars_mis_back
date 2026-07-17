from django.db import models, transaction
from django.utils import timezone


class AwardSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class Award(models.Model):
    """Contract award to a vendor after comparative statement approval."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("pending_notification", "Pending Notification"),
        ("notified", "Notified"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("cancelled", "Cancelled"),
        ("Draft", "Draft (legacy)"),
        ("Pending Notification", "Pending Notification (legacy)"),
        ("Notified", "Notified (legacy)"),
        ("Accepted", "Accepted (legacy)"),
        ("Declined", "Declined (legacy)"),
        ("Cancelled", "Cancelled (legacy)"),
    ]

    NOTIFICATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]

    ACCEPTANCE_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
    ]

    DELIVERY_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in-progress", "In Progress"),
        ("delivered", "Delivered"),
        ("partial", "Partial"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("partial", "Partial"),
        ("paid", "Paid"),
    ]

    award_number = models.CharField(max_length=50, unique=True, blank=True)
    comparative_statement = models.ForeignKey(
        "procurement.ComparativeStatement",
        on_delete=models.CASCADE,
        related_name="awards",
    )
    rfq = models.ForeignKey(
        "procurement.RFQ",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="awards",
    )
    vendor_profile = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="awards",
    )

    # Core info
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    # Financial
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    approved_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Dates
    award_date = models.DateField(null=True, blank=True)
    notification_date = models.DateField(null=True, blank=True)
    response_deadline = models.DateField(null=True, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    acceptance_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)

    # Contract details
    validity_period = models.CharField(max_length=100, null=True, blank=True)
    delivery_timeline = models.CharField(max_length=255, null=True, blank=True)
    delivery_address = models.TextField(null=True, blank=True)
    payment_terms = models.TextField(null=True, blank=True)
    warranty_period = models.CharField(max_length=100, null=True, blank=True)
    justification = models.TextField(null=True, blank=True)
    terms_and_conditions = models.TextField(null=True, blank=True)

    # Status fields
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="active")
    notification_status = models.CharField(
        max_length=20, choices=NOTIFICATION_STATUS_CHOICES, default="pending"
    )
    acceptance_status = models.CharField(
        max_length=20, choices=ACCEPTANCE_STATUS_CHOICES, default="pending"
    )
    delivery_status = models.CharField(
        max_length=20, choices=DELIVERY_STATUS_CHOICES, default="pending"
    )
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )

    # Delivery tracking
    delivery_progress = models.IntegerField(default=0)
    total_items = models.IntegerField(default=0)
    delivered_items = models.IntegerField(default=0)

    # Structured JSON fields
    items = models.JSONField(null=True, blank=True)  # list of item dicts
    terms = models.JSONField(null=True, blank=True)  # list of condition strings
    delivery_schedule = models.JSONField(null=True, blank=True)  # list of phase dicts
    organization_info = models.JSONField(
        null=True, blank=True
    )  # org name/contact/address
    contact_info = models.JSONField(null=True, blank=True)  # procurement contact

    awarded_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="given_awards",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        previous_acceptance_status = None
        if self.pk:
            try:
                previous_acceptance_status = Award.objects.values_list(
                    "acceptance_status", flat=True
                ).get(pk=self.pk)
            except Award.DoesNotExist:
                previous_acceptance_status = None

        if self.acceptance_status == "accepted" and not self.acceptance_date:
            if previous_acceptance_status != "accepted":
                self.acceptance_date = timezone.now().date()

        if not self.award_number:
            current_year = timezone.now().year
            with transaction.atomic():
                sequence, _ = AwardSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])
                self.award_number = f"AWD-{current_year}-{sequence.last_number:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.award_number} - {self.vendor_profile or self.rfq or self.id}"


class AwardNotification(models.Model):
    """Notification sent to vendor about award decision."""

    NOTIFICATION_TYPE_CHOICES = [
        ("Award", "Award"),
        ("Regret", "Regret"),
    ]

    award = models.ForeignKey(
        Award, on_delete=models.CASCADE, related_name="notifications"
    )
    vendor_profile = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.CASCADE,
        related_name="award_notifications",
    )
    notification_type = models.CharField(
        max_length=20, choices=NOTIFICATION_TYPE_CHOICES
    )
    sent_date = models.DateTimeField(null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    is_sent = models.BooleanField(default=False)
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_date = models.DateTimeField(null=True, blank=True)

    sent_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_type} - {self.vendor_profile} - {self.award.award_number}"
