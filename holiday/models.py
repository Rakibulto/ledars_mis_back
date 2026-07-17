from django.db import models
from employee.models import Branch, Department, Designation, Employee


# Holiday model to manage holidays with flexible assignment options for global and granular allocation.
class Holiday(models.Model):
    """
    Model to manage holidays with flexible assignment options for global and granular allocation.
    Supports filtering by branch, designation, department, employment type, and individual employees.
    Supports both single-day and multi-day holidays with from_date and to_date.
    """

    name = models.CharField(
        max_length=100, help_text="Name of the holiday (e.g., Eid-ul-Fitr, Christmas)"
    )
    from_date = models.DateField(help_text="Start date of the holiday")
    to_date = models.DateField(help_text="End date of the holiday")
    description = models.TextField(
        blank=True, null=True, help_text="Optional description of the holiday"
    )
    is_global = models.BooleanField(
        default=True,
        help_text="If true, holiday applies to all employees unless exceptions are specified",
    )

    # Granular Filtering Fields
    branches = models.ManyToManyField(
        Branch,
        blank=True,
        related_name="holidays",
        help_text="Specific branches to which this holiday applies (if not global)",
    )
    designations = models.ManyToManyField(
        Designation,
        blank=True,
        related_name="holidays",
        help_text="Specific designations to which this holiday applies (if not global)",
    )
    departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name="holidays",
        help_text="Specific departments to which this holiday applies (if not global)",
    )
    employment_types = models.ForeignKey(
        "leave.LeaveGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Employment types to which this holiday applies (if not global). If null, applies to all.",
    )

    # Specific Employee Assignments and Exceptions
    assigned_employees = models.ManyToManyField(
        Employee,
        blank=True,
        related_name="assigned_holidays",
        help_text="Specific employees assigned to this holiday (used for granular assignment)",
    )
    excluded_employees = models.ManyToManyField(
        Employee,
        blank=True,
        related_name="excluded_holidays",
        help_text="Employees explicitly excluded from this holiday",
    )

    # System Fields
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        unique_together = ("name", "from_date", "to_date")
        verbose_name = "Holiday"
        verbose_name_plural = "Holidays"

    def __str__(self):
        if self.from_date == self.to_date:
            return f"{self.name} - {self.from_date.strftime('%Y-%m-%d')}"
        return f"{self.name} - {self.from_date.strftime('%Y-%m-%d')} to {self.to_date.strftime('%Y-%m-%d')}"

    def validate_dates(self):
        """
        Ensure to_date is not before from_date.
        """
        if self.to_date < self.from_date:
            raise ValueError("to_date cannot be earlier than from_date")

    def save(self, *args, **kwargs):
        """
        Validate dates before saving.
        """
        self.validate_dates()
        super().save(*args, **kwargs)

    def is_applicable_to_employee(self, employee):
        """
        Determine if the holiday applies to a specific employee based on global settings,
        granular filters, and exceptions.

        Logic:
        - If holiday is global, it applies to all employees (unless excluded)
        - If holiday is not global, filters are combined with OR logic:
          - If assigned_employees is specified, employee must be in that list
          - Otherwise, employee must match ANY of the specified criteria:
            branches OR designations OR departments OR employment_types
        """
        # Check if employee is explicitly excluded
        if self.excluded_employees.filter(pk=employee.pk).exists():
            return False

        # If holiday is global, it applies unless excluded
        if self.is_global:
            return True

        # Check if employee is specifically assigned - this takes priority
        has_assigned_employees = self.assigned_employees.exists()
        if has_assigned_employees:
            return self.assigned_employees.filter(pk=employee.pk).exists()

        # Collect which filters are specified and whether employee matches each
        has_branch_filter = self.branches.exists()
        has_designation_filter = self.designations.exists()
        has_department_filter = self.departments.exists()
        has_employment_type_filter = self.employment_types is not None

        # If no filters are specified, the holiday does not apply
        if not (
            has_branch_filter
            or has_designation_filter
            or has_department_filter
            or has_employment_type_filter
        ):
            return False

        # Check each filter - employee must match ALL specified filters (AND logic)
        # If a filter is specified but employee lacks the attribute, they don't match

        # Branch filter check
        if has_branch_filter:
            if not employee.location:
                return False  # Employee has no branch, can't match branch filter
            if not self.branches.filter(pk=employee.location.pk).exists():
                return False  # Employee's branch not in holiday's branches

        # Designation filter check
        if has_designation_filter:
            if not employee.designation:
                return (
                    False  # Employee has no designation, can't match designation filter
                )
            if not self.designations.filter(pk=employee.designation.pk).exists():
                return False  # Employee's designation not in holiday's designations

        # Department filter check
        if has_department_filter:
            if not employee.department:
                return (
                    False  # Employee has no department, can't match department filter
                )
            if not self.departments.filter(pk=employee.department.pk).exists():
                return False  # Employee's department not in holiday's departments

        # Employment type filter check
        if has_employment_type_filter:
            if employee.employment_type != self.employment_types:
                return False  # Employee's employment type doesn't match

        # Employee passed all specified filters
        return True
