from decimal import Decimal

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone


class ProjectManagementSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class Currency(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    code = models.CharField(max_length=10, unique=True, help_text="ISO currency code, e.g. USD")
    name = models.CharField(max_length=100, blank=True)
    symbol = models.CharField(max_length=10, blank=True)
    exchange_rate = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        default=1,
        help_text="Exchange rate relative to the base currency (1 unit of this currency = rate * base).",
    )
    base_currency = models.CharField(
        max_length=10,
        blank=True,
        help_text="Reference/base currency code this rate is expressed against, e.g. BDT.",
    )
    decimal_places = models.PositiveSmallIntegerField(default=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)


class ProjectManagementExpenseSequence(models.Model):
    key = models.CharField(max_length=32, unique=True, default="expense")
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.key} - {self.last_number}"


class ProjectManagementUnit(models.Model):
    """Lookup units used by project plan sub-activities (not traditional UOM)."""

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    status = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_project_management_units",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProjectManagementProject(models.Model):
    PROJECT_TYPE_CHOICES = (
        ("Development", "Development"),
        ("Emergency", "Emergency"),
        ("Livelihood", "Livelihood"),
        ("Education", "Education"),
        ("Health", "Health"),
        ("Protection", "Protection"),
        ("WASH", "WASH"),
        ("Nutrition", "Nutrition"),
        ("Shelter", "Shelter"),
        ("Other", "Other"),
    )
    IMPLEMENTATION_TYPE_CHOICES = (
        ("Direct", "Direct"),
        ("Partner", "Partner"),
        ("Consortium", "Consortium"),
    )
    STATUS_CHOICES = (
        ("Draft", "Draft"),
        ("Planning", "Planning"),
        ("Active", "Active"),
        ("On Hold", "On Hold"),
        ("Completed", "Completed"),
        ("Closed", "Closed"),
    )
    REPORTING_FREQUENCY_CHOICES = (
        ("Weekly", "Weekly"),
        ("Monthly", "Monthly"),
        ("Quarterly", "Quarterly"),
        ("Biannual", "Biannual"),
        ("Annual", "Annual"),
    )
    RISK_LEVEL_CHOICES = (
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
        ("Critical", "Critical"),
    )

    code = models.CharField(max_length=40, unique=True, blank=True)
    title = models.CharField(max_length=255)
    short_name = models.CharField(max_length=120, blank=True)
    donor = models.ForeignKey(
        "donor.Donor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_projects",
    )
    project_type = models.JSONField(default=list, blank=True)
    implementation_type = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    duration_months = models.PositiveIntegerField(default=0)
    budget_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    budget = models.ForeignKey(
        "procurement.Budget",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_management_projects",
        help_text="Linked procurement budget for this project plan expenditure",
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )
    project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_project_management_projects",
    )
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="assigned_project_management_projects",
        blank=True,
    )
    sector = models.CharField(max_length=120, blank=True)
    location = models.CharField(max_length=255, blank=True)
    # List of vulnerability type names selected as target beneficiaries
    target_beneficiaries = models.JSONField(default=list, blank=True)
    background = models.TextField(blank=True)
    objectives = models.TextField(blank=True)
    expected_outcomes = models.TextField(blank=True)
    monitoring_plan = models.TextField(blank=True)
    reporting_frequency = models.CharField(
        max_length=20,
        choices=REPORTING_FREQUENCY_CHOICES,
        default="Monthly",
    )
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES, default="Medium")
    notes = models.TextField(blank=True)
    # Deprecated: this field is no longer used. Will be removed in a future migration.
    materials_expense = models.OneToOneField(
        "ProjectManagementExpense",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materials_project",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_project_management_projects",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def currency_code(self):
        return self.currency.code if self.currency_id else "BDT"

    def save(self, *args, **kwargs):
        is_new = self._state.adding

        if not self.project_type:
            self.project_type = ["Development"]
        if not self.implementation_type:
            self.implementation_type = ["Direct"]
        if self.target_beneficiaries is None:
            self.target_beneficiaries = []

        if not self.code:
            current_year = timezone.now().year
            with transaction.atomic():
                sequence, _ = ProjectManagementSequence.objects.select_for_update().get_or_create(
                    year=current_year,
                    defaults={"last_number": 0},
                )
                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])
                self.code = f"NGO-{current_year}-{sequence.last_number:04d}"

        if self.start_date and self.end_date and self.end_date >= self.start_date:
            month_delta = (self.end_date.year - self.start_date.year) * 12 + (
                self.end_date.month - self.start_date.month
            )
            self.duration_months = month_delta + 1

        super().save(*args, **kwargs)

        if is_new and self.donor_id and self.budget_amount:
            from donor.models import DonorLedger
            DonorLedger.objects.create(
                donor_id=self.donor_id,
                transaction_date=self.start_date or timezone.now().date(),
                transaction_type="donation",
                amount=self.budget_amount,
                currency=self.currency.code if self.currency else "BDT",
                reference=self.code,
                description=f"Project budget allocated: {self.title}",
                related_project=self,
            )
        

    @property
    def planned_cost(self):
        return self.materials.aggregate(total=Sum("estimated_total_cost"))["total"] or Decimal("0")

    @property
    def committed_amount(self):
        return self.expenses.filter(status="Approved").aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

    @property
    def spent_amount(self):
        return self.expenses.filter(status="Paid").aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

    @property
    def remaining_budget(self):
        return (self.budget_amount or Decimal("0")) - self.spent_amount

    @property
    def budget_utilization_pct(self):
        budget = self.budget_amount or Decimal("0")
        if budget > 0:
            return (self.spent_amount / budget) * Decimal("100")
        return Decimal("0")

    def budget_summary(self):
        return {
            "budget": self.budget_amount or Decimal("0"),
            "planned": self.planned_cost,
            "committed": self.committed_amount,
            "spent": self.spent_amount,
            "remaining": self.remaining_budget,
            "utilization_pct": self.budget_utilization_pct,
        }


