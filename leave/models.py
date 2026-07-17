from decimal import Decimal
from django.db import models
from authentication.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from notification.models import Notification
import uuid
from datetime import timedelta


# Leave Groups
class LeaveGroup(models.Model):
    """Categorizes employees for applying specific leave policies (e.g., General, Teachers)."""

    name = models.CharField(max_length=100, unique=True, blank=True, null=True)
    description = models.TextField(
        blank=True, null=True, help_text="Optional description for the leave group."
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the group was created."
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the group was last updated."
    )

    def __str__(self):
        return self.name


# Leave Policies


class LeavePolicy(models.Model):
    """Defines the rules for a specific type of leave."""

    EFFECTIVE_FROM_CHOICES = (
        ("joining", "From Joining"),
        ("confirmation", "After Confirmation"),
        ("one_year", "After 1 Year of Service"),
    )

    GENDER = (("any", "Any"), ("male", "Male"), ("female", "Female"))

    leave_type_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Name of the leave type (e.g., Casual Leave, Sick Leave).",
    )
    leave_groups = models.ManyToManyField(
        LeaveGroup,
        related_name="leave_policies",
        blank=True,
        help_text="Leave groups that can apply this policy.",
    )
    total_leave_days = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Total leave days allotted per year for this policy.",
    )
    gender = models.CharField(max_length=10, choices=GENDER, default="any")
    apply_before_days = models.PositiveIntegerField(
        default=0, help_text="Min days to apply in advance. 0 for any time."
    )
    effective_from = models.CharField(
        max_length=20, choices=EFFECTIVE_FROM_CHOICES, default="joining"
    )
    max_days_per_request = models.PositiveIntegerField(
        default=30,
        blank=True,
        null=True,
        help_text="Maximum days allowed per leave request. Leave requests exceeding this will be rejected.",
    )
    min_days_per_request = models.PositiveIntegerField(
        default=1,
        blank=True,
        null=True,
        help_text="Minimum days required for a leave request. Leave requests with fewer days will be rejected.",
    )
    allow_half_day = models.BooleanField(
        default=True,
        blank=True,
        null=True,
        help_text="If checked, allows half-day leave requests.",
    )
    count_holidays = models.BooleanField(
        default=False,
        blank=True,
        null=True,
        help_text="If checked, holidays within the leave period are counted as leave.",
    )
    count_weekends = models.BooleanField(
        default=False,
        blank=True,
        null=True,
        help_text="If checked, weekends within the leave period are counted as leave.",
    )
    is_active = models.BooleanField(default=True, blank=True, null=True)
    validity = models.PositiveBigIntegerField(
        default=0,
        help_text="Validity period in days for this leave request. Default is 0 (no expiry).",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the policy was created."
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the policy was last updated."
    )

    def __str__(self):
        # return self.leave_type_name or f"Unnamed LeavePolicy (ID: {self.pk})"
        groups = ", ".join([group.name for group in self.leave_groups.all()])
        return f"{groups} - {self.leave_type_name}"

    @property
    def export_label(self):
        groups = ", ".join(self.leave_groups.values_list("name", flat=True))
        return f"{groups} - {self.leave_type_name}"


# Special Leave Policies


class SpecialLeavePolicy(models.Model):
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_special_leave_policies",
        blank=True,
        null=True,
        help_text="User who created this special leave policy.",
    )
    leave_policy = models.ForeignKey(
        LeavePolicy,
        on_delete=models.CASCADE,
        related_name="special_policies",
        blank=True,
        null=True,
        help_text="Leave policy this special policy is based on.",
    )
    available_policies = models.ManyToManyField(
        LeavePolicy,
        related_name="available_special_policies",
        blank=True,
        help_text="Policies that can be applied for this special leave.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the special leave policy was created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the special leave policy was last updated.",
    )

    def __str__(self):
        return f"Special Leave Policy for {self.leave_policy.leave_type_name if self.leave_policy else 'Unnamed Policy'}"


