from django.db import models
from django.core.exceptions import ValidationError
from authentication.models import User
from rest_framework.exceptions import ValidationError as DRFValidationError
from employee.models import Employee
from django.utils import timezone
from django.utils.timezone import timedelta
from datetime import datetime
import calendar
from datetime import date


class AttendanceData(models.Model):

    ATTENDANCE_TYPE = (
        ("Present", "Present"),
        ("Absent", "Absent"),
        ("Late", "Late"),
        ("Overtime", "Overtime"),
        ("Early Leave", "Early Leave"),
        ("Not Detected", "Not Detected"),
    )

    LOGIN_TYPE = (
        ("Device Login", "Device Login"),
        ("Web Login", "Web Login"),
        ("Manual Entry", "Manual Entry"),
    )
    employee = models.ForeignKey(
        Employee,
        related_name="user_attendance_data",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    rfid_or_machine_code = models.CharField(max_length=100, null=True, blank=True)
    # Get local IP
    local_ip_address = models.CharField(max_length=100, null=True, blank=True)
    # Get Geo Location
    latitude = models.CharField(max_length=100, null=True, blank=True)
    longitude = models.CharField(max_length=100, null=True, blank=True)
    location_accuracy = models.CharField(max_length=100, null=True, blank=True)
    location_name = models.CharField(max_length=500, null=True, blank=True)
    # Device details
    device_serial_number = models.CharField(max_length=100, null=True, blank=True)
    login_type = models.CharField(
        max_length=100,
        choices=LOGIN_TYPE,
        default="Device Login",
        null=True,
        blank=True,
    )

    # Incoming from device
    timestamp = models.DateTimeField(null=True, blank=True)

    attendance_status = models.CharField(
        max_length=100, choices=ATTENDANCE_TYPE, null=True, blank=True
    )
    remarks = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    created_by = models.ForeignKey(
        Employee,
        related_name="created_by",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Attendance Data"
        verbose_name_plural = "Attendances Data"
        indexes = [
            models.Index(fields=["employee", "timestamp"]),
            models.Index(fields=["timestamp"]),
        ]
        permissions = [
            ("view_own_attendance", "Can view own attendance data"),
            ("view_subordinate_attendance", "Can view subordinate attendance data"),
        ]

    def __str__(self):
        return self.employee.user.email

    def clean(self):
        """Custom validation to ensure either employee or rfid_or_machine_code is set."""
        if not self.employee and not self.rfid_or_machine_code:
            raise ValidationError(
                "Either employee or RFID/machine code must be provided."
            )

        if self.rfid_or_machine_code and not self.employee:
            # If rfid_or_machine_code is provided, look up the employee
            try:
                Employee.objects.get(rfid_or_machine_code=self.rfid_or_machine_code)
            except Employee.DoesNotExist:
                raise ValidationError(
                    f"Employee with RFID or machine code '{self.rfid_or_machine_code}' does not exist."
                )

    def save(self, *args, **kwargs):
        self.clean()  # Call clean method to validate data
        # Look up employee by RFID or machine code if not set
        if not self.employee and self.rfid_or_machine_code:
            try:
                employee = Employee.objects.get(
                    rfid_or_machine_code=self.rfid_or_machine_code
                )
                self.employee = employee
            except Employee.DoesNotExist:
                raise ValidationError(
                    f"Employee with RFID or machine code '{self.rfid_or_machine_code}' does not exist."
                )

        # Only calculate status if employee and timestamp are available

        if self.employee and self.timestamp:
            # Ensure rfid_or_machine_code is set to the employee's rfid_or_machine_code
            rf_id = (
                self.employee.rfid_or_machine_code
                if self.employee.rfid_or_machine_code
                else None
            )
            self.rfid_or_machine_code = rf_id

            employee_shift = self.employee.office_time
            if employee_shift:
                # Determine if this is an overnight shift
                is_overnight = (
                    employee_shift.office_end_time < employee_shift.office_start_time
                )

                # Get the shift start date for this timestamp
                today = self.timestamp.date()
                shift_date = today
                check_in_start_dt = timezone.make_aware(
                    datetime.combine(today, employee_shift.check_in_start_time),
                    timezone.get_current_timezone(),
                )
                check_in_end_dt = timezone.make_aware(
                    datetime.combine(today, employee_shift.check_in_end_time),
                    timezone.get_current_timezone(),
                )
                check_out_start_dt = timezone.make_aware(
                    datetime.combine(today, employee_shift.check_out_start_time),
                    timezone.get_current_timezone(),
                )
                check_out_end_dt = timezone.make_aware(
                    datetime.combine(today, employee_shift.check_out_end_time),
                    timezone.get_current_timezone(),
                )

                if is_overnight:
                    check_out_start_dt += timedelta(days=1)
                    check_out_end_dt += timedelta(days=1)
                    # If timestamp is in check-out window, map to previous day's shift
                    if check_out_start_dt <= self.timestamp <= check_out_end_dt:
                        shift_date = today - timedelta(days=1)
                        # Skip status assignment for check-out timestamps
                        self.attendance_status = ""
                        super().save(*args, **kwargs)
                        return

                # Only assign status for timestamps in check-in window
                if check_in_start_dt <= self.timestamp <= check_in_end_dt:
                    # Check for existing records for this shift
                    existing_records = AttendanceData.objects.filter(
                        employee=self.employee,
                        timestamp__gte=timezone.make_aware(
                            datetime.combine(
                                shift_date, employee_shift.check_in_start_time
                            ),
                            timezone.get_current_timezone(),
                        ),
                        timestamp__lte=timezone.make_aware(
                            datetime.combine(
                                shift_date, employee_shift.check_out_end_time
                            )
                            + (timedelta(days=1) if is_overnight else timedelta(0)),
                            timezone.get_current_timezone(),
                        ),
                    ).order_by("timestamp")

                    is_first_record_of_shift = True
                    if existing_records.exists():
                        first_record_timestamp = existing_records.first().timestamp
                        if self.timestamp > first_record_timestamp:
                            is_first_record_of_shift = False
                        elif self.pk and self.pk == existing_records.first().pk:
                            is_first_record_of_shift = True

                    if is_first_record_of_shift:
                        # Calculate status based on office_start_time
                        office_start_time = timezone.make_aware(
                            datetime.combine(
                                shift_date, employee_shift.office_start_time
                            ),
                            timezone.get_current_timezone(),
                        )
                        office_start_time_consideration = (
                            employee_shift.office_start_time_consideration
                        )

                        time_difference = (
                            self.timestamp - office_start_time
                        ).total_seconds() / 60

                        if time_difference <= office_start_time_consideration:
                            self.attendance_status = "Present"
                        else:
                            self.attendance_status = "Late"
                    else:
                        # Non-first records in check-in window (e.g., multiple check-ins) get no status
                        self.attendance_status = ""
                else:
                    # Timestamps outside check-in window (e.g., mid-shift or check-out) get no status
                    self.attendance_status = ""
            else:
                self.attendance_status = ""
        else:
            self.attendance_status = ""

        super().save(*args, **kwargs)


class AttendanceAdjustmentRequest(models.Model):
    """Manages employee requests for attendance adjustments."""

    ADJUSTMENT_CHOICES = (
        ("forgot_sign_in", "Forgot to Sign In"),
        ("forgot_sign_out", "Forgot to Sign Out"),
        ("traffic_delay", "Traffic Delay"),
        ("personal_emergency", "Personal Emergency"),
        ("other", "Other"),
    )
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )
    CHECK_TYPE_CHOICES = (
        ("check_in", "Check In"),
        ("check_out", "Check Out"),
    )

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="adjustment_requests"
    )
    date = models.DateField(null=True, blank=True)
    check_type = models.CharField(
        max_length=100, choices=CHECK_TYPE_CHOICES, null=True, blank=True
    )
    actual_duty_start_time = models.DateTimeField(
        help_text="The start of the period needing adjustment", null=True, blank=True
    )
    actual_arival_time = models.DateTimeField(
        help_text="The end of the period needing adjustment", null=True, blank=True
    )
    adjustment_type = models.CharField(
        max_length=100, choices=ADJUSTMENT_CHOICES, null=True, blank=True
    )
    remarks = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Adjustment Request for {self.employee} on {self.date}"