class ProjectManagementProjectPlan(models.Model):
    STATUS_CHOICES = (
        ("Pending", "Pending"),
        ("In Progress", "In Progress"),
        ("On Hold", "On Hold"),
        ("Completed", "Completed"),
    )
    APPROVAL_STATUS_CHOICES = (
        ("Pending Approval", "Pending Approval"),
        ("Approved", "Approved"),
    )

    project = models.ForeignKey(
        ProjectManagementProject,
        on_delete=models.CASCADE,
        related_name="plans",
    )
    serial_no = models.PositiveIntegerField()
    # Display/hierarchy code for main plan (e.g. "1", "2"). Sub plans use "{code}.{n}".
    serial_code = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    duration_days = models.PositiveIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default="Pending Approval",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_project_management_project_plans",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="assigned_project_management_project_plans",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["serial_no", "id"]
        unique_together = ("project", "serial_no")

    def __str__(self):
        return f"{self.project.title} - Step {self.serial_no}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")

        if not self.serial_code and self.serial_no:
            self.serial_code = str(self.serial_no)
            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.add("serial_code")
                kwargs["update_fields"] = list(update_fields)

        if self.status != "Completed":
            self.approval_status = "Pending Approval"
            self.approved_by = None
            self.approved_at = None

            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.update({"approval_status", "approved_by", "approved_at"})
                kwargs["update_fields"] = list(update_fields)

        super().save(*args, **kwargs)

    def mark_approved(self, user):
        self.approval_status = "Approved"
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=["approval_status", "approved_by", "approved_at", "updated_at"])

    def sync_status_from_work_items(self):
        work_items = list(self.work_items.all())
        if not work_items:
            return

        states = {item.state for item in work_items}

        if states == {"Done"}:
            new_status = "Completed"
        elif self.status == "On Hold":
            new_status = "On Hold"
        elif "Doing" in states or "Done" in states:
            new_status = "In Progress"
        else:
            new_status = "Pending"

        if self.status != new_status:
            self.status = new_status
            self.save(update_fields=["status", "updated_at"])