# Leave Requests
class LeaveRequest(models.Model):
    """Stores employee leave requests and their approval status."""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    )
    HALF_DAY_CHOICES = (
        ("first half", "First Half"),
        ("second half", "Second Half"),
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="leave_request_creator",
        blank=True,
        null=True,
    )
    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.CASCADE,
        related_name="leave_requests",
        blank=True,
        null=True,
    )
    leave_policy = models.ForeignKey(
        LeavePolicy,
        on_delete=models.PROTECT,
        related_name="leave_requests",
        blank=True,
        null=True,
        help_text="Leave policy applied for this request.",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    is_half_day = models.BooleanField(
        default=False, help_text="If checked, this is a half-day leave request."
    )
    half_day_period = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=HALF_DAY_CHOICES,
        help_text="If this is a half-day leave, specify the period (e.g., 'first half', 'second half').",
    )
    reason = models.TextField(
        help_text="Reason for the leave request", blank=True, null=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    status_tracking_date = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the status was last updated."
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="leave_request_updated_by",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Signature fields
    admin_check_sign = models.JSONField(null=True, blank=True, default=None)
    req_unit_head_sign = models.JSONField(null=True, blank=True, default=None)
    req_excutive_sign = models.JSONField(null=True, blank=True, default=None)
    joining_excutive_sign = models.JSONField(null=True, blank=True, default=None)
    joining_employee_sign = models.JSONField(null=True, blank=True, default=None)

    # Joining fields
    actual_joining_date = models.DateField(null=True, blank=True)
    as_per_leave_joining_date = models.DateField(null=True, blank=True, editable=False)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Leave request for {self.employee} from {self.start_date}"

    def create_approvals(self):
        """Create approval instances for each supervisor level"""
        supervisor_levels = SupervisorLevel.objects.filter(
            employee=self.employee
        ).order_by("level")

        leave_group_names = ", ".join(
            [group.name for group in self.leave_policy.leave_groups.all()]
        )

        for level in supervisor_levels:
            approval = LeaveApproval.objects.create(
                leave_request=self, approver=level.supervisor, level=level.level
            )

            Notification.objects.create(
                title=f"""Leave request for {self.employee.user} from {self.start_date} to {self.end_date}. Leave Policy - {leave_group_names}, Leave Type - {self.leave_policy.leave_type_name} {'- Half Day Leave' if self.is_half_day else ''}
                """,
                type="leave",
                notification_id=approval.id,
                employee=self.employee.user,
                receiver=level.supervisor,
            )

    def update_status(self):
        """Update overall status based on approval statuses"""
        approvals = self.approvals.all()

        if not approvals.exists():
            return

        # Check if any rejection exists
        if approvals.filter(status="rejected").exists():
            self.status = "rejected"
            self.save()
            return

        # Check if all approved
        if approvals.filter(status="approved").count() == approvals.count():
            self.status = "approved"
            self.save()

    def save(self, *args, **kwargs):
        created = not self.pk  # Check if this is a new instance

        # Auto-calculate as_per_leave_joining_date as end_date + 1 day
        if self.end_date and not self.as_per_leave_joining_date:
            from datetime import timedelta
            self.as_per_leave_joining_date = self.end_date + timedelta(days=1)

        # Store previous status for balance updates
        if not created:
            previous = LeaveRequest.objects.get(pk=self.pk)
            self.previous_status = previous.status
            if previous.status != self.status:
                self.status_tracking_date = timezone.now()
        else:
            self._previous_status = None

        super().save(*args, **kwargs)

        if created:
            self.create_approvals()

    def clean(self):
        """Validate leave request before saving"""

        if (
            self.leave_policy
            and self.leave_policy.leave_type_name == "Compensatory Leave"
        ):

            # Calculate required leave days
            leave_days = (self.end_date - self.start_date).days + 1
            if self.is_half_day:
                leave_days = 0.5

            # Check compensatory leave balance
            try:
                balance = self.employee.comp_leave_balance
                balance.clean_expired_leaves()

                if balance.current_balance < leave_days:
                    raise ValidationError(
                        f"Insufficient compensatory leave balance. "
                        f"Available: {balance.current_balance}, Required: {leave_days}"
                    )
            except CompensatoryLeaveBalance.DoesNotExist:
                raise ValidationError("No compensatory leave balance found.")


# Supervisor Levels


class SupervisorLevel(models.Model):
    """Defines employee-specific supervisor hierarchy for leave approvals."""

    employee = models.ForeignKey(
        "employee.Employee", on_delete=models.CASCADE, related_name="supervisor_levels"
    )
    supervisor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="supervisor_levels",
    )
    level = models.PositiveIntegerField(
        help_text="The approval level sequence (1=first, 2=second, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("employee", "supervisor")
        ordering = ["level"]

    def __str__(self):
        return f"Level {self.level} supervisor for {self.employee}"

    def clean(self):
        # Prevent the same supervisor being assigned to multiple levels for the same employee
        if (
            SupervisorLevel.objects.filter(
                employee=self.employee, supervisor=self.supervisor
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                f"{self.supervisor} is already assigned as a supervisor for {self.employee} at another level."
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        # Add this supervisor to the employee's supervisors if not already present
        if self.supervisor and self.supervisor not in self.employee.supervisor.all():
            self.employee.supervisor.add(self.supervisor)


# Leave Approvals


class LeaveApproval(models.Model):
    """Stores the status of each approval level for a LeaveRequest."""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )
    leave_request = models.ForeignKey(
        LeaveRequest,
        on_delete=models.CASCADE,
        related_name="approvals",
        blank=True,
        null=True,
        help_text="The leave request this approval is for.",
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="leave_approvals_level",
        blank=True,
        null=True,
        help_text="Users who can approve this request.",
    )
    level = models.PositiveIntegerField(help_text="The approval level sequence.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    comments = models.TextField(
        blank=True, null=True, help_text="Optional comments from the approver."
    )
    action_date = models.DateTimeField(
        blank=True, null=True, help_text="Timestamp of the approval/rejection."
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the approval was created."
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the approval was last updated."
    )

    class Meta:
        unique_together = ("leave_request", "level")
        ordering = ["level"]

    def __str__(self):
        return f"Level {self.level} approval for {self.leave_request}"

    def clean(self):
        """Validate that the approver is actually assigned as a supervisor for this employee"""
        if not SupervisorLevel.objects.filter(
            employee=self.leave_request.employee,
            supervisor=self.approver,
            level=self.level,
        ).exists():
            raise ValidationError(
                f"{self.approver} is not assigned as a level {self.level} supervisor for {self.leave_request.employee}"
            )

    def save(self, *args, **kwargs):
        # Track previous status
        is_new = self.pk is None
        previous_status = None
        if not is_new:
            previous = LeaveApproval.objects.get(pk=self.pk)
            previous_status = previous.status

        # Set action date
        if is_new:
            if self.status in ["approved", "rejected"]:
                self.action_date = timezone.now()
        else:
            if previous_status != self.status and self.status in [
                "approved",
                "rejected",
            ]:
                self.action_date = timezone.now()

        # Save instance first
        super().save(*args, **kwargs)

        # 🔔 Send Notification on approved/rejected
        if (is_new and self.status in ["approved", "rejected"]) or (
            previous_status != self.status and self.status in ["approved", "rejected"]
        ):
            Notification.objects.create(
                title=f"{self.leave_request.leave_policy.leave_type_name} Request from {self.leave_request.start_date} to {self.leave_request.end_date} has been {self.status} by {self.approver}",
                receiver=self.leave_request.employee.user,
                type="leave",
                remarks=self.comments,
            )

        # ❗ Rejection cascade
        if self.status == "rejected":
            other_approvals = (
                LeaveApproval.objects.filter(leave_request=self.leave_request)
                .exclude(pk=self.pk)
                .exclude(status="rejected")
            )

            for approval in other_approvals:
                approval.status = "rejected"
                approval.action_date = timezone.now()
                approval.comments = (
                    approval.comments
                    or f"Automatically rejected because level {self.level} was rejected"
                )
                approval.save()


# Leave Reset
class LeaveReset(models.Model):
    MONTH_CHOICES = [
        (1, "January"),
        (2, "February"),
        (3, "March"),
        (4, "April"),
        (5, "May"),
        (6, "June"),
        (7, "July"),
        (8, "August"),
        (9, "September"),
        (10, "October"),
        (11, "November"),
        (12, "December"),
    ]
    start_month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES, default=1)
    start_day = models.PositiveSmallIntegerField(default=1)
    end_month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES, default=12)
    end_day = models.PositiveSmallIntegerField(default=31)
    is_active = models.BooleanField(
        default=True, help_text="If checked, this reset period is currently active."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Leave Reset Period"
        verbose_name_plural = "Leave Reset Periods"

    def __str__(self):
        return f"{self.get_start_month_display()} {self.start_day} to {self.get_end_month_display()} {self.end_day}"

    @classmethod
    def get_current_period(cls, date):
        """Get the current leave period for a given date"""
        # Get the first active reset period (if exists)
        reset_period = cls.objects.filter(is_active=True).first()
        # If no active reset period, return default calendar year
        if not reset_period:
            # Default to calendar year if no reset period is configured
            return (date.replace(month=1, day=1), date.replace(month=12, day=31))

        # Get the current year
        year = date.year

        # Create start and end dates
        start_date = date.replace(
            month=reset_period.start_month, day=reset_period.start_day
        )
        end_date = date.replace(month=reset_period.end_month, day=reset_period.end_day)

        # Handle cases where end month is earlier in the year than start month (e.g., June-May)
        if reset_period.end_month < reset_period.start_month:
            if date >= start_date:
                # Current period started this year, ends next year
                end_date = end_date.replace(year=year + 1)
            else:
                # Current period started last year, ends this year
                start_date = start_date.replace(year=year - 1)

        return start_date, end_date


# Leave Transfer


class LeaveTransfer(models.Model):
    """Tracks leave transfers when employees change leave groups"""

    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.CASCADE,
        related_name="leave_transfers",
        blank=True,
        null=True,
    )
    from_leave_policy = models.ForeignKey(
        LeavePolicy,
        on_delete=models.CASCADE,
        related_name="transfers_out",
        blank=True,
        null=True,
    )
    to_leave_policy = models.ForeignKey(
        LeavePolicy,
        on_delete=models.CASCADE,
        related_name="transfers_in",
        blank=True,
        null=True,
    )
    from_leave_group = models.ForeignKey(
        LeaveGroup,
        on_delete=models.CASCADE,
        related_name="transfers_out",
        blank=True,
        null=True,
    )
    to_leave_group = models.ForeignKey(
        LeaveGroup,
        on_delete=models.CASCADE,
        related_name="transfers_in",
        blank=True,
        null=True,
    )
    days_transferred = models.DecimalField(default=0, max_digits=5, decimal_places=2)
    transfer_date = models.DateField(auto_now_add=True)
    year = models.DateField(
        help_text="Year when the transfer occurred. Defaults to current year.",
        blank=True,
        null=True,
    )
    transfer_identifier = models.UUIDField(default=uuid.uuid4, editable=False)
    is_reversed = models.BooleanField(default=False)
    reversed_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.days_transferred} days transferred for {self.employee}"

    def save(self, *args, **kwargs):
        if self.year is None:
            # Set year to current date if not provided
            self.year = timezone.now().date()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-transfer_date"]
        indexes = [
            models.Index(fields=["employee", "year"]),
            models.Index(fields=["transfer_identifier"]),
        ]


