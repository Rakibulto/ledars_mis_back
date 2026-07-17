from django.db import models, transaction
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.utils import timezone


class PRFSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class PaymentRequisition(models.Model):
    """Payment Requisition Form (PRF) for requesting payment to vendors."""

    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Submitted", "Submitted"),
        ("Pending Approval", "Pending Approval"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("Processing", "Processing"),
        ("Paid", "Paid"),
    ]

    PRIORITY_CHOICES = [
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
        ("Urgent", "Urgent"),
    ]

    prf_number = models.CharField(max_length=50, unique=True, blank=True)
    work_order = models.ForeignKey(
        "procurement.WorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_requisitions",
    )
    grn = models.ForeignKey(
        "procurement.GoodsReceiptNote",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_requisitions",
    )
    grns = models.ManyToManyField(
        "procurement.GoodsReceiptNote",
        blank=True,
        related_name="payment_requisition_groups",
    )
    supplier = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.CASCADE,
        related_name="payment_requisitions",
    )
    invoice_number = models.CharField(max_length=100, null=True, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    invoice_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    budget_code = models.ForeignKey(
        "procurement.Budget", on_delete=models.SET_NULL, null=True, blank=True
    )
    account_code = models.ForeignKey(
        "procurement.Account", on_delete=models.SET_NULL, null=True, blank=True
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    department = models.ForeignKey(
        "employee.Department", on_delete=models.SET_NULL, null=True, blank=True
    )
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="Medium"
    )
    purpose = models.TextField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")

    attachment = models.FileField(
        upload_to="payment_requisitions/", null=True, blank=True
    )

    payment_method = models.CharField(max_length=50, null=True, blank=True)
    finance_remarks = models.TextField(null=True, blank=True)
    tentative_payment_schedule_date = models.DateField(null=True, blank=True)
    grn_checkbox = models.BooleanField(default=False)

    approver = models.ForeignKey(
        "employee.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_payment_requisitions",
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payment_requisitions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def calculate_net_amount(self):
        self.net_amount = self.total_amount - self.tax_amount
        self.save(update_fields=["net_amount"])

    def save(self, *args, **kwargs):
        if not self.prf_number:
            current_year = timezone.now().year
            with transaction.atomic():
                sequence, _ = PRFSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])
                self.prf_number = f"PRF-{current_year}-{sequence.last_number:04d}"
        self.net_amount = self.total_amount - self.tax_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.prf_number} - {self.supplier}"


class PaymentRequisitionItem(models.Model):
    """Line items in a payment requisition."""

    payment_requisition = models.ForeignKey(
        PaymentRequisition, on_delete=models.CASCADE, related_name="prf_items"
    )
    description = models.CharField(max_length=500, null=True, blank=True)
    item = models.ForeignKey(
        "inventory.Item", on_delete=models.SET_NULL, null=True, blank=True
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.payment_requisition.prf_number} - {self.description or self.item}"
        )
