from calendar import weekday
import math
from django.db import models
from django.db import transaction
from decimal import Decimal
from authentication.models import (
    User,
)
from notification.models import Notification
from shift.models import Shift
from leave.models import LeavePolicy
from django.utils import timezone


def upload_to_profile(instance, filename):
    return "assets/uploads/employee/image/{filename}".format(filename=filename)


def upload_to_signature(instance, filename):
    return "assets/uploads/employee/signature/{filename}".format(filename=filename)


class Department(models.Model):
    """Stores company departments."""

    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.name


class Designation(models.Model):
    """Stores job titles/designations."""

    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="designations"
    )
    name = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.name


class Branch(models.Model):
    """Stores company branches or locations."""

    name = models.CharField(max_length=100, unique=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.name


class Grade(models.Model):
    """Stores company grades."""

    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.name


class Nominee(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    relationship = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=100, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    percentage = models.FloatField(default=0, null=True, blank=True)

    def __str__(self):
        return self.name


class EmergencyContact(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    relationship = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=100, null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name


class Salary(models.Model):
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_salaries",
    )
    employee = models.ForeignKey(
        "Employee", on_delete=models.CASCADE, related_name="salaries"
    )
    effective_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date from which this salary structure is effective. "
        "Used by payroll to pick the correct salary for a given month.",
    )
    basic = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    house_rent = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    conveyance = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    medical = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    gross_salary = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    festival_bonus = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    absence_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    is_late_during_holiday = models.BooleanField(
        default=False,
        help_text="If true, late deduction will be applied even if the employee is late on a holiday or weekend",
    )
    late_count_threshold = models.PositiveIntegerField(
        default=3,
        help_text="Number of late arrivals allowed before late deduction is applied",
    )
    late_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    holiday_compensation = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    weekday_compensation = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    performance_bonus = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    tax_percentage = models.IntegerField(
        blank=True,
        null=True,
        help_text="Tax percentage to apply on Net salary",
    )
    tax_amount_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Net salary threshold for tax deduction",
    )
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return f"{self.employee.employee_name} - {self.gross_salary}"

    def save(self, *args, **kwargs):
        # Use Decimal for arithmetic and save inside a transaction.
        basic = self.basic or Decimal("0")
        house = self.house_rent or Decimal("0")
        convey = self.conveyance or Decimal("0")
        medical = self.medical or Decimal("0")

        self.gross_salary = math.ceil(basic + house + convey + medical)

        # Save the Salary record first, then atomically update the Employee.salary
        with transaction.atomic():
            super().save(*args, **kwargs)
            if getattr(self, "employee_id", None):
                Employee.objects.filter(pk=self.employee_id).update(
                    salary=self.gross_salary
                )