class AttendanceAdjustmentApproval(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    actual_duty_start_time = models.DateTimeField(
        help_text="Actual duty start time", null=True, blank=True
    )
    actual_arrival_time = models.DateTimeField(
        help_text="The end of the period needing adjustment", null=True, blank=True
    )
    requested_arrival_time = models.DateTimeField(
        help_text="The start of the period needing adjustment", null=True, blank=True
    )
    adjustment_request = models.ForeignKey(
        AttendanceAdjustmentRequest,
        on_delete=models.CASCADE,
        related_name="adjustment_approvals",
    )
    approver = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="adjustment_approvals"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    remarks = models.TextField(blank=True, null=True)
    comments = models.TextField(blank=True, null=True)
    action_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Approval for {self.adjustment_request} by {self.approver}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # Get previous status if this is an update
        if not is_new:
            prev = AttendanceAdjustmentApproval.objects.get(pk=self.pk)
            status_changed_to_approved = (
                prev.status != "approved" and self.status == "approved"
            )
        else:
            status_changed_to_approved = self.status == "approved"

        # validation: Approving a check-out adjustment, require a corresponding check-in record in AttendanceHistory
        if status_changed_to_approved:
            req = self.adjustment_request
            if req.check_type == "check_out":
                # check existence of a check-in for the same day
                has_checkin = AttendanceHistory.objects.filter(
                    employee=req.employee,
                    date=req.date,
                    check_in_time__isnull=False,
                ).exists()
                if not has_checkin:
                    raise DRFValidationError(
                        "Cannot approve check-out adjustment before a check-in record exists. Please approve the check-in adjustment first."
                    )

        # Save this instance first
        super().save(*args, **kwargs)

        # If status just changed to approved → update others
        if status_changed_to_approved:
            AttendanceAdjustmentApproval.objects.filter(
                adjustment_request=self.adjustment_request
            ).exclude(pk=self.pk).exclude(status="approved").update(status="approved")


class AttendanceHistory(models.Model):
    """Stores historical attendance data for employees."""

    employee = models.ForeignKey(
        Employee, related_name="attendance_history", on_delete=models.CASCADE
    )
    date = models.DateField()
    rfid_or_machine_code = models.CharField(max_length=100, null=True, blank=True)
    local_ip_address = models.CharField(max_length=100, null=True, blank=True)
    device_serial_number = models.CharField(max_length=100, null=True, blank=True)
    is_late = models.BooleanField(default=False)
    is_holiday = models.BooleanField(default=False)
    is_weekend = models.BooleanField(default=False)
    # keeps track if a first-half half-day leave adjustment was applied when
    # calculating lateness (i.e. the effective start time was shifted).
    half_day_adjusted = models.BooleanField(default=False)
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    early_out_by = models.DurationField(
        null=True, blank=True, help_text="Duration of early out in minutes"
    )
    late_by = models.DurationField(
        null=True, blank=True, help_text="Duration of lateness in minutes"
    )
    status = models.CharField(max_length=100, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Attendance History"
        verbose_name_plural = "Attendances History"
        unique_together = ("employee", "date")

    def save(self, *args, **kwargs):
        # No status calculation here; handled by the signal in AttendanceHistory
        self.attendance_status = ""
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee.employee_name} ({self.employee.employee_id}) - {self.date}"
        )


