import threading
from django.db.models.signals import post_save
from rest_framework.exceptions import ValidationError
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
import pytz
from datetime import datetime, timedelta, time
from leave.models import SupervisorLevel
from .models import (
    AttendanceAdjustmentRequest,
    AttendanceAdjustmentApproval,
    AttendanceData,
    AttendanceHistory,
)
from notification.models import Notification
from authentication.models import User
from holiday.models import Holiday
from employee.utils import check_probation_periods


@receiver(post_save, sender=AttendanceData)
def trigger_probation_check(sender, instance, created, **kwargs):
    if created:  # Only trigger on new attendance records
        threading.Thread(target=check_probation_periods).start()


@receiver(post_save, sender=AttendanceAdjustmentRequest)
def create_adjustment_approvals(sender, instance, created, **kwargs):
    if created:
        # Handle creation - your existing code
        actual_duty_start_time = instance.actual_duty_start_time
        actual_arrival_time = instance.actual_arival_time
        employee = instance.employee

        # Get all top-level supervisor IDs in a single query
        top_level_supervisor_ids = SupervisorLevel.objects.filter(
            level=1, supervisor__isnull=False
        ).values_list("supervisor_id", flat=True)

        # Convert to set for faster lookups
        top_level_supervisor_ids = set(top_level_supervisor_ids)

        # Get all supervisor ids from employee
        supervisor_ids = set(employee.supervisor.all().values_list("id", flat=True))

        # Common supervisor in top_level_supervisor_ids and employee supervisor_ids
        common_supervisor = top_level_supervisor_ids & supervisor_ids

        # Common Supervisor User = top_level_supervisor
        top_level_supervisor = User.objects.filter(id__in=common_supervisor)

        if len(top_level_supervisor) == 0:
            raise ValidationError("No Supervisor found!")

        for supervisor in top_level_supervisor:
            approval = AttendanceAdjustmentApproval.objects.create(
                actual_duty_start_time=actual_duty_start_time,
                actual_arrival_time=actual_arrival_time,
                requested_arrival_time=actual_duty_start_time,
                adjustment_request=instance,
                approver=supervisor,
                remarks=instance.remarks,
            )

            Notification.objects.create(
                title=(
                    f"Attendance Adjustment Request of {instance.employee.user.email}."
                    f" Duty Start Time - {approval.actual_duty_start_time.strftime('%I%p')},"
                    f" Arrival Time - {approval.actual_arrival_time.strftime('%I%p')}"
                ),
                notification_id=approval.id,
                employee=employee.user,
                receiver=supervisor,
                type="attendance_adjustment",
                remarks=instance.remarks,
            )

    else:
        # Handle updates - update existing approval instances
        approvals = AttendanceAdjustmentApproval.objects.filter(
            adjustment_request=instance
        )

        # Update all related approval instances with the new data
        approvals.update(
            actual_duty_start_time=instance.actual_duty_start_time,
            actual_arrival_time=instance.actual_arival_time,
            requested_arrival_time=instance.actual_duty_start_time,
            remarks=instance.remarks,
        )

        # Optionally, update notifications as well
        for approval in approvals:
            try:
                notification = Notification.objects.get(
                    notification_id=approval.id, type="attendance_adjustment"
                )
                notification.title = (
                    f"Attendance Adjustment Request of {instance.employee.user.email} - Late Arrival - "
                    f"{approval.actual_arrival_time.strftime('%I%p') if approval.actual_arrival_time else 'N/A'} "
                    f"to {approval.actual_duty_start_time.strftime('%I%p') if approval.actual_duty_start_time else 'N/A'}"
                )
                notification.remarks = instance.remarks
                notification.save()
            except Notification.DoesNotExist:
                # Notification might not exist or might have been deleted
                pass