class Employee(models.Model):
    """
    The core model for storing all employee information.
    Linked one-to-one with the User model for authentication.
    """

    STATUS_CHOICES = (
        ("active", "Active"),
        ("resigned", "Resigned"),
        ("terminated", "Terminated"),
        ("incomplete", "Incomplete"),
    )

    MARITAL_STATUS_CHOICES = [
        ("single", "Single"),
        ("married", "Married"),
        ("divorced", "Divorced"),
        ("widowed", "Widowed"),
    ]

    BLOOD_GROUP_CHOICES = [
        ("A+", "A+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B-", "B-"),
        ("AB+", "AB+"),
        ("AB-", "AB-"),
        ("O+", "O+"),
        ("O-", "O-"),
    ]

    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ]

    REQUIRED_FIELDS_FOR_ACTIVE_STATUS = [
        "employee_name",
        "department",
        "designation",
        "location",
        "joining_date",
        "present_address",
        "permanent_address",
        "personal_mobile_number",
        "gender",
    ]
    # --- Official Information (Admin Managed) ---
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    employee_id = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique Employee ID",
        blank=True,
        null=True,
    )
    employee_name = models.CharField(
        max_length=255, help_text="Full name of the employee", blank=True, null=True
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, blank=True, null=True
    )
    designation = models.ForeignKey(
        Designation, on_delete=models.SET_NULL, blank=True, null=True
    )
    location = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="Work location/branch",
    )
    joining_date = models.DateField(
        blank=True, null=True, help_text="Date when the employee joined the company"
    )
    probation_period = models.BooleanField(
        default=True,
        help_text="Indicates if the employee has completed their probation period",
    )
    probation_period_time = models.PositiveIntegerField(
        default=3, help_text="In months"
    )
    confirmation_date = models.DateField(null=True, blank=True)
    supervisor = models.ManyToManyField(
        User,
        related_name="supervised_employees",
        blank=True,
        help_text="Direct supervisor(s) for this employee",
    )
    office_days = models.CharField(
        max_length=100, default="Sunday-Thursday", blank=True, null=True
    )
    office_time = models.ForeignKey(
        Shift,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Assigned office shift",
    )
    official_mobile_number = models.CharField(max_length=20, blank=True, null=True)
    employment_type = models.ForeignKey(
        "leave.LeaveGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Employment type",
        related_name="employment_type_employees",
    )
    leave_group = models.ForeignKey(
        "leave.LeaveGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Leave group for applying specific leave policies",
    )
    salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    rfid_or_machine_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="RFID or Biometric Machine Code",
    )
    grade = models.ForeignKey(
        Grade,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="Employee grade",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="incomplete"
    )
    resign_terminated_date = models.DateField(null=True, blank=True)
    resign_terminated_reason = models.TextField(blank=True, null=True)

    # --- Personal Information (Admin/Employee Editable) ---
    present_address = models.TextField(blank=True, null=True)
    permanent_address = models.TextField(blank=True, null=True)
    marital_status = models.CharField(
        max_length=20,
        choices=MARITAL_STATUS_CHOICES,
        default="single",
        blank=True,
        null=True,
    )
    religion = models.CharField(max_length=50, blank=True, null=True)
    blood_group = models.CharField(
        max_length=20, choices=BLOOD_GROUP_CHOICES, default="O+"
    )
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default="male")
    personal_mobile_number = models.CharField(max_length=20, blank=True, null=True)
    personal_email_id = models.EmailField(blank=True, null=True)
    last_education = models.CharField(max_length=255, blank=True, null=True)
    educational_institute = models.CharField(max_length=255, blank=True, null=True)
    last_job_experience = models.TextField(blank=True, null=True, default="N/A")
    emergency_contact = models.ManyToManyField(
        EmergencyContact, blank=True, help_text="Emergency contact details"
    )
    nominee = models.ManyToManyField(
        Nominee, blank=True, help_text="Nominee details for benefits"
    )
    profile_picture = models.ImageField(
        upload_to=upload_to_profile, null=True, blank=True
    )
    signature = models.ImageField(
        upload_to=upload_to_signature, null=True, blank=True
    )
    date_of_birth = models.DateField(null=True, blank=True)

    # Bank Information
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_account_number = models.CharField(max_length=100, blank=True, null=True)
    bank_branch = models.CharField(max_length=100, blank=True, null=True)

    # --- System & Access Settings ---
    allow_web_login = models.BooleanField(
        default=True, help_text="Enable/disable web login entirely for this user"
    )
    is_ip_restricted = models.BooleanField(
        default=True, help_text="If true, user can only login from pre-approved IPs"
    )
    allow_any_ip_attendance = models.BooleanField(
        default=False, help_text="Admin-controlled exception for remote staff"
    )

    def is_complete(self):
        """Check if all required fields are filled for active status"""
        for field_name in self.REQUIRED_FIELDS_FOR_ACTIVE_STATUS:
            value = getattr(self, field_name)
            if value is None or value == "":
                return False
        return True

    def update_status(self):
        """Determine the appropriate status without saving."""
        # If status is 'resigned' or 'terminated', preserve it unless explicitly changed
        if self.status in ["resigned", "terminated"]:
            return self.status
        # If profile is complete and status is 'incomplete', set to 'active'
        if self.is_complete() and self.status == "incomplete":
            return "active"
        # If profile is incomplete and status is 'active', set to 'incomplete'
        if not self.is_complete() and self.status == "active":
            return "incomplete"
        # Otherwise, keep the current status
        return self.status

    def update_leave_group(self):
        """Update leave group based on employment type"""
        if self.employment_type and self.leave_group != self.employment_type:
            self.leave_group = self.employment_type
            leaves_in_group = LeavePolicy.objects.filter(
                leave_groups=self.employment_type
            )
            total_leaves = 0
            for leave in leaves_in_group:
                total_leaves += leave.total_leave_days
            admin_user = User.objects.filter(is_superuser=True).first()
            Notification.objects.create(
                title=f"Your probation is complete. Your leave balance has been updated to {total_leaves} days.",
                receiver=self.user,
                type="leave",
                remarks=f"Your leave group has been updated to {self.leave_group.name} with a total of {total_leaves} leaves.",
            )
            Notification.objects.create(
                title=f"{self.user.username}'s probation is complete. Leave balance has been updated to {total_leaves} days.",
                receiver=admin_user,
                type="leave",
                remarks=f"{self.user.username}'s leave group has been updated to {self.leave_group.name} with a total of {total_leaves} leaves.",
            )
            super().save(update_fields=["leave_group"])

    def save(self, *args, **kwargs):
        # Optionally update status on save as well
        self.status = self.update_status()

        super().save(*args, **kwargs)

        # Automatically update leave group after save
        self.update_leave_group()

    def __str__(self):
        return f"{self.employee_name} - ({self.employee_id})"

    @property
    def id(self):
        """Return the primary key value for compatibility"""
        return self.pk


class ProbationCheckLog(models.Model):
    """
    Log for probation period checks.
    This is used to track when the probation period was checked and the result.
    """

    date = models.DateField(unique=True, help_text="Date of the probation check")
    last_checked = models.BooleanField(
        default=False, help_text="Whether the probation period was checked on this date"
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Clean old data
        threshold_date = timezone.now().date() - timezone.timedelta(days=30)
        ProbationCheckLog.objects.filter(date__lt=threshold_date).delete()

    def __str__(self):
        return f"{self.date}"