class ProjectManagementPlanSubPlan(models.Model):
    """Nested plan step under a main ProjectManagementProjectPlan."""

    plan = models.ForeignKey(
        ProjectManagementProjectPlan,
        on_delete=models.CASCADE,
        related_name="sub_plans",
    )
    serial_code = models.CharField(max_length=40)
    title = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    unit_type = models.CharField(max_length=50, blank=True)
    unit_no = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=1)
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="assigned_project_management_plan_sub_plans",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        unique_together = ("plan", "serial_code")

    def __str__(self):
        return f"{self.serial_code} - {self.title or 'Sub plan'}"

    def save(self, *args, **kwargs):
        unit_no = self.unit_no if self.unit_no is not None else 0
        unit_cost = self.unit_cost if self.unit_cost is not None else 0
        self.cost = unit_no * unit_cost

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("cost")
            kwargs["update_fields"] = list(update_fields)

        super().save(*args, **kwargs)


class ProjectManagementSubPlanUnitPeriod(models.Model):
    """
    Date-range unit distribution for a sub activity.
    Each row: start_date → end_date with unit_no for that span.
    Weekly / monthly / yearly expenditure views aggregate from these ranges.
  """

    PERIOD_RANGE = "range"
    PERIOD_MONTHLY = "monthly"  # legacy
    PERIOD_WEEKLY = "weekly"  # legacy
    PERIOD_YEARLY = "yearly"  # legacy
    PERIOD_TYPE_CHOICES = (
        (PERIOD_RANGE, "Date range"),
        (PERIOD_MONTHLY, "Monthly"),
        (PERIOD_WEEKLY, "Weekly"),
        (PERIOD_YEARLY, "Yearly"),
    )

    sub_plan = models.ForeignKey(
        ProjectManagementPlanSubPlan,
        on_delete=models.CASCADE,
        related_name="unit_periods",
    )
    period_type = models.CharField(
        max_length=16, choices=PERIOD_TYPE_CHOICES, default=PERIOD_RANGE
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    year = models.PositiveIntegerField(default=0)
    month = models.PositiveIntegerField(default=0)
    week = models.PositiveIntegerField(default=0)
    unit_no = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_date", "year", "month", "week", "id"]

    def __str__(self):
        if self.start_date and self.end_date:
            return f"{self.sub_plan.serial_code} {self.start_date} → {self.end_date}: {self.unit_no}"
        label = f"{self.year}"
        if self.month:
            label += f"-{self.month:02d}"
        if self.week:
            label += f" W{self.week}"
        return f"{self.sub_plan.serial_code} {label}: {self.unit_no}"


class ProjectManagementPlanWorkItem(models.Model):
    STATE_CHOICES = (
        ("Todo", "Todo"),
        ("Doing", "Doing"),
        ("Done", "Done"),
    )
    APPROVAL_STATUS_CHOICES = (
        ("Pending Approval", "Pending Approval"),
        ("Approved", "Approved"),
    )

    plan = models.ForeignKey(
        ProjectManagementProjectPlan,
        on_delete=models.CASCADE,
        related_name="work_items",
    )
    title = models.CharField(max_length=255)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default="Todo")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_management_plan_work_items",
    )
    notes = models.TextField(blank=True)
    issues = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_end_date = models.DateField(null=True, blank=True)
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default="Pending Approval",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_project_management_plan_work_items",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.plan} - {self.title}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")

        if self.state == "Done" and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.state != "Done":
            self.completed_at = None
            self.approval_status = "Pending Approval"
            self.approved_by = None
            self.approved_at = None

            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.update({"approval_status", "approved_by", "approved_at", "completed_at"})
                kwargs["update_fields"] = list(update_fields)

        super().save(*args, **kwargs)

    def mark_approved(self, user):
        self.approval_status = "Approved"
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=["approval_status", "approved_by", "approved_at", "updated_at"])


