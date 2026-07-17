from decimal import Decimal

from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.utils import timezone
from procurement.models.office_models import OfficeManagement


class DonorCode(models.Model):
    """Donor/funding source code for NGO projects (e.g. DNR-2026-001)."""

    code = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} – {self.name}"

    @classmethod
    def generate_code(cls):
        year = timezone.now().year
        prefix = f"DNR-{year}-"
        last = cls.objects.filter(code__startswith=prefix).order_by("code").last()
        if last:
            try:
                last_num = int(last.code.split("-")[-1])
            except (ValueError, IndexError):
                last_num = 0
            next_num = last_num + 1
        else:
            next_num = 1
        return f"{prefix}{next_num:03d}"


class MRSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class MaterialRequisition(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Pending Approval", "Pending Approval"),
        ("Finance Review", "Finance Review"),
        ("Final Approval", "Final Approval"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("Converted to RFQ", "Converted to RFQ"),
    ]

    PRIORITY_CHOICES = [
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
        ("Urgent", "Urgent"),
    ]

    requisition_no = models.CharField(max_length=50, unique=True, null=True, blank=True)
    department = models.ForeignKey(
        "employee.Department", on_delete=models.SET_NULL, null=True, blank=True
    )
    project = models.ForeignKey(
        "project_managements.ProjectManagementProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_requisitions",
    )
    donor_code = models.ForeignKey(
        "donor.Donor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_requisitions",
    )
    category = models.ForeignKey(
        "inventory.Category", on_delete=models.SET_NULL, null=True, blank=True
    )
    items = models.ManyToManyField(
        "inventory.Item",
        through="MaterialItem",
        related_name="material_requisitions",
        blank=True,
    )
    budget_code = models.ForeignKey(
        "procurement.Budget", on_delete=models.SET_NULL, null=True, blank=True
    )
    account_code = models.ForeignKey(
        "procurement.Account", on_delete=models.SET_NULL, null=True, blank=True
    )
    fiscal_year = models.CharField(max_length=50, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Draft", null=True, blank=True
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="Medium", null=True, blank=True
    )
    purpose = models.TextField(null=True, blank=True)

    # Section 4: Specifications & Details (requisition-level)
    specifications = models.TextField(null=True, blank=True)
    preferred_brand = models.CharField(max_length=255, null=True, blank=True)
    alternative_brands = models.CharField(max_length=255, null=True, blank=True)
    warranty_period = models.CharField(max_length=100, null=True, blank=True)
    country_of_origin = models.CharField(max_length=100, null=True, blank=True)
    quality_standards = models.TextField(null=True, blank=True)

    requesting_office = models.ForeignKey(
        OfficeManagement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requesting_requisitions",
    )
    delivery_location = models.ForeignKey(
        OfficeManagement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_requisitions",
    )
    delivery_date = models.DateField(null=True, blank=True)
    contact_person = models.CharField(max_length=100, null=True, blank=True)
    contact_phone = models.CharField(max_length=100, null=True, blank=True)
    special_instruction = models.TextField(null=True, blank=True)

    attachment = models.FileField(
        upload_to="material_requisitions/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "doc",
                    "docx",
                    "xls",
                    "xlsx",
                    "jpg",
                    "jpeg",
                    "png",
                    "svg",
                    "gif",
                    "webp",
                ]
            )
        ],
        null=True,
        blank=True,
    )
    approver1 = models.ForeignKey(
        "employee.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_requisitions_approver1",
    )
    approver2 = models.ForeignKey(
        "employee.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_requisitions_approver2",
    )

    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_material_requisitions",
    )
    updated_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_material_requisitions",
    )
    version = models.CharField(max_length=20, default="1.0", editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # AUTO CALCULATION METHOD
    def calculate_total_amount(self):
        total = Decimal("0")

        for line in self.material_items.select_related("item"):
            unit_price = (
                line.item.cost
                if line.item_id and line.item
                else line.requested_unit_price
            )
            total += Decimal(str(line.quantity or 0)) * (unit_price or Decimal("0"))

        MaterialRequisition.objects.filter(pk=self.pk).update(total_amount=total)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.version = "1.0"
        else:
            try:
                major, minor = self.version.split(".")
                self.version = f"{major}.{int(minor) + 1}"
            except (ValueError, AttributeError):
                self.version = "1.0"

        if not self.requisition_no:
            current_year = timezone.now().year

            with transaction.atomic():
                sequence, _ = MRSequence.objects.select_for_update().get_or_create(
                    year=current_year, defaults={"last_number": 0}
                )

                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])

                self.requisition_no = f"REQ-{current_year}-{sequence.last_number:04d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.requisition_no or self.pk}"