@receiver(post_save, sender=AttendanceAdjustmentApproval)
def update_adjustment_request_status(sender, instance, created, **kwargs):
    if instance.status == "approved":
        # Create attendance record
        AttendanceData.objects.create(
            employee=instance.adjustment_request.employee,
            timestamp=instance.requested_arrival_time,
            attendance_status="Present",
            remarks=f"Attendance adjusted by {instance.approver}",
        )

        Notification.objects.create(
            title=f"Attendance Adjustment Request {instance.adjustment_request} has been Approved by - {instance.approver}",
            type="attendance_adjustment",
            receiver=instance.adjustment_request.employee.user,
            remarks=instance.comments,
        )

        instance.adjustment_request.status = "approved"
        instance.adjustment_request.save()

    if instance.status == "rejected":

        Notification.objects.create(
            title=f"Attendance Adjustment Request {instance.adjustment_request} has been Rejected by - {instance.approver}",
            type="attendance_adjustment",
            receiver=instance.adjustment_request.employee.user,
            remarks=instance.comments,
        )

        employee = instance.adjustment_request.employee
        shift = employee.office_time
        tz = pytz.timezone("Asia/Dhaka")

        # Convert all times to local timezone for accurate comparison
        local_requested_time = instance.requested_arrival_time.astimezone(tz)
        adjustment_date = local_requested_time.date()

        # Get records in the local date context
        start_datetime = tz.localize(datetime.combine(adjustment_date, time.min))
        end_datetime = tz.localize(datetime.combine(adjustment_date, time.max))

        attendance_records = AttendanceData.objects.filter(
            employee=employee, timestamp__range=(start_datetime, end_datetime)
        ).order_by("timestamp")

        target_record = None
        for record in attendance_records:
            local_record_time = record.timestamp.astimezone(tz)
            local_shift_start = tz.localize(
                datetime.combine(local_record_time.date(), shift.office_start_time)
            )

            if local_record_time >= local_shift_start:
                target_record = record
                break

        if target_record:
            # print(f"Deleting record: {target_record.timestamp.astimezone(tz)}")
            target_record.delete()

        instance.adjustment_request.status = "rejected"
        instance.adjustment_request.save()


def _get_working_days(office_days_str):
    """
    Helper function to parse office_days string and return a set of working day indices.
    """
    office_days_str = office_days_str or "Sunday-Thursday"
    days_map = {
        "sunday": 6,
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
    }
    if "-" in office_days_str:
        start_day, end_day = office_days_str.lower().split("-")
        start_idx = days_map.get(start_day.strip(), 6)
        end_idx = days_map.get(end_day.strip(), 3)
        if start_idx <= end_idx:
            working_days = list(range(start_idx, end_idx + 1))
        else:
            working_days = list(range(start_idx, 7)) + list(range(0, end_idx + 1))
    else:
        working_days = [
            days_map.get(day.lower().strip(), 6) for day in office_days_str.split(",")
        ]
    return set(working_days)


def _is_holiday_for_employee(date, employee):
    """
    Checks if the given date is a holiday for the employee based on the Holiday model.
    """
    holidays = Holiday.objects.filter(from_date__lte=date, to_date__gte=date)
    for holiday in holidays:
        if holiday.is_applicable_to_employee(employee):
            return True
    return False


def _calculate_half_day_midpoint(shift_date, employee_shift):
    """
    Calculate the midpoint of a shift as a timezone-aware datetime.
    For a 9-17 shift, returns 13:00.  For a 22-06 overnight shift, returns 02:00 next day.
    """
    shift_start = datetime.combine(shift_date, employee_shift.office_start_time)
    shift_end = datetime.combine(shift_date, employee_shift.office_end_time)

    is_overnight = employee_shift.office_end_time < employee_shift.office_start_time
    if is_overnight:
        shift_end += timedelta(days=1)

    shift_duration = (shift_end - shift_start).total_seconds()
    midpoint_dt = shift_start + timedelta(seconds=shift_duration / 2)

    return timezone.make_aware(midpoint_dt, timezone.get_current_timezone())


def _get_half_day_adjusted_start_time(employee, shift_date, employee_shift):
    """
    Check if the employee has an approved first-half half-day leave on *shift_date*.
    If so, return the midpoint of the shift (the adjusted effective start time).
    Returns None when no adjustment is needed.
    """
    from leave.models import LeaveRequest

    has_approved_half_day = LeaveRequest.objects.filter(
        employee=employee,
        is_half_day=True,
        half_day_period="first half",
        start_date__lte=shift_date,
        end_date__gte=shift_date,
        status__iexact="approved",
    ).exists()

    if not has_approved_half_day:
        return None

    return _calculate_half_day_midpoint(shift_date, employee_shift)


def _get_half_day_adjusted_end_time(employee, shift_date, employee_shift):
    """
    Check if the employee has an approved second-half half-day leave on *shift_date*.
    If so, return the midpoint of the shift (the adjusted effective end time).
    Returns None when no adjustment is needed.
    """
    from leave.models import LeaveRequest

    has_approved_half_day = LeaveRequest.objects.filter(
        employee=employee,
        is_half_day=True,
        half_day_period="second half",
        start_date__lte=shift_date,
        end_date__gte=shift_date,
        status__iexact="approved",
    ).exists()

    if not has_approved_half_day:
        return None

    return _calculate_half_day_midpoint(shift_date, employee_shift)


@receiver(post_save, sender=AttendanceData)
def update_attendance_history(sender, instance, created, **kwargs):
    """
    Signal handler to calculate and store/update attendance data in AttendanceHistory
    when an AttendanceData record is saved.
    """
    if not instance.employee or not instance.timestamp:
        return

    employee = instance.employee
    employee_shift = employee.office_time
    if not employee_shift:
        return

    # Added rfid_or_machine_code and device_serial_number to AttendanceData
    if instance.rfid_or_machine_code:
        rfid_or_machine_code = instance.rfid_or_machine_code
    else:
        rfid_or_machine_code = None

    if instance.device_serial_number:
        device_serial_number = instance.device_serial_number
    else:
        device_serial_number = None

    # Added local_ip_address to AttendanceData
    if instance.local_ip_address:
        local_ip_address = instance.local_ip_address
    else:
        local_ip_address = None

    # Determine shift date and boundaries
    today = instance.timestamp.date()
    is_overnight = employee_shift.office_end_time < employee_shift.office_start_time
    shift_date = today

    # Define check-in and check-out windows for today
    check_in_start_dt = timezone.make_aware(
        datetime.combine(today, employee_shift.check_in_start_time),
        timezone.get_current_timezone(),
    )
    check_in_end_dt = timezone.make_aware(
        datetime.combine(today, employee_shift.check_in_end_time),
        timezone.get_current_timezone(),
    )
    # Adjust check-in end time for overnight shifts
    if employee_shift.check_in_end_time <= employee_shift.check_in_start_time:
        check_in_end_dt += timedelta(days=1)

    check_out_start_dt = timezone.make_aware(
        datetime.combine(today, employee_shift.check_out_start_time),
        timezone.get_current_timezone(),
    )
    check_out_end_dt = timezone.make_aware(
        datetime.combine(today, employee_shift.check_out_end_time),
        timezone.get_current_timezone(),
    )

    if employee_shift.check_out_end_time <= employee_shift.check_out_start_time:
        check_out_end_dt += timedelta(days=1)

    # For overnight shifts, check if the timestamp is in the check-out window of the previous day's shift
    if is_overnight:
        # Check if timestamp is in the check-out window of the previous day's shift
        prev_day = today - timedelta(days=1)

        prev_day_check_out_start_dt = timezone.make_aware(
            datetime.combine(prev_day, employee_shift.check_out_start_time),
            timezone.get_current_timezone(),
        )

        prev_day_check_out_end_dt = timezone.make_aware(
            datetime.combine(today, employee_shift.check_out_end_time),
            timezone.get_current_timezone(),
        )

        if (
            prev_day_check_out_start_dt
            <= instance.timestamp
            <= prev_day_check_out_end_dt
        ):
            shift_date = prev_day
            # Recalculate boundaries for the previous day
            check_in_start_dt = timezone.make_aware(
                datetime.combine(shift_date, employee_shift.check_in_start_time),
                timezone.get_current_timezone(),
            )
            check_in_end_dt = timezone.make_aware(
                datetime.combine(shift_date, employee_shift.check_in_end_time),
                timezone.get_current_timezone(),
            )
            if employee_shift.check_in_end_time <= employee_shift.check_in_start_time:
                check_in_end_dt += timedelta(days=1)
            check_out_start_dt = prev_day_check_out_start_dt
            check_out_end_dt = prev_day_check_out_end_dt

    # Determine if the shift date is a working day or holiday
    working_days = _get_working_days(employee.office_days)
    is_working_day = shift_date.weekday() in working_days
    is_holiday = _is_holiday_for_employee(shift_date, employee)

    # Get or create AttendanceHistory record for the shift date
    attendance_history, created = AttendanceHistory.objects.get_or_create(
        employee=employee,
        date=shift_date,
        defaults={
            "is_late": False,
            "check_in_time": None,
            "check_out_time": None,
            "late_by": None,
            "early_out_by": None,
            "is_holiday": is_holiday,  # Set correct value from the start
            # Set correct value from the start
            "is_weekend": not is_working_day and not is_holiday,
            "status": (
                "Holiday"
                if is_holiday
                else "Weekend" if not is_working_day else "Absent"
            ),
            "remarks": instance.remarks,
            "rfid_or_machine_code": rfid_or_machine_code,
            "local_ip_address": local_ip_address,
            "device_serial_number": device_serial_number,
        },
    )

    # Update remarks to indicate if attendance occurred on a holiday or weekend
    day_type_remark = ""
    comp_leave_check_needed = False
    if is_holiday:
        day_type_remark = "Attendance recorded on a holiday"
    elif not is_working_day:
        day_type_remark = "Attendance recorded on a weekend"

    # For existing records, ensure holiday/weekend flags are set correctly
    # and check if we need to trigger compensatory leave logic
    if not created:
        if is_holiday and not attendance_history.is_holiday:
            attendance_history.is_holiday = True
            comp_leave_check_needed = True
        if not is_working_day and not is_holiday and not attendance_history.is_weekend:
            attendance_history.is_weekend = True
            comp_leave_check_needed = True

    # Skip status updates if the current status is 'Early Leave' or 'On Leave'
    # protected_statuses = ['Early Leave', 'On Leave', 'Holiday', 'Weekend']
    protected_statuses = ["Holiday", "Weekend"]
    can_update_status = attendance_history.status not in protected_statuses
    check_in_added = False

    # Handle check-in
    if check_in_start_dt <= instance.timestamp <= check_in_end_dt:
        # Only update check-in if this is the first or earliest check-in
        if (
            not attendance_history.check_in_time
            or instance.timestamp < attendance_history.check_in_time
        ):
            old_check_in = attendance_history.check_in_time
            attendance_history.check_in_time = instance.timestamp
            attendance_history.rfid_or_machine_code = rfid_or_machine_code
            attendance_history.local_ip_address = local_ip_address
            attendance_history.device_serial_number = device_serial_number

            # Mark that check-in was added for the first time
            if old_check_in is None:
                check_in_added = True

            # Calculate lateness
            office_start_time = timezone.make_aware(
                datetime.combine(shift_date, employee_shift.office_start_time),
                timezone.get_current_timezone(),
            )

            # Check for approved half-day first-half leave adjustment
            half_day_adjusted_start = _get_half_day_adjusted_start_time(
                employee, shift_date, employee_shift
            )
            if half_day_adjusted_start:
                office_start_time = half_day_adjusted_start
                attendance_history.half_day_adjusted = True

            consideration_minutes = employee_shift.office_start_time_consideration or 0
            time_difference = (
                instance.timestamp - office_start_time
            ).total_seconds() / 60

            attendance_history.is_late = time_difference > consideration_minutes
            if attendance_history.is_late:
                late_duration = instance.timestamp - office_start_time
                attendance_history.late_by = late_duration
                attendance_history.status = "Late"
            else:
                attendance_history.late_by = None

            if can_update_status:
                if attendance_history.is_late:
                    attendance_history.status = "Late"
                else:
                    attendance_history.status = "Present"

    # Handle check-out
    if (
        check_out_start_dt <= instance.timestamp <= check_out_end_dt
        and not attendance_history.check_in_time == instance.timestamp
    ):
        # Update check-out if this is the latest check-out
        if (
            not attendance_history.check_out_time
            or instance.timestamp > attendance_history.check_out_time
        ):
            attendance_history.check_out_time = instance.timestamp
            attendance_history.rfid_or_machine_code = rfid_or_machine_code
            attendance_history.local_ip_address = local_ip_address
            attendance_history.device_serial_number = device_serial_number

            # Calculate early out only if status can be updated
            if can_update_status:
                office_end_time = timezone.make_aware(
                    datetime.combine(shift_date, employee_shift.office_end_time),
                    timezone.get_current_timezone(),
                )
                if is_overnight:
                    office_end_time += timedelta(days=1)

                # Check for approved second-half half-day leave
                half_day_adjusted_end = _get_half_day_adjusted_end_time(
                    employee, shift_date, employee_shift
                )
                if half_day_adjusted_end:
                    office_end_time = half_day_adjusted_end
                    attendance_history.half_day_adjusted = True

                consideration_minutes = (
                    employee_shift.office_end_time_consideration or 0
                )
                early_threshold = office_end_time - timedelta(
                    minutes=consideration_minutes
                )

                if instance.timestamp < early_threshold:
                    early_out_duration = office_end_time - instance.timestamp
                    attendance_history.early_out_by = early_out_duration
                    attendance_history.status = "Early Leave"
                else:
                    attendance_history.early_out_by = None
                    if attendance_history.is_late:
                        attendance_history.status = "Late"
                    else:
                        attendance_history.status = "Present"

    # Calculate half-day status if both check-in and check-out exist and status can be updated
    if (
        can_update_status
        and attendance_history.check_in_time
        and attendance_history.check_out_time
    ):
        shift_start_time = timezone.make_aware(
            datetime.combine(shift_date, employee_shift.office_start_time),
            timezone.get_current_timezone(),
        )
        shift_end_time = timezone.make_aware(
            datetime.combine(shift_date, employee_shift.office_end_time),
            timezone.get_current_timezone(),
        )
        if is_overnight:
            shift_end_time += timedelta(days=1)

        shift_duration = (shift_end_time - shift_start_time).total_seconds()
        half_shift_hours = shift_duration / (2 * 3600)

        actual_duration = (
            attendance_history.check_out_time - attendance_history.check_in_time
        ).total_seconds()
        actual_hours = actual_duration / 3600

        tolerance_hours = 1
        if abs(actual_hours - half_shift_hours) <= tolerance_hours:
            attendance_history.status = "Half Day"

    # Update remarks if provided
    if instance.remarks:
        attendance_history.remarks = instance.remarks

    attendance_history.save()

    # Manual compensatory leave check for:
    # 1. Existing records that had their holiday/weekend flags updated
    # 2. Records where check-in was added for the first time to a holiday/weekend
    if (
        comp_leave_check_needed or (check_in_added and not created)
    ) and attendance_history.check_in_time:
        from leave.models import CompensatoryLeaveBalance, CompensatoryLeaveEarned

        # Check if compensatory leave should be created
        if (
            (attendance_history.is_holiday or attendance_history.is_weekend)
            and attendance_history.employee.employment_type
            and attendance_history.employee.employment_type.name
            in ["General Staff (Regular)", "General Staff (Probation)"]
        ):

            # Get or create compensatory leave balance
            balance, _ = CompensatoryLeaveBalance.objects.get_or_create(
                employee=attendance_history.employee,
                defaults={"total_earned": 0, "total_used": 0, "current_balance": 0},
            )

            # Check if compensatory leave already exists for this date
            if not CompensatoryLeaveEarned.objects.filter(
                employee=attendance_history.employee,
                earned_date=attendance_history.date,
            ).exists():

                # Add compensatory leave
                balance.add_comp_leave(attendance_history.date)

                # Link the attendance record
                comp_leave = CompensatoryLeaveEarned.objects.get(
                    employee=attendance_history.employee,
                    earned_date=attendance_history.date,
                )
                comp_leave.related_attendance = attendance_history
                comp_leave.save()


def bulk_update_attendance_history(instances):
    with transaction.atomic():
        for instance in instances:
            update_attendance_history(
                sender=AttendanceData, instance=instance, created=True
            )