# CutOff Date model to manage cutoff dates for attendance processing and payroll calculations
class CutOff(models.Model):
    name = models.CharField(max_length=100, unique=True, default="Cut Off")
    date = models.PositiveIntegerField(default=25)
    cut_off_start = models.DateField(blank=True, null=True)
    cut_off = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.name

    @classmethod
    def update_cutoff(cls):
        """Get or create cutoff object and update cutoff date based on logic."""
        today = timezone.now().date()

        # ensure there is a single cutoff record
        cutoff_obj, created = cls.objects.get_or_create(
            name="Cut Off",
            defaults={
                "date": 25,
                "cut_off": (
                    today.replace(day=25)
                    if today.day <= 25
                    else cls._get_next_month_date(today, 25)
                ),
            },
        )

        cutoff_day = cutoff_obj.date or 25

        # determine which month/year to calculate the cutoff for
        if today.day <= cutoff_day:
            target_year = today.year
            target_month = today.month
        else:
            # roll over to next month
            if today.month == 12:
                target_year = today.year + 1
                target_month = 1
            else:
                target_year = today.year
                target_month = today.month + 1

        # compute the day of month to use; if cutoff_day is 31, use last day
        # of the target month.  otherwise clamp to the month's length as well.
        last_day = calendar.monthrange(target_year, target_month)[1]
        if cutoff_day == 31:
            use_day = last_day
        else:
            use_day = min(cutoff_day, last_day)

        new_cutoff = date(target_year, target_month, use_day)

        # compute the corresponding cut_off_start value according to rules:
        # - when cutoff_day == 31, start is first day of same month
        # - otherwise, start is day-after the cutoff_day in the previous month
        if cutoff_day == 31:
            new_cutoff_start = date(target_year, target_month, 1)
        else:
            # figure previous month/year
            if target_month == 1:
                prev_year = target_year - 1
                prev_month = 12
            else:
                prev_year = target_year
                prev_month = target_month - 1
            prev_last = calendar.monthrange(prev_year, prev_month)[1]
            prev_day = min(cutoff_day, prev_last)
            prev_cutoff = date(prev_year, prev_month, prev_day)
            new_cutoff_start = prev_cutoff + timedelta(days=1)

        # update only if any values changed
        if (
            cutoff_obj.cut_off != new_cutoff
            or cutoff_obj.cut_off_start != new_cutoff_start
        ):
            cutoff_obj.cut_off = new_cutoff
            cutoff_obj.cut_off_start = new_cutoff_start
            cutoff_obj.save(update_fields=["cut_off", "cut_off_start", "updated_at"])

        return cutoff_obj

    @staticmethod
    def _get_next_month_date(current_date, day):
        """Helper to calculate cutoff date in next month with given day."""
        year = current_date.year
        month = current_date.month + 1
        if month > 12:
            month = 1
            year += 1

        # handle if `day` > last day of month
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(day, last_day))