# Compensatory Leave Balance
class CompensatoryLeaveBalance(models.Model):
    """Tracks compensatory leave balance for employees"""

    employee = models.OneToOneField(
        "employee.Employee", on_delete=models.CASCADE, related_name="comp_leave_balance"
    )
    total_earned = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        default=0,
        help_text="Total compensatory leaves earned",
    )
    total_used = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        default=0,
        help_text="Total compensatory leaves used",
    )
    current_balance = models.DecimalField(
        max_digits=5, decimal_places=1, default=0, help_text="Current available balance"
    )
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.employee_name} - Balance: {self.current_balance}"

    def add_comp_leave(self, earned_date, days_earned=1):
        """Add compensatory leave and create a tracking record"""
        days_earned = Decimal(days_earned)
        self.total_earned += days_earned
        self.current_balance += days_earned
        self.save()

        # Create tracking record
        CompensatoryLeaveEarned.objects.create(
            employee=self.employee,
            earned_date=earned_date,
            expires_on=earned_date + timedelta(days=30),
            is_used=False,
            days_earned=days_earned,
        )

    def use_comp_leave(self, days_used):
        """Use compensatory leave (FIFO - First In, First Out)"""
        days_used = Decimal(days_used)
        if self.current_balance < days_used:
            raise ValueError("Insufficient compensatory leave balance")

        remaining_to_use = days_used
        earned_leaves = CompensatoryLeaveEarned.objects.filter(
            employee=self.employee, is_used=False, expires_on__gte=timezone.now().date()
        ).order_by("-earned_date")

        for earned_leave in earned_leaves:
            if remaining_to_use <= 0:
                break

            if earned_leave.days_earned <= remaining_to_use:
                # Use the entire earned leave
                earned_leave.is_used = True
                earned_leave.used_date = timezone.now().date()
                earned_leave.days_used = earned_leave.days_earned
                earned_leave.save()
                remaining_to_use -= earned_leave.days_earned
            else:
                # Use part of this leave (For partial leave)
                earned_leave.is_used = True
                earned_leave.used_date = timezone.now().date()
                earned_leave.days_used = remaining_to_use
                earned_leave.save()
                remaining_to_use = Decimal("0")

        self.total_used += days_used
        self.current_balance -= days_used
        self.save()

    def clean_expired_leaves(self):
        """Remove expired unused compensatory leaves"""
        expired_leaves = CompensatoryLeaveEarned.objects.filter(
            employee=self.employee,
            is_used=False,
            is_expired=False,
            expires_on__lt=timezone.now().date(),
        )

        expired_count = Decimal("0")
        for expired_leave in expired_leaves:
            expired_leave.is_expired = True
            expired_leave.save()
            expired_count += expired_leave.days_earned

        if expired_count > 0:
            self.current_balance = max(
                self.current_balance - expired_count, Decimal("0")
            )
            self.save()

        return expired_count


