from django.db import models
from authentication.models import User
from .core import Category
from .product import Product
from .warehouse import Warehouse, OperationType
from .operations import GRNLineItem


class QualityCheck(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Declined", "Declined"),
    ]
    TYPE_CHOICES = [
        ("Receipt", "Receipt Inspection"),
        ("Periodic", "Periodic Audit"),
        ("Return", "Return Inspection"),
        ("Random", "Random Sampling"),
    ]
    RESULT_CHOICES = [
        ("Pass", "Pass"),
        ("Fail", "Fail"),
        ("Conditional Pass", "Conditional Pass"),
    ]
    PRIORITY_CHOICES = [
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
        ("Critical", "Critical"),
    ]

    reference = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField()
    check_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default="Receipt"
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    grn_line = models.ForeignKey(
        GRNLineItem,
        related_name="quality_checks",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    office_location = models.ForeignKey(
        "procurement.OfficeManagement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_checks",
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True
    )
    team = models.ForeignKey(
        "QualityTeam", on_delete=models.SET_NULL, null=True, blank=True
    )
    inspector = models.CharField(max_length=150, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    result = models.CharField(
        max_length=20, choices=RESULT_CHOICES, null=True, blank=True
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="Medium"
    )
    findings = models.TextField(null=True, blank=True)
    corrective_actions = models.TextField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_quality_checks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.reference} - {self.status}"


class QualityAlert(models.Model):
    SEVERITY_CHOICES = [
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
        ("Critical", "Critical"),
    ]
    STATUS_CHOICES = [
        ("New", "New"),
        ("In Progress", "In Progress"),
        ("Resolved", "Resolved"),
    ]

    reference = models.CharField(max_length=50, unique=True, blank=True)
    title = models.CharField(max_length=200)
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    severity = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES, default="Medium"
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="New")
    description = models.TextField(null=True, blank=True)
    corrective_action = models.TextField(null=True, blank=True)
    reported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reported_quality_alerts",
    )
    office_location = models.ForeignKey(
        "procurement.OfficeManagement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_alerts",
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_quality_alerts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.reference} - {self.title}"


class QualityControlPoint(models.Model):
    FREQUENCY_CHOICES = [
        ("Daily", "Daily"),
        ("Weekly", "Weekly"),
        ("Monthly", "Monthly"),
        ("Per Batch", "Per Batch"),
    ]
    PRIORITY_CHOICES = [
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
        ("Critical", "Critical"),
    ]

    reference = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=200)
    office_location = models.ForeignKey(
        "procurement.OfficeManagement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_control_points",
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="quality_control_points",
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_control_points",
    )
    frequency = models.CharField(
        max_length=20, choices=FREQUENCY_CHOICES, default="Weekly"
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="Medium"
    )
    inspection_criteria = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    # Legacy fields kept for backward compatibility
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True
    )
    operation_type = models.ForeignKey(
        OperationType, on_delete=models.SET_NULL, null=True, blank=True
    )
    parameter = models.CharField(max_length=200, blank=True, default="")
    standard = models.CharField(max_length=200, blank=True, default="")
    tolerance = models.CharField(max_length=100, null=True, blank=True)
    is_mandatory = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_control_points",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.reference or self.name}"


class QualityTeam(models.Model):
    name = models.CharField(max_length=100)
    leader = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_quality_teams",
    )
    members = models.ManyToManyField(User, blank=True, related_name="quality_teams")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True
    )
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class QCTemplate(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True
    )
    checklist = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
