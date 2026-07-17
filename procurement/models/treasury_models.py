from django.db import models, transaction
from django.utils import timezone


class TreasurySequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class TreasuryProcessing(models.Model):
    """Finance review and treasury processing of payment requisitions."""

    STATUS_CHOICES = [
        ("Pending Review", "Pending Review"),
        ("Under Review", "Under Review"),
        ("Budget Verified", "Budget Verified"),
        ("Approved for Payment", "Approved for Payment"),
        ("Payment Scheduled", "Payment Scheduled"),
        ("Payment Processed", "Payment Processed"),
        ("On Hold", "On Hold"),
        ("Rejected", "Rejected"),
    ]

    processing_number = models.CharField(max_length=50, unique=True, blank=True)
    payment_requisition = models.ForeignKey(
        "procurement.PaymentRequisition",
        on_delete=models.CASCADE,
        related_name="treasury_processing",
    )
    budget_verified = models.BooleanField(default=False)
    budget_remarks = models.TextField(null=True, blank=True)
    finance_remarks = models.TextField(null=True, blank=True)
    approved_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    payment_scheduled_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="Pending Review"
    )

    reviewed_by = models.ForeignKey(
        "employee.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_treasury",
    )
    reviewed_date = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "employee.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_treasury",
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.processing_number:
            current_year = timezone.now().year
            with transaction.atomic():
                (
                    sequence,
                    _,
                ) = TreasurySequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])
                self.processing_number = (
                    f"TRS-{current_year}-{sequence.last_number:04d}"
                )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.processing_number}"


class PaymentRecord(models.Model):
    """Actual payment made to vendor via treasury."""

    PAYMENT_METHOD_CHOICES = [
        ("Bank Transfer", "Bank Transfer"),
        ("Cheque", "Cheque"),
        ("Cash", "Cash"),
        ("Mobile Banking", "Mobile Banking"),
    ]

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Processed", "Processed"),
        ("Completed", "Completed"),
        ("Failed", "Failed"),
        ("Reversed", "Reversed"),
    ]

    treasury_processing = models.ForeignKey(
        TreasuryProcessing, on_delete=models.CASCADE, related_name="payments"
    )
    supplier = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_records",
    )
    payment_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_method = models.CharField(
        max_length=30, choices=PAYMENT_METHOD_CHOICES, default="Bank Transfer"
    )
    reference_number = models.CharField(max_length=100, null=True, blank=True)
    bank_name = models.CharField(max_length=255, null=True, blank=True)
    account_number = models.CharField(max_length=100, null=True, blank=True)
    cheque_number = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    remarks = models.TextField(null=True, blank=True)

    processed_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment - {self.reference_number} - {self.amount}"


class PaymentTimeline(models.Model):
    """Timeline tracking of payment stages."""

    STAGE_CHOICES = [
        ("PRF Submitted", "PRF Submitted"),
        ("Finance Review", "Finance Review"),
        ("Budget Verified", "Budget Verified"),
        ("Approved for Payment", "Approved for Payment"),
        ("Payment Scheduled", "Payment Scheduled"),
        ("Payment Processed", "Payment Processed"),
        ("Payment Completed", "Payment Completed"),
    ]

    payment_requisition = models.ForeignKey(
        "procurement.PaymentRequisition",
        on_delete=models.CASCADE,
        related_name="timeline",
    )
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(null=True, blank=True)
    performed_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.payment_requisition.prf_number} - {self.stage}"