class ProjectManagementPlanAttachment(models.Model):
    plan = models.ForeignKey(
        ProjectManagementProjectPlan,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    work_item = models.ForeignKey(
        ProjectManagementPlanWorkItem,
        on_delete=models.CASCADE,
        related_name="attachments",
        null=True,
        blank=True,
    )
    file = models.FileField(
        upload_to="project_managements/task_attachments/%Y/%m/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "doc",
                    "docx",
                    "xls",
                    "xlsx",
                    "csv",
                    "txt",
                    "jpg",
                    "jpeg",
                    "png",
                    "webp",
                    "zip",
                ]
            )
        ],
    )
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_management_plan_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.plan} - {self.display_name}"

    @property
    def display_name(self):
        return self.original_name or self.file.name.rsplit("/", 1)[-1]

    def save(self, *args, **kwargs):
        if self.work_item_id and not self.plan_id:
            self.plan = self.work_item.plan
        if self.file and not self.original_name:
            self.original_name = self.file.name.rsplit("/", 1)[-1]
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        stored_file = self.file
        super().delete(*args, **kwargs)
        if stored_file:
            stored_file.delete(save=False)


class ProjectManagementProjectMaterial(models.Model):
    project = models.ForeignKey(
        ProjectManagementProject,
        on_delete=models.CASCADE,
        related_name="materials",
    )
    plan = models.ForeignKey(
        ProjectManagementProjectPlan,
        on_delete=models.SET_NULL,
        related_name="materials",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=40, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    estimated_unit_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    estimated_total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    preferred_vendor = models.CharField(max_length=255, blank=True)
    required_by = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.estimated_total_cost = (self.quantity or 0) * (self.estimated_unit_cost or 0)
        super().save(*args, **kwargs)

    @property
    def actual_spent(self):
        return self.expense_items.aggregate(total=Sum("line_total"))["total"] or Decimal("0")

    @property
    def variance(self):
        return (self.estimated_total_cost or Decimal("0")) - self.actual_spent


class ProjectManagementExpense(models.Model):
    STATUS_CHOICES = (
        ("Draft", "Draft"),
        ("Submitted", "Submitted"),
        ("Approved", "Approved"),
        ("Paid", "Paid"),
        ("Rejected", "Rejected"),
    )

    invoice_number = models.CharField(max_length=32, unique=True, blank=True)
    project = models.ForeignKey(
        ProjectManagementProject,
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    plan = models.ForeignKey(
        ProjectManagementProjectPlan,
        on_delete=models.SET_NULL,
        related_name="expenses",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    vendor_name = models.CharField(max_length=255, blank=True)
    expense_date = models.DateField(default=timezone.localdate)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="Draft")
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_project_management_expenses",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_project_management_expenses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-created_at", "-id"]

    def __str__(self):
        return self.invoice_number or self.title

    @property
    def currency_code(self):
        return self.currency.code if self.currency_id else "BDT"

    def save(self, *args, **kwargs):
        if self.plan_id and self.plan.project_id != self.project_id:
            self.project = self.plan.project

        if not self.invoice_number:
            with transaction.atomic():
                sequence, _ = ProjectManagementExpenseSequence.objects.select_for_update().get_or_create(
                    key="expense",
                    defaults={"last_number": 0},
                )
                sequence.last_number += 1
                sequence.save(update_fields=["last_number"])
                self.invoice_number = f"EXP-{sequence.last_number:04d}"

        super().save(*args, **kwargs)

    def recalculate_total(self, save=True):
        total = sum(item.line_total for item in self.items.all())
        self.total_amount = total
        if save:
            self.save(update_fields=["total_amount", "updated_at"])
        return total

    def transition_status(self, next_status, user=None):
        allowed_transitions = {
            "Draft": {"Submitted", "Rejected"},
            "Submitted": {"Approved", "Rejected", "Draft"},
            "Approved": {"Paid", "Rejected"},
            "Paid": set(),
            "Rejected": {"Draft", "Submitted"},
        }

        current_status = self.status or "Draft"
        if next_status == current_status:
            return

        if next_status not in dict(self.STATUS_CHOICES):
            raise ValueError("Invalid expense status.")

        if next_status not in allowed_transitions.get(current_status, set()):
            raise ValueError(f"Cannot transition expense from {current_status} to {next_status}.")

        now = timezone.now()
        self.status = next_status

        if next_status == "Submitted":
            self.submitted_at = now
        elif next_status == "Approved":
            self.approved_at = now
            self.approved_by = user
        elif next_status == "Paid":
            self.paid_at = now
            if user and not self.approved_by:
                self.approved_by = user
            # Auto-create donor ledger debit entry
            if self.project and self.project.donor_id:
                from donor.models import DonorLedger
                DonorLedger.objects.create(
                    donor_id=self.project.donor_id,
                    transaction_date=now.date(),
                    transaction_type="debit",
                    amount=self.total_amount,
                    currency=self.currency.code if self.currency else "BDT",
                    reference=self.invoice_number,
                    description=f"Expense paid: {self.title}",
                    related_project=self.project,
                    created_by=user,
                )
        elif next_status == "Draft":
            self.approved_by = None
            self.approved_at = None
            self.paid_at = None
        elif next_status == "Rejected":
            self.paid_at = None

        self.save(
            update_fields=[
                "status",
                "submitted_at",
                "approved_at",
                "paid_at",
                "approved_by",
                "updated_at",
            ]
        )


class ProjectManagementExpenseItem(models.Model):
    expense = models.ForeignKey(
        ProjectManagementExpense,
        on_delete=models.CASCADE,
        related_name="items",
    )
    material = models.ForeignKey(
        "ProjectManagementProjectMaterial",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_items",
    )
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or 0) * (self.unit_price or 0)
        super().save(*args, **kwargs)


