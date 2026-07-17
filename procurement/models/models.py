from django.utils import timezone
from django.db import models, transaction
from authentication.models import User

# from inventory.models import Category
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from employee.models import Employee


class POSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class PurchaseOrder(models.Model):

    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Pending Approval", "Pending Approval"),
        ("Approved", "Approved"),
        ("Sent to Supplier", "Sent to Supplier"),
        ("Partially Received", "Partially Received"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    ]

    po_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    items = models.ManyToManyField(
        "inventory.Item", through="ItemPO", related_name="purchase_orders", blank=True
    )
    supplier = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.SET_NULL,
        null=True,
        related_name="purchase_orders",
    )
    delivery_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    approval_status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="Draft"
    )

    created_by = models.ForeignKey(
        "employee.Employee", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def calculate_total_amount(self):
        total = (
            self.po_items.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("quantity") * F("item__unit_price"),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                )
            )["total"]
            or 0
        )

        self.total_amount = total
        self.save(update_fields=["total_amount"])

    def save(self, *args, **kwargs):
        if not self.po_number:
            current_year = timezone.now().year
            with transaction.atomic():
                sequence, _ = POSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )
                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])
                self.po_number = f"PO-{current_year}-{sequence.last_number:03d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.po_number or self.pk} - {self.supplier or self.pk}"


class ItemPO(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="po_items"
    )
    item = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True)

    quantity = models.PositiveIntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Recalculate total amount after saving ItemPO
        if self.purchase_order:
            self.purchase_order.calculate_total_amount()

    def delete(self, *args, **kwargs):
        po = self.purchase_order
        super().delete(*args, **kwargs)
        # Recalculate total amount after deleting ItemPO
        if po:
            po.calculate_total_amount()


class PRSequence(models.Model):
    year = models.IntegerField(unique=True, db_index=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class PurchaseRequisition(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Submitted", "Submitted"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("PR Created", "PR Created"),
    ]
    pr_number = models.CharField(max_length=50, unique=True)
    department = models.ForeignKey(
        "employee.Department", on_delete=models.SET_NULL, null=True, blank=True
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    items = models.ManyToManyField(
        "inventory.Item",
        through="ItemPR",
        related_name="purchase_requisitions",
        blank=True,
    )
    estimated_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    approver = models.ForeignKey(
        "employee.Employee", on_delete=models.SET_NULL, null=True, blank=True
    )

    created_by = models.ForeignKey(
        "employee.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_purchase_requisitions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # AUTO CALCULATION METHOD
    def calculate_estimated_amount(self):
        total = (
            self.pr_items.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("quantity") * F("item__unit_price"),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                )
            )["total"]
            or 0
        )

        PurchaseRequisition.objects.filter(pk=self.pk).update(estimated_amount=total)

    def save(self, *args, **kwargs):
        if not self.pr_number:
            current_year = timezone.now().year

            with transaction.atomic():
                sequence, _ = PRSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )

                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])

                self.pr_number = f"PR-{current_year}-{sequence.last_number:04d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.pr_number or self.pk}"


class ItemPR(models.Model):
    purchase_requisition = models.ForeignKey(
        PurchaseRequisition, on_delete=models.CASCADE, related_name="pr_items"
    )
    item = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True)

    quantity = models.PositiveIntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Auto update PR total
        if self.purchase_requisition:
            self.purchase_requisition.calculate_estimated_amount()

    def delete(self, *args, **kwargs):
        pr = self.purchase_requisition
        super().delete(*args, **kwargs)

        # Auto update after delete
        if pr:
            pr.calculate_estimated_amount()



class ApprovalRequest(models.Model):
    TYPE_CHOICES = (
        ("Purchase Requisition", "Purchase Requisition"),
        ("Purchase Order", "Purchase Order"),
        ("Request For Quotation", "Request For Quotation"),
    )
    PRIORITY_CHOICES = (
        ("Normal", "Normal"),
        ("High", "High"),
        ("Urgent", "Urgent"),
    )
    STATUS_CHOICES = (
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
    )

    reference_number = models.CharField(max_length=100, unique=True, blank=True)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, null=True, blank=True)
    # 'yourapp.Department'
    department = models.CharField(max_length=100, null=True)
    # 'yourapp.Project'
    project = models.CharField(max_length=100, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="Normal"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="Pending")
    description = models.TextField(blank=True, null=True)
    current_approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_approvals",
    )

    approval_level = models.PositiveIntegerField(default=1)
    total_levels = models.PositiveIntegerField(default=1)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="approval_requests"
    )
    submitted_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):

        if not self.reference_number:
            year = timezone.now().year

            # Generate prefix from type (First letter of each word)
            prefix = "".join(word[0] for word in self.type.split()).upper()

            # Get last record of same type and year
            last_record = (
                ApprovalRequest.objects.filter(type=self.type, created_at__year=year)
                .order_by("-id")
                .first()
            )

            if last_record and last_record.reference_number:
                last_seq = int(last_record.reference_number.split("-")[-1])
                sequence = str(last_seq + 1).zfill(3)
            else:
                sequence = "001"

            self.reference_number = f"{prefix}-{year}-{sequence}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference_number} - {self.type}"


class ApprovalHistory(models.Model):

    ACTION_CHOICES = (
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("Returned", "Returned"),
    )
    approval_request = models.ForeignKey(
        ApprovalRequest, on_delete=models.CASCADE, related_name="approval_histories"
    )
    approver = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="approval_actions"
    )
    role = models.CharField(max_length=100)
    action = models.CharField(
        max_length=10, choices=ACTION_CHOICES, null=True, blank=True
    )
    comments = models.TextField(blank=True, null=True)
    level = models.PositiveIntegerField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.approval_request.reference_number} - {self.action} by {self.approver.username}"
