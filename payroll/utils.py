"""
Payroll generation utilities.

All heavy computation is done here so that views stay thin.
Queries are bulk-fetched up front to avoid N+1 problems.
"""

import calendar
import logging
import threading
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict
from django.db import close_old_connections
from attendance.models import AttendanceHistory
from employee.models import Employee, Salary
from holiday.models import Holiday
from leave.models import LeaveRequest
from leave.utils import LeaveBalanceCalculator
from payroll.models import Payroll
import math

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MONTH_NAMES = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def get_month_date_range(month: int, year: int):
    """Return (first_day, last_day) for the given month/year."""
    days_in_month = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, days_in_month)


def get_holidays_for_employee(employee, holidays_in_month):
    """
    Given a pre-fetched list of Holiday objects that overlap with the target
    month, return the set of dates that are holidays for *this* employee.
    """
    holiday_dates = set()
    for h in holidays_in_month:
        if h.is_applicable_to_employee(employee):
            d = h.from_date
            while d <= h.to_date:
                holiday_dates.add(d)
                d += timedelta(days=1)
    return holiday_dates


# ---------------------------------------------------------------------------
# Bulk data fetchers – run once per generation request
# ---------------------------------------------------------------------------


def _fetch_active_employees(employee_ids=None):
    """All active employees with related fields pre-loaded.

    If *employee_ids* is given (a list/set of PKs), only those employees are
    returned — provided they are also active.
    """
    qs = Employee.objects.filter(status="active").select_related(
        "user", "department", "designation", "location", "office_time"
    )
    if employee_ids is not None:
        qs = qs.filter(pk__in=employee_ids)
    return qs


def _fetch_attendance_map(start_date, end_date, employee_pks):
    """
    Return {employee_pk: [AttendanceHistory, ...]} for the date range.
    Single query, no N+1.
    """
    qs = AttendanceHistory.objects.filter(
        employee__pk__in=employee_pks,
        date__gte=start_date,
        date__lte=end_date,
    ).select_related("employee")
    mapping = defaultdict(list)
    for ah in qs:
        mapping[ah.employee_id].append(ah)
    return mapping


def _fetch_leave_map(start_date, end_date, employee_pks):
    """
    Return {employee_pk: [LeaveRequest, ...]} for approved leaves that
    overlap with the date range.  Single query.
    """
    qs = LeaveRequest.objects.filter(
        employee__pk__in=employee_pks,
        status="approved",
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).select_related("leave_policy", "employee")
    mapping = defaultdict(list)
    for lr in qs:
        mapping[lr.employee_id].append(lr)
    return mapping


def _fetch_holidays_in_range(start_date, end_date):
    """All holidays overlapping with the date range (single query)."""
    return list(
        Holiday.objects.filter(
            from_date__lte=end_date,
            to_date__gte=start_date,
        ).prefetch_related(
            "branches",
            "designations",
            "departments",
            "assigned_employees",
            "excluded_employees",
        )
    )


def _fetch_effective_salary_map(employee_pks, payroll_end_date):
    """
    Return {employee_pk: Salary} mapping, picking the salary record that was
    **effective** for the payroll month.

    Selection logic (per employee):
    1. Salary records whose ``effective_date`` is on or before ``payroll_end_date``
       are considered; the one with the most recent ``effective_date`` wins.
    2. If all records have ``effective_date = NULL`` (legacy data), the record
       with the highest PK (most recently created) is used instead.
    3. Records whose ``effective_date`` is **after** ``payroll_end_date`` are
       ignored (future salary revisions should not affect past months).
    """
    salaries = Salary.objects.filter(employee__pk__in=employee_pks).select_related(
        "employee"
    )
    # Group by employee
    grouped = defaultdict(list)
    for sal in salaries:
        grouped[sal.employee_id].append(sal)

    mapping = {}
    for emp_pk, sal_list in grouped.items():
        # Separate records with and without effective_date
        with_date = [s for s in sal_list if s.effective_date is not None]
        without_date = [s for s in sal_list if s.effective_date is None]

        if with_date:
            # Filter to those effective on or before the payroll month end
            eligible = [s for s in with_date if s.effective_date <= payroll_end_date]
            if eligible:
                # Pick the one with the most recent effective_date
                mapping[emp_pk] = max(eligible, key=lambda s: s.effective_date)
                continue
            # If no record is effective yet, fall through to without_date

        # Fallback: use the most recently created record (highest PK)
        if without_date:
            mapping[emp_pk] = max(without_date, key=lambda s: s.pk)
        elif with_date:
            # All records have future effective_date but no null ones exist
            # Pick the one with the earliest effective_date as best effort
            mapping[emp_pk] = min(with_date, key=lambda s: s.effective_date)

    return mapping


