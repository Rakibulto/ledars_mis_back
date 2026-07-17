from datetime import date, timedelta
from django.db.models import Q
from holiday.models import Holiday
from .models import LeaveReset


class LeaveBalanceCalculator:
    """Core leave balance calculation logic"""

    DAY_MAP = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    @classmethod
    def get_weekend_days(cls, employee):
        """Determine weekend days based on office_days"""
        if not employee.office_days:
            return [5, 6]  # Default to Saturday, Sunday

        try:
            if "-" in employee.office_days:  # Range format
                start, end = employee.office_days.lower().split("-")
                start_day = cls.DAY_MAP[start.strip()]
                end_day = cls.DAY_MAP[end.strip()]

                working_days = []
                current = start_day

                # Handle both forward and backward ranges
                if start_day <= end_day:
                    # Normal forward range (e.g., Monday-Friday)
                    working_days = list(range(start_day, end_day + 1))
                else:
                    # Wrapped range (e.g., Saturday-Thursday)
                    working_days = list(range(start_day, 7)) + list(
                        range(0, end_day + 1)
                    )

                return sorted(set(range(7)) - set(working_days))

        except (ValueError, KeyError):
            return [5, 6]  # Fallback to Sat/Sun

        return [5, 6]

    @classmethod
    def is_holiday(cls, date, employee):
        """Check if date is a holiday for this employee"""
        return (
            Holiday.objects.filter(
                Q(from_date__lte=date, to_date__gte=date),
                Q(is_global=True)
                | Q(branches=employee.location)
                | Q(departments=employee.department)
                | Q(designations=employee.designation)
                | Q(assigned_employees=employee),
            )
            .exclude(excluded_employees=employee)
            .exists()
        )

    @classmethod
    def calculate_leave_days(
        cls, start_date, end_date, employee, policy, is_half_day=False
    ):
        """Calculate effective leave days considering all rules"""
        delta = end_date - start_date
        weekend_days = cls.get_weekend_days(employee)
        days = 0

        # Single day leave
        if delta.days == 0:
            date = start_date
            # Check if it's a weekend or holiday (only if they shouldn't be counted)
            is_weekend = date.weekday() in weekend_days
            is_holiday = cls.is_holiday(date, employee)

            # Only count if:
            # - It's a weekday or weekends are counted
            # AND
            # - It's not a holiday or holidays are counted
            if (policy.count_weekends or not is_weekend) and (
                policy.count_holidays or not is_holiday
            ):
                if policy.allow_half_day and is_half_day:
                    return 0.5
                return 1
            return 0

        # Multi-day leave
        for i in range(delta.days + 1):
            date = start_date + timedelta(days=i)

            # Skip weekends if not counted
            if not policy.count_weekends and date.weekday() in weekend_days:
                continue

            # Skip holidays if not counted
            if not policy.count_holidays and cls.is_holiday(date, employee):
                continue

            days += 1

        return days

    @classmethod
    def get_leave_period_for_date(cls, target_date=None):
        """Get the leave period for a given date, defaults to today"""
        if target_date is None:
            target_date = date.today()

        return LeaveReset.get_current_period(target_date)

    @classmethod
    def get_leave_period_for_year(cls, year):
        """get the leave period for a specific year"""
        # Use January 1st of the year as a reference point
        reference_date = date(year, 1, 1)
        return cls.get_leave_period_for_date(reference_date)