class Advance(models.Model):
    CAUSE_OF_ADVANCE_CHOICES = (
        ("Field Work", "Field Work"),
        ("Training", "Training"),
        ("Procurement", "Procurement"),
        ("Travel", "Travel"),
        ("Emergency", "Emergency"),
        ("Other", "Other"),
    )
    RECEIVE_MEDIUM_CHOICES = (
        ("cheque", "Cheque"),
        ("direct", "Direct"),
    )
    CHECK_CHOICES = (
        ("tick", "✓ Tick"),
        ("cross", "✗ Cross"),
    )

    from_employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="advances_from",
    )
    from_text = models.TextField(blank=True, help_text="Rich text content for the 'From' block")
    to_text = models.TextField(blank=True, help_text="Rich text content for the 'To' block")
    project = models.ForeignKey(
        ProjectManagementProject,
        on_delete=models.CASCADE,
        related_name="advances",
    )
    cause_of_advance = models.CharField(
        max_length=40,
        choices=CAUSE_OF_ADVANCE_CHOICES,
        default="Other",
    )
    advance_receivable_date = models.DateField()
    advance_receivable_amount = models.DecimalField(max_digits=15, decimal_places=2)
    amount_in_words = models.CharField(max_length=500, blank=True, editable=False)
    expected_date = models.DateField()
    receive_medium = models.CharField(
        max_length=10,
        choices=RECEIVE_MEDIUM_CHOICES,
        default="direct",
    )
    bank_name = models.CharField(max_length=255, blank=True)
    cheque_no = models.CharField(max_length=100, blank=True)
    accountant_remarks = models.TextField(blank=True)
    check_outstanding = models.CharField(
        max_length=5, choices=CHECK_CHOICES, null=True, blank=True
    )
    check_adjusted = models.CharField(
        max_length=5, choices=CHECK_CHOICES, null=True, blank=True
    )
    check_completed = models.CharField(
        max_length=5, choices=CHECK_CHOICES, null=True, blank=True
    )
    signature_recipient = models.ImageField(
        upload_to="advance_signatures/", blank=True, null=True
    )
    signature_accountant = models.ImageField(
        upload_to="advance_signatures/", blank=True, null=True
    )
    signature_recommender = models.ImageField(
        upload_to="advance_signatures/", blank=True, null=True
    )
    signature_approver = models.ImageField(
        upload_to="advance_signatures/", blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        employee_name = self.from_employee.username if self.from_employee else "Unknown"
        return f"Advance - {employee_name} - {self.advance_receivable_date}"

    def save(self, *args, **kwargs):
        from .utils import number_to_words
        if self.advance_receivable_amount is not None:
            self.amount_in_words = number_to_words(self.advance_receivable_amount)
        super().save(*args, **kwargs)