# Compensatory Leave Earned


class CompensatoryLeaveEarned(models.Model):
    """Tracks individual compensatory leaves earned with expiry"""

    employee = models.ForeignKey(
        "employee.Employee", on_delete=models.CASCADE, related_name="comp_leaves_earned"
    )
    earned_date = models.DateField(help_text="Date when compensatory leave was earned")
    expires_on = models.DateField(help_text="Expiry date for this compensatory leave")
    days_earned = models.DecimalField(
        max_digits=3, decimal_places=1, default=1, help_text="Number of days earned"
    )
    days_used = models.DecimalField(
        max_digits=3, decimal_places=1, default=0, help_text="Number of days used"
    )
    is_used = models.BooleanField(default=False)
    used_date = models.DateField(null=True, blank=True)
    is_expired = models.BooleanField(default=False)
    related_attendance = models.OneToOneField(
        "attendance.AttendanceHistory", on_delete=models.CASCADE, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("employee", "earned_date")

    def __str__(self):
        return f"{self.employee.employee_name} - Earned: {self.earned_date} - Expires: {self.expires_on}"

    def delete(self, *args, **kwargs):
        if self.is_used == True:
            raise ValidationError(
                "Cannot delete a compensatory leave that has been used."
            )
        super().delete(*args, **kwargs)