def _fetch_existing_payrolls(month_name, year, employee_pks):
    """Return {employee_pk: Payroll} for existing records of the month/year."""
    qs = Payroll.objects.filter(
        payroll_month=month_name,
        payroll_year=year,
        employee__pk__in=employee_pks,
    ).select_related("employee")
    return {p.employee_id: p for p in qs}


# ---------------------------------------------------------------------------
# Per-employee calculation
# ---------------------------------------------------------------------------


def _compute_employee_payroll(
    employee,
    start_date,
    end_date,
    attendance_records,
    leave_requests,
    holidays_in_month,
    salary_record,
    include_festival_bonus,
    include_performance_bonus,
):
    """
    Compute all payroll fields for one employee.
    Returns a dict ready to be set on a Payroll instance.

    When the caller provides an explicit start/end range (instead of a
    month/year), the resulting dictionary will use the actual span for
    `days_of_month` and `working_days`.  Prior versions always reported the
    full calendar month which was confusing for partial‑period payrolls.

    Late deduction logic has evolved:
    * `salary_record.late_count_threshold` determines how many late
      occurrences constitute one deduction unit.  e.g. threshold=3 means a
      deduction is applied once every three late days rather than per-day.
    * `salary_record.is_late_during_holiday` controls whether lateness on
      holidays AND weekends should count toward the threshold/deduction.  If
      False, holiday and weekend lateness is ignored when calculating the
      effective late count.
    """
    # number of days in the provided range (may be partial month)
    days_in_range = (end_date - start_date).days + 1
    weekend_day_nums = LeaveBalanceCalculator.get_weekend_days(employee)
    employee_holidays = get_holidays_for_employee(employee, holidays_in_month)

    # Restrict holiday dates to the range for classification
    employee_holidays = {d for d in employee_holidays if start_date <= d <= end_date}

    # ---- Classify range days ------------------------------------------------
    weekend_count = 0
    holiday_count = 0
    working_days_range = 0

    for offset in range(days_in_range):
        d = start_date + timedelta(days=offset)
        is_weekend = d.weekday() in weekend_day_nums
        is_holiday = d in employee_holidays

        if is_weekend:
            weekend_count += 1
        elif is_holiday:
            holiday_count += 1
        else:
            working_days_range += 1

    # compute full-month values for proration and reporting
    full_start, full_end = get_month_date_range(end_date.month, end_date.year)
    days_in_month = (full_end - full_start).days + 1
    # classify full month working days (ignore holidays outside the month range)
    full_holidays = get_holidays_for_employee(
        employee,
        [
            h
            for h in holidays_in_month
            if h.from_date <= full_end and h.to_date >= full_start
        ],
    )
    working_days_full = 0
    temp = full_start
    while temp <= full_end:
        if temp.weekday() not in weekend_day_nums and temp not in full_holidays:
            working_days_full += 1
        temp += timedelta(days=1)

    # decide whether range is full month
    is_full_month = start_date == full_start and end_date == full_end
    if is_full_month:
        working_days = working_days_full
    else:
        # report actual working days within the provided range
        working_days = working_days_range

    # ---- Attendance analysis (from AttendanceHistory) ---------------------

    present_days = 0  # counts only normal working-day presence
    late_days = 0
    # late occurrences that happened on a holiday or weekend; used only for threshold
    holiday_late_days = 0
    weekend_late_days = 0
    holiday_present_days = 0
    weekend_present_days = 0

    for ah in attendance_records:
        d = ah.date
        is_weekend = d.weekday() in weekend_day_nums
        is_holiday = d in employee_holidays

        if is_weekend:
            # Employee worked on a weekend
            if ah.status in ("Present", "Late"):
                weekend_present_days += 1
            # count lateness on weekend separately
            if getattr(ah, "is_late", False):
                weekend_late_days += 1
        elif is_holiday:
            # Employee worked on a holiday
            if ah.status in ("Present", "Late"):
                holiday_present_days += 1
            # count lateness separately; this is excluded from the usual "late_days"
            if getattr(ah, "is_late", False):
                holiday_late_days += 1
        else:
            # Normal working day: count presence and lateness separately.
            if ah.status in ("Present", "Late"):
                present_days += 1
            # Count lateness from the boolean flag on AttendanceHistory (source of truth)
            if getattr(ah, "is_late", False):
                late_days += 1

    # ---- Leave analysis ---------------------------------------------------
    leave_breakdown = {}
    leave_days_set = set()

    for lr in leave_requests:
        policy_name = lr.leave_policy.leave_type_name if lr.leave_policy else "Unknown"
        eff_start = max(lr.start_date, start_date)
        eff_end = min(lr.end_date, end_date)
        d = eff_start
        days_count = Decimal("0")
        while d <= eff_end:
            is_weekend = d.weekday() in weekend_day_nums
            is_holiday = d in employee_holidays

            if not is_weekend and not is_holiday:
                # Only count working-day leaves
                if lr.is_half_day and eff_start == eff_end:
                    days_count += Decimal("0.5")
                else:
                    days_count += Decimal("1")
                leave_days_set.add(d)
            d += timedelta(days=1)

        if policy_name in leave_breakdown:
            leave_breakdown[policy_name] += float(days_count)
        else:
            leave_breakdown[policy_name] = float(days_count)

    total_leave_days = len(leave_days_set)

    # Absent days should be based on the *range* of dates, not full month
    absent_days_range = working_days_range - present_days - total_leave_days
    if absent_days_range < 0:
        absent_days_range = 0

    # The value returned in Payroll.absent_days uses range-based count; internal
    # working_days still reflects full-month value for reporting.
    absent_days = absent_days_range

    # Compute total present days (all attendance including weekends/holidays) BEFORE salary calculation
    # This is needed for the gross salary proration
    reported_present_days = present_days + holiday_present_days + weekend_present_days

    # ---- Salary components ------------------------------------------------
    zero = Decimal("0")

    # earnings components are taken directly from salary record
    basic = salary_record.basic or zero if salary_record else zero
    house_rent = salary_record.house_rent or zero if salary_record else zero
    conveyance = salary_record.conveyance or zero if salary_record else zero
    medical = salary_record.medical or zero if salary_record else zero
    gross_orig = math.ceil(basic + house_rent + conveyance + medical)

    # prorate gross using per-day salary when range is partial; components
    # themselves remain unchanged. Use ALL present days (including weekend/holiday attendance)
    if not is_full_month and working_days_full > 0 and gross_orig > 0:
        daily_rate = gross_orig / Decimal(working_days_full)
        gross = math.ceil(daily_rate * Decimal(reported_present_days))
    else:
        gross = gross_orig

    per_late = salary_record.late_deduction or zero if salary_record else zero
    per_absent = salary_record.absence_deduction or zero if salary_record else zero
    per_holiday_comp = (
        salary_record.holiday_compensation or zero if salary_record else zero
    )
    per_weekend_comp = (
        salary_record.weekday_compensation or zero if salary_record else zero
    )
    festival_bonus_amount = (
        (salary_record.festival_bonus or zero if salary_record else zero)
        if include_festival_bonus
        else zero
    )
    performance_bonus_amount = (
        (salary_record.performance_bonus or zero if salary_record else zero)
        if include_performance_bonus
        else zero
    )

    # ---- Late deduction with threshold & holiday policy ------------------
    # Salary record may specify a threshold (e.g. 3 days before deduction)
    threshold = 1
    include_holiday_late = False
    if salary_record:
        threshold = salary_record.late_count_threshold or 1
        # defensive: avoid zero
        if threshold <= 0:
            threshold = 1
        include_holiday_late = bool(salary_record.is_late_during_holiday)

    # effective late count to consider for deduction
    if include_holiday_late:
        effective_late_count = late_days + holiday_late_days + weekend_late_days
    else:
        effective_late_count = late_days

    num_groups = effective_late_count // threshold
    total_late_deduction = per_late * num_groups
    total_absence_deduction = per_absent * absent_days
    total_holiday_compensation = per_holiday_comp * holiday_present_days
    total_weekend_compensation = per_weekend_comp * weekend_present_days

    # Determine what should be reported as "late_days" in payroll record.
    reported_late_days = effective_late_count if include_holiday_late else late_days

    # Note: reported_present_days was already computed earlier for use in gross calculation

    net_salary = (
        gross
        + festival_bonus_amount
        + performance_bonus_amount
        + total_holiday_compensation
        + total_weekend_compensation
        - total_late_deduction
        - total_absence_deduction
    )

    # Ensure payroll is never negative — clamp to zero
    if net_salary < zero:
        net_salary = zero

    # ---- Tax deduction --------------------------------------------------
    tax_deduction = zero
    # tax is only charged when both percentage and threshold are provided
    if salary_record and getattr(salary_record, "tax_percentage", None):
        threshold = getattr(salary_record, "tax_amount_threshold", None)
        if threshold is not None and threshold > zero:
            if net_salary >= threshold:
                # percentage is stored as integer (e.g. 5 for 5%)
                tax_deduction = (
                    net_salary * Decimal(salary_record.tax_percentage) / Decimal(100)
                )
                # round to 2 decimals like other monetary fields
                tax_deduction = tax_deduction.quantize(Decimal("0.01"))
    total_transfer = net_salary - tax_deduction
    if total_transfer < zero:
        total_transfer = zero

    # `days_of_month` should reflect the length of the requested range,
    # not the full calendar month when using a date span.
    return {
        "days_of_month": days_in_range,
        "working_days": working_days,
        "present_days": reported_present_days,
        "late_days": reported_late_days,
        "absent_days": absent_days,
        "weekend_days": weekend_count,
        "holidays": holiday_count,
        "leave_breakdown": leave_breakdown or None,
        "basic": basic,
        "house_rent": house_rent,
        "conveyance": conveyance,
        "medical": medical,
        "gross_salary": gross,
        "festival_bonus": festival_bonus_amount,
        "performance_bonus": performance_bonus_amount,
        "absence_deduction": total_absence_deduction,
        "late_deduction": total_late_deduction,
        "holiday_compensation": total_holiday_compensation,
        "weekday_compensation": total_weekend_compensation,
        "net_salary": net_salary,
        "tax_deduction": tax_deduction,
        "total_transfer_amount": total_transfer,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_payroll(
    *,
    month=None,
    year=None,
    start_date=None,
    end_date=None,
    creator,
    include_festival_bonus=False,
    include_performance_bonus=False,
    employee_ids=None,
):
    """
    Generate (or update) payroll records for active employees for the given
    month/year or an explicit date range.

    Provide either `month`+`year` (legacy mode) OR `start_date`+`end_date`.

    Parameters
    ----------
    start_date, end_date : date | None
        When provided, the payroll is generated for the exact date range and
        the Salary record used is the one effective on `end_date`.

    employee_ids : list[int] | None
        When provided, payroll is generated only for the employees whose PKs
        are in this list (they must also be active).  When *None*, payroll is
        generated for **all** active employees.

    Returns a list of Payroll instances that were created or updated.
    """
    # Determine the date range to operate on (either month/year or explicit range)
    if start_date is not None or end_date is not None:
        if start_date is None or end_date is None:
            raise ValueError("Both start_date and end_date must be provided together.")
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        range_start, range_end = start_date, end_date
        payroll_month_name = MONTH_NAMES[range_end.month]
        payroll_year = range_end.year
    else:
        if month is None or year is None:
            raise ValueError(
                "Either month/year or start_date/end_date must be provided"
            )
        range_start, range_end = get_month_date_range(month, year)
        payroll_month_name = MONTH_NAMES[month]
        payroll_year = year

    # Before proceeding, prevent regeneration on a locked period regardless
    # of whether a full-month or partial-date range request was made.  The
    # payroll_month/year values are already determined above.
    if Payroll.objects.filter(
        payroll_month=payroll_month_name,
        payroll_year=payroll_year,
        is_locked=True,
    ).exists():
        raise ValueError(
            f"Payroll for {payroll_month_name} {payroll_year} is locked and cannot be regenerated."
        )

    # 1. Bulk-fetch all data up front (avoids N+1) -------------------------
    employees = list(_fetch_active_employees(employee_ids))
    if not employees:
        return []

    employee_pks = [e.pk for e in employees]

    attendance_map = _fetch_attendance_map(range_start, range_end, employee_pks)
    leave_map = _fetch_leave_map(range_start, range_end, employee_pks)
    holidays = _fetch_holidays_in_range(range_start, range_end)
    salary_map = _fetch_effective_salary_map(employee_pks, range_end)
    existing_payrolls = _fetch_existing_payrolls(
        payroll_month_name, payroll_year, employee_pks
    )

    # 2. Compute & upsert per employee -------------------------------------
    payrolls_to_create = []
    payrolls_to_update = []

    for emp in employees:
        data = _compute_employee_payroll(
            employee=emp,
            start_date=range_start,
            end_date=range_end,
            attendance_records=attendance_map.get(emp.pk, []),
            leave_requests=leave_map.get(emp.pk, []),
            holidays_in_month=holidays,
            salary_record=salary_map.get(emp.pk),
            include_festival_bonus=include_festival_bonus,
            include_performance_bonus=include_performance_bonus,
        )

        if emp.pk in existing_payrolls:
            # Update existing payroll
            payroll = existing_payrolls[emp.pk]
            payroll.payroll_month = payroll_month_name
            payroll.payroll_year = payroll_year
            payroll.creator = creator
            for field, value in data.items():
                setattr(payroll, field, value)
            payrolls_to_update.append(payroll)
        else:
            # Create new payroll
            payroll = Payroll(
                creator=creator,
                employee=emp,
                payroll_month=payroll_month_name,
                payroll_year=payroll_year,
                **data,
            )
            payrolls_to_create.append(payroll)

    # 3. Bulk database operations -------------------------------------------
    update_fields = [
        "creator",
        "payroll_month",
        "payroll_year",
        "days_of_month",
        "working_days",
        "present_days",
        "late_days",
        "absent_days",
        "weekend_days",
        "holidays",
        "leave_breakdown",
        "basic",
        "house_rent",
        "conveyance",
        "medical",
        "gross_salary",
        "festival_bonus",
        "performance_bonus",
        "absence_deduction",
        "late_deduction",
        "holiday_compensation",
        "weekday_compensation",
        "net_salary",
        "tax_deduction",
        "total_transfer_amount",
    ]

    created = []
    if payrolls_to_create:
        created = Payroll.objects.bulk_create(payrolls_to_create)

    if payrolls_to_update:
        Payroll.objects.bulk_update(payrolls_to_update, update_fields)

    return created + payrolls_to_update


# ---------------------------------------------------------------------------
# Async (threaded) generation
# ---------------------------------------------------------------------------


def generate_payroll_async(
    *,
    month=None,
    year=None,
    start_date=None,
    end_date=None,
    creator_id,
    include_festival_bonus=False,
    include_performance_bonus=False,
    employee_ids=None,
):
    """
    Spawn a background thread to generate payroll.

    Accepts the same date arguments as `generate_payroll` (either month/year or
    start_date/end_date).  Uses *creator_id* (int) so the thread re-fetches the
    User inside the worker (avoids stale ORM state).

    Returns the ``threading.Thread`` object (already started).
    """

    def _worker():
        from authentication.models import User  # avoid circular import at module level
        from notification.models import Notification

        try:
            close_old_connections()

            creator = User.objects.get(pk=creator_id)
            payrolls = generate_payroll(
                month=month,
                year=year,
                start_date=start_date,
                end_date=end_date,
                creator=creator,
                include_festival_bonus=include_festival_bonus,
                include_performance_bonus=include_performance_bonus,
                employee_ids=employee_ids,
            )

            # Build a human-friendly period label for the notification
            if end_date:
                month_label = MONTH_NAMES[end_date.month]
                year_label = end_date.year
            elif month:
                month_label = MONTH_NAMES[month]
                year_label = year
            else:
                month_label = "Period"
                year_label = ""

            Notification.objects.create(
                title=f"Payroll Generated — {month_label} {year_label}",
                type="payroll",
                receiver=creator,
                employee=creator,
                remarks=(
                    f"Payroll for {month_label} {year_label} has been generated "
                    f"successfully for {len(payrolls)} employee(s)."
                ),
            )
            logger.info(
                "Async payroll generation completed: %s %s — %d employee(s)",
                month_label,
                year_label,
                len(payrolls),
            )
        except Exception:
            logger.exception(
                "Async payroll generation failed for %s/%s",
                month or start_date,
                year or end_date,
            )
            try:
                label = (
                    MONTH_NAMES.get(month, str(month))
                    if month
                    else (str(end_date) if end_date else "period")
                )
                Notification.objects.create(
                    title=f"Payroll Failed — {label}",
                    type="payroll",
                    receiver_id=creator_id,
                    employee_id=creator_id,
                    remarks=(
                        f"Payroll generation for {label} failed. "
                        "Please try again or contact support."
                    ),
                )
            except Exception:
                logger.exception("Failed to create error notification")
        finally:
            close_old_connections()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread
