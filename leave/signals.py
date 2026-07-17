from datetime import timedelta
from django.db.models.signals import post_save, post_delete, pre_save
from django.utils import timezone
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from attendance.models import AttendanceHistory
from employee.models import Employee
from .utils import LeaveBalanceCalculator
from .models import (
    CompensatoryLeaveBalance,
    CompensatoryLeaveEarned,
    LeaveApproval,
    LeavePolicy,
    LeaveRequest,
    LeaveReset,
    LeaveTransfer,
    SupervisorLevel,
)
from django.db.models.signals import m2m_changed
from employee.signals import handle_employee_supervisor_levels


# Signal to ensure supervisor is added to employee's supervisor list when SupervisorLevel is created or updated
@receiver(post_save, sender=SupervisorLevel)
def add_supervisor_to_employee(sender, instance, created, **kwargs):
    """When a SupervisorLevel is created/updated, ensure supervisor is in employee's supervisor list"""
    if (
        instance.supervisor
        and instance.supervisor not in instance.employee.supervisor.all()
    ):
        # Temporarily disconnect the m2m_changed signal to prevent infinite recursion

        m2m_changed.disconnect(
            handle_employee_supervisor_levels, sender=Employee.supervisor.through
        )
        try:
            instance.employee.supervisor.add(instance.supervisor)
        finally:
            # Reconnect the signal
            m2m_changed.connect(
                handle_employee_supervisor_levels,
                sender=Employee.supervisor.through,
            )


@receiver(post_delete, sender=SupervisorLevel)
def remove_supervisor_if_no_levels(sender, instance, **kwargs):
    """When a SupervisorLevel is deleted, remove supervisor from employee if no longer needed"""
    if instance.supervisor:
        # Check if this supervisor exists in any other levels for this employee
        other_levels = SupervisorLevel.objects.filter(
            employee=instance.employee, supervisor=instance.supervisor
        ).exists()

        if not other_levels:
            instance.employee.supervisor.remove(instance.supervisor)


# Signal to update leave request status after a LeaveApproval is saved
@receiver(post_save, sender=LeaveApproval)
def update_leave_request_status(sender, instance, **kwargs):
    instance.leave_request.update_status()


# Signal to recalculate attendance when a half-day first-half leave is approved
def _recalculate_lateness_for_half_day(attendance_history, employee_shift, shift_date):
    """
    Recalculate lateness for an AttendanceHistory record using the midpoint
    of the shift as the effective start time (first-half half-day leave).
    Works for both day shifts and overnight shifts.
    """
    from attendance.signals import _calculate_half_day_midpoint

    adjusted_start = _calculate_half_day_midpoint(shift_date, employee_shift)

    consideration_minutes = employee_shift.office_start_time_consideration or 0
    time_difference = (
        attendance_history.check_in_time - adjusted_start
    ).total_seconds() / 60

    attendance_history.half_day_adjusted = True
    attendance_history.is_late = time_difference > consideration_minutes

    if attendance_history.is_late:
        late_duration = attendance_history.check_in_time - adjusted_start
        attendance_history.late_by = late_duration
        attendance_history.status = "Late"
    else:
        attendance_history.late_by = None
        attendance_history.status = "Present"

    attendance_history.save()


def _recalculate_early_out_for_half_day(attendance_history, employee_shift, shift_date):
    """
    Recalculate early-out for an AttendanceHistory record using the midpoint
    of the shift as the effective end time (second-half half-day leave).
    Works for both day shifts and overnight shifts.
    """
    from attendance.signals import _calculate_half_day_midpoint

    adjusted_end = _calculate_half_day_midpoint(shift_date, employee_shift)

    consideration_minutes = employee_shift.office_end_time_consideration or 0
    early_threshold = adjusted_end - timedelta(minutes=consideration_minutes)

    attendance_history.half_day_adjusted = True

    if attendance_history.check_out_time < early_threshold:
        early_out_duration = adjusted_end - attendance_history.check_out_time
        attendance_history.early_out_by = early_out_duration
        attendance_history.status = "Early Leave"
    else:
        attendance_history.early_out_by = None
        if attendance_history.is_late:
            attendance_history.status = "Late"
        else:
            attendance_history.status = "Present"

    attendance_history.save()


@receiver(post_save, sender=LeaveRequest)
def recalculate_attendance_on_half_day_approval(sender, instance, **kwargs):
    """
    When a half-day leave request is approved, recalculate the
    AttendanceHistory for the affected date(s):
    - First half: adjust lateness using shift midpoint as effective start time
    - Second half: adjust early-out using shift midpoint as effective end time
    """
    if not (
        instance.is_half_day
        and instance.half_day_period in ("first half", "second half")
        and instance.status == "approved"
    ):
        return

    # Only act when the status *just* changed to approved
    previous_status = getattr(instance, "previous_status", None)
    if previous_status == "approved":
        return  # already was approved – nothing to recalculate

    employee = instance.employee
    employee_shift = employee.office_time
    if not employee_shift:
        return

    # Iterate through every date in the leave range
    current_date = instance.start_date
    while current_date <= instance.end_date:
        try:
            attendance_history = AttendanceHistory.objects.get(
                employee=employee, date=current_date
            )
        except AttendanceHistory.DoesNotExist:
            current_date += timedelta(days=1)
            continue

        if instance.half_day_period == "first half":
            if attendance_history.check_in_time:
                _recalculate_lateness_for_half_day(
                    attendance_history, employee_shift, current_date
                )
        elif instance.half_day_period == "second half":
            if attendance_history.check_out_time:
                _recalculate_early_out_for_half_day(
                    attendance_history, employee_shift, current_date
                )

        current_date += timedelta(days=1)


# Signal to automatically handle transfers when leave group changes
@receiver(pre_save, sender=Employee)
def handle_leave_group_change(sender, instance, **kwargs):
    if not instance.pk:  # New employee, nothing to transfer
        return

    try:
        old_employee = Employee.objects.get(pk=instance.pk)
    except Employee.DoesNotExist:
        return

    if old_employee.leave_group == instance.leave_group:  # No change
        return

    current_date = timezone.now().date()

    # Get the current reset period
    reset_start, reset_end = LeaveReset.get_current_period(current_date)

    # Get all existing transfers for this employee in current reset period
    existing_transfers = LeaveTransfer.objects.filter(
        employee=instance, year__range=(reset_start, reset_end)
    ).order_by("created_at")

    if existing_transfers.exists():
        first_transfer = existing_transfers.first()
        original_leave_group = first_transfer.from_leave_group

        # Case 1: Returning to original group - delete all transfers
        if instance.leave_group == original_leave_group:
            existing_transfers.delete()
            return

        # Case 2: Moving from current group to another group - update last transfer
        last_transfer = existing_transfers.last()
        if last_transfer.to_leave_group == old_employee.leave_group:
            _update_existing_transfer(
                employee=instance,
                old_employee=old_employee,
                current_date=current_date,
                existing_transfer=last_transfer,
                reset_start=reset_start,
                reset_end=reset_end,
            )
            return

    # Default case: create new transfers or update existing ones
    _create_or_update_transfers(
        instance, old_employee, current_date, reset_start, reset_end
    )


def _update_existing_transfer(
    employee, old_employee, current_date, existing_transfer, reset_start, reset_end
):
    """Updates an existing transfer record with new destination group"""
    new_policies = LeavePolicy.objects.filter(
        leave_groups=employee.leave_group, is_active=True
    )

    new_policy = new_policies.filter(
        leave_type_name=existing_transfer.to_leave_policy.leave_type_name
    ).first()

    if new_policy:
        total_used_days = _calculate_total_used_days_for_leave_type(
            employee,
            existing_transfer.to_leave_policy.leave_type_name,
            reset_start,
            reset_end,
        )

        existing_transfer.to_leave_group = employee.leave_group
        existing_transfer.to_leave_policy = new_policy
        existing_transfer.days_transferred = total_used_days
        existing_transfer.notes = (
            f"Updated: {existing_transfer.from_leave_group}→"
            f"{old_employee.leave_group}→{employee.leave_group}"
        )
        existing_transfer.save()


def _create_or_update_transfers(
    employee, old_employee, current_date, reset_start, reset_end
):
    """Creates new transfers or updates existing ones for each leave type"""
    old_policies = LeavePolicy.objects.filter(
        leave_groups=old_employee.leave_group, is_active=True
    )

    new_policies = LeavePolicy.objects.filter(
        leave_groups=employee.leave_group, is_active=True
    )

    for old_policy in old_policies:
        new_policy = new_policies.filter(
            leave_type_name=old_policy.leave_type_name
        ).first()

        if new_policy:
            existing_transfer = (
                LeaveTransfer.objects.filter(
                    employee=employee,
                    from_leave_policy__leave_type_name=old_policy.leave_type_name,
                    year__range=(reset_start, reset_end),
                )
                .order_by("-created_at")
                .first()
            )

            total_used_days = _calculate_total_used_days_for_leave_type(
                employee, old_policy.leave_type_name, reset_start, reset_end
            )

            if existing_transfer:
                # Update existing transfer
                existing_transfer.to_leave_group = employee.leave_group
                existing_transfer.to_leave_policy = new_policy
                existing_transfer.days_transferred = total_used_days
                existing_transfer.notes = (
                    f"Updated: {existing_transfer.from_leave_group}→"
                    f"{employee.leave_group}"
                )
                existing_transfer.save()
            else:
                # Create new transfer if days were used
                if total_used_days > 0:
                    LeaveTransfer.objects.create(
                        employee=employee,
                        from_leave_policy=old_policy,
                        to_leave_policy=new_policy,
                        from_leave_group=old_employee.leave_group,
                        to_leave_group=employee.leave_group,
                        days_transferred=total_used_days,
                        year=current_date,
                        notes=f"Transfer: {old_employee.leave_group}→{employee.leave_group}",
                    )


def _calculate_total_used_days_for_leave_type(
    employee, leave_type_name, reset_start, reset_end
):
    """
    Calculates total used days for a leave type within the current reset period
    """
    approved_leaves = LeaveRequest.objects.filter(
        employee=employee,
        leave_policy__leave_type_name=leave_type_name,
        status="approved",
        start_date__gte=reset_start,
        end_date__lte=reset_end,
    )

    total_used = 0
    for leave_request in approved_leaves:
        days = LeaveBalanceCalculator.calculate_leave_days(
            leave_request.start_date,
            leave_request.end_date,
            employee,
            leave_request.leave_policy,
            leave_request.is_half_day,
        )
        total_used += days

    return total_used


def _calculate_used_days_for_policy(employee, policy, reset_start, reset_end):
    """Calculates used days for a specific policy within reset period"""
    approved_leaves = LeaveRequest.objects.filter(
        employee=employee,
        leave_policy=policy,
        status="approved",
        start_date__gte=reset_start,
        end_date__lte=reset_end,
    )

    return sum(
        LeaveBalanceCalculator.calculate_leave_days(
            leave.start_date, leave.end_date, employee, policy, leave.is_half_day
        )
        for leave in approved_leaves
    )


# Signals for Compensatory Leave Balance updates
@receiver(post_save, sender=AttendanceHistory)
def create_compensatory_leave(sender, instance, created, **kwargs):
    """
    Create compensatory leave when employee works on Holiday or Weekend with both check-in and check-out
    """
    # Only process if this is a holiday/weekend with both check-in and check-out time
    if (
        (instance.is_holiday or instance.is_weekend)
        and instance.check_in_time is not None
        and instance.check_out_time is not None
        and instance.employee.employment_type
        and instance.employee.employment_type.name
        in ["General Staff (Regular)", "General Staff (Probation)"]
    ):
        # Check if compensatory leave already exists for this date
        if CompensatoryLeaveEarned.objects.filter(
            employee=instance.employee, earned_date=instance.date
        ).exists():
            return

        # Calculate hours worked on holiday/weekend
        time_difference = instance.check_out_time - instance.check_in_time
        hours_worked = time_difference.total_seconds() / 3600

        # Determine days earned based on hours worked
        if hours_worked >= 6:
            days_earned = 1
        else:
            # No hours worked, no compensatory leave earned
            return

        # Get or create compensatory leave balance
        balance, created = CompensatoryLeaveBalance.objects.get_or_create(
            employee=instance.employee,
            defaults={"total_earned": 0, "total_used": 0, "current_balance": 0},
        )

        # Add compensatory leave days to balance
        balance.add_comp_leave(instance.date, days_earned)

        # Link the attendance record
        comp_leave = CompensatoryLeaveEarned.objects.get(
            employee=instance.employee, earned_date=instance.date
        )
        comp_leave.related_attendance = instance
        comp_leave.save()


@receiver(pre_save, sender=LeaveRequest)
def handle_compensatory_leave_request(sender, instance, **kwargs):
    """
    Handle compensatory leave request - use comp leave balance if available
    """
    if (
        instance.leave_policy
        and instance.leave_policy.leave_type_name == "Compensatory Leave"
        and instance.status == "approved"
    ):

        # Calculate leave days
        leave_days = (instance.end_date - instance.start_date).days + 1
        if instance.is_half_day:
            leave_days = 0.5

        # Get employee's comp leave balance
        try:
            balance = CompensatoryLeaveBalance.objects.get(employee=instance.employee)
            balance.clean_expired_leaves()  # Clean expired leaves first

            if float(balance.current_balance) >= leave_days:
                balance.use_comp_leave(leave_days)
            else:
                raise ValidationError(
                    f"Insufficient compensatory leave balance. Available: {balance.current_balance}, Required: {leave_days}"
                )

        except CompensatoryLeaveBalance.DoesNotExist:
            raise ValidationError(
                "No compensatory leave balance found for this employee"
            )


# Signal for updating compensatory leave balance
@receiver(post_delete, sender=CompensatoryLeaveEarned)
def update_balance_on_leave_deletion(sender, instance, **kwargs):
    """
    Update compensatory leave balance when a CompensatoryLeaveEarned record is deleted
    """
    try:
        balance = CompensatoryLeaveBalance.objects.get(employee=instance.employee)

        # Only adjust balance if the leave wasn't used or expired
        if not instance.is_used and not instance.is_expired:
            balance.total_earned -= instance.days_earned
            balance.current_balance -= instance.days_earned
            balance.save()

        # If the leave was used, we might also want to adjust total_used
        elif instance.is_used:
            balance.total_used -= instance.days_used
            balance.save()

    except CompensatoryLeaveBalance.DoesNotExist:
        # If balance doesn't exist, we can't update it
        pass