class MaterialItem(models.Model):
    material_requisition = models.ForeignKey(
        MaterialRequisition, on_delete=models.CASCADE, related_name="material_items"
    )
    item = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True)
    requested_item_name = models.CharField(max_length=255, null=True, blank=True)
    requested_item_description = models.TextField(null=True, blank=True)
    requested_unit = models.CharField(max_length=100, null=True, blank=True)
    requested_unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    remarks = models.CharField(max_length=500, null=True, blank=True)

    quantity = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    @property
    def is_manual_entry(self):
        return self.item_id is None and bool(self.requested_item_name)

    @property
    def effective_unit_price(self):
        """Used for total_price calculation — requested_unit_price takes priority."""
        if self.requested_unit_price:
            return self.requested_unit_price
        if self.item_id and self.item:
            return self.item.cost or Decimal("0")
        return Decimal("0")

    @property
    def inventory_unit_price(self):
        """Reference price from inventory item."""
        if self.item_id and self.item:
            return self.item.cost or Decimal("0")
        return None

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Auto update PR total
        if self.material_requisition:
            self.material_requisition.calculate_total_amount()

    def delete(self, *args, **kwargs):
        mr = self.material_requisition
        super().delete(*args, **kwargs)

        # Auto update after delete
        if mr:
            mr.calculate_total_amount()


class MaterialRequisitionAttachment(models.Model):
    material_requisition = models.ForeignKey(
        MaterialRequisition, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(
        upload_to="material_requisitions/attachments/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "doc",
                    "docx",
                    "xls",
                    "xlsx",
                    "jpg",
                    "jpeg",
                    "png",
                    "svg",
                    "gif",
                    "webp",
                ]
            )
        ],
    )
    uploaded_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def filename(self):
        return self.file.name.split("/")[-1] if self.file else None

    def __str__(self):
        return f"{self.material_requisition} - {self.filename or self.pk}"


class MaterialRequisitionStatusLog(models.Model):
    material_requisition = models.ForeignKey(
        MaterialRequisition, on_delete=models.CASCADE, related_name="status_logs"
    )
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20)
    action = models.CharField(max_length=100, null=True, blank=True)
    comments = models.TextField(null=True, blank=True)
    acted_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.material_requisition} {self.from_status or 'New'} -> {self.to_status}"


class MaterialRequisitionApprovalStep(models.Model):
    """Per-level, per-user approval tracking driven by ApprovalMatrix."""

    STEP_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Returned", "Returned"),
        ("Rejected", "Rejected"),
    ]

    APPROVAL_MODE_CHOICES = [
        ("any_approver", "Independent Approval"),
        ("all_approvers", "Unanimous Approval"),
    ]

    material_requisition = models.ForeignKey(
        MaterialRequisition,
        on_delete=models.CASCADE,
        related_name="approval_steps",
    )
    approval_level = models.PositiveIntegerField()
    approval_mode = models.CharField(
        max_length=20,
        choices=APPROVAL_MODE_CHOICES,
        default="all_approvers",
        help_text="Inherited from ApprovalMatrix at step creation time.",
    )
    approver = models.ForeignKey(
        "employee.Employee",
        on_delete=models.CASCADE,
        related_name="mr_approval_steps",
    )
    status = models.CharField(
        max_length=20, choices=STEP_STATUS_CHOICES, default="Pending"
    )
    comments = models.TextField(null=True, blank=True)
    acted_at = models.DateTimeField(null=True, blank=True)
    acted_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mr_step_actions",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["approval_level", "id"]
        unique_together = [("material_requisition", "approval_level", "approver")]

    def __str__(self):
        return (
            f"{self.material_requisition} – L{self.approval_level} "
            f"{self.approver} [{self.status}]"
        )
