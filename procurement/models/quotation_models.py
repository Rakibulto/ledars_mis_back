from decimal import Decimal

from django.db import models, transaction
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class QuotationSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class VendorQuotation(models.Model):
    """Vendor's response/bid to an RFQ with pricing details."""

    STATUS_CHOICES = [
        ("under_review", "Under Review"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    quotation_number = models.CharField(max_length=50, unique=True, blank=True)
    rfq = models.ForeignKey(
        "procurement.RFQ", on_delete=models.CASCADE, related_name="vendor_quotations"
    )
    vendor = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.CASCADE,
        related_name="quotations",
        null=True,
        blank=True,
    )
    submission_date = models.DateTimeField(null=True, blank=True)
    validity_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    delivery_terms = models.TextField(null=True, blank=True)
    payment_terms = models.TextField(null=True, blank=True)
    warranty_terms = models.TextField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="under_review"
    )

    # Price proposal data from ApplyRFQ
    price_proposal = models.JSONField(
        null=True, blank=True, help_text="Price proposal data copied from ApplyRFQ"
    )
    attachment = models.FileField(upload_to="quotations/", null=True, blank=True)

    # ── Direct evaluation fields ─ optional, no vendor-portal record required ──
    is_direct_evaluation = models.BooleanField(default=False)
    direct_vendor_name = models.CharField(max_length=255, null=True, blank=True)
    direct_vendor_email = models.EmailField(null=True, blank=True)
    direct_vendor_phone = models.CharField(max_length=50, null=True, blank=True)
    direct_vendor_address = models.TextField(null=True, blank=True)
    direct_evaluation_justification = models.TextField(null=True, blank=True)

    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_quotations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        # unique_together only enforced when vendor is set (NULL treated as
        # distinct in SQLite/PostgreSQL UNIQUE, but we enforce it via
        # validate_unique to be safe and support multiple direct evaluations).
        unique_together = ["rfq", "vendor"]

    def calculate_totals(self):
        total = (
            self.quotation_items.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("quantity") * F("unit_price"),
                        output_field=DecimalField(max_digits=15, decimal_places=2),
                    )
                )
            )["total"]
            or 0
        )

        self.total_amount = total
        discount = total * (self.discount_percentage / Decimal("100"))
        self.grand_total = total - discount + self.tax_amount
        self.save(update_fields=["total_amount", "grand_total"])

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            current_year = timezone.now().year
            with transaction.atomic():
                (
                    sequence,
                    _,
                ) = QuotationSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])
                self.quotation_number = f"QTN-{current_year}-{sequence.last_number:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quotation_number} - {self.vendor}"


class QuotationItem(models.Model):
    """Line item in a vendor quotation with pricing."""

    quotation = models.ForeignKey(
        VendorQuotation, on_delete=models.CASCADE, related_name="quotation_items"
    )
    item = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remarks = models.TextField(null=True, blank=True)

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.quotation:
            self.quotation.calculate_totals()

    def delete(self, *args, **kwargs):
        quotation = self.quotation
        super().delete(*args, **kwargs)
        if quotation:
            quotation.calculate_totals()

    def __str__(self):
        return f"{self.quotation.quotation_number} - {self.item}"


class QuotationOpening(models.Model):
    """Record of formal bid opening event."""

    STATUS_CHOICES = [
        ("Scheduled", "Scheduled"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    ]

    rfq = models.OneToOneField(
        "procurement.RFQ", on_delete=models.CASCADE, related_name="opening"
    )
    opening_date = models.DateTimeField()
    venue = models.CharField(max_length=255, null=True, blank=True)
    committee_members = models.ManyToManyField(
        "employee.Employee", blank=True, related_name="quotation_openings"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Scheduled"
    )
    minutes = models.TextField(null=True, blank=True)

    opened_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-opening_date"]

    def __str__(self):
        return f"Opening - {self.rfq.rfq_number}"


@receiver(post_save, sender=VendorQuotation)
def create_quotation_opening(sender, instance, created, **kwargs):
    """
    Automatically create a QuotationOpening when an RFQ's submission deadline has passed
    and there are submitted quotations, but no opening exists yet.
    """
    if instance.status == "Submitted" and instance.rfq.submission_deadline:
        now = timezone.now()
        if now > instance.rfq.submission_deadline and not hasattr(
            instance.rfq, "opening"
        ):
            QuotationOpening.objects.create(
                rfq=instance.rfq,
                opening_date=now,
                status="Scheduled",
            )
