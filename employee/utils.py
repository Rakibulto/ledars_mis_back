from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.db.models import Count, Q
from datetime import date, timedelta
from django.utils import timezone
from leave.models import LeaveRequest
from leave.utils import LeaveBalanceCalculator
from .models import Employee, ProbationCheckLog
from notification.models import Notification
from attendance.models import AttendanceHistory, AttendanceAdjustmentRequest
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


def check_probation_periods():
    """
    Checks probation periods for all active employees and sends notifications.
    """
    today = timezone.now().date()

    # Check if probation check has already run today
    if ProbationCheckLog.objects.filter(date=today).exists():
        return

    # Mark today as checked
    ProbationCheckLog.objects.create(date=today)

    # Get all active employees who haven't completed probation
    employees = Employee.objects.filter(status="active", probation_period=True)
    # print(f"Checking probation periods for {employees.count()} active employees.")
    for employee in employees:
        if not employee.joining_date or not employee.probation_period_time:
            continue

        # Calculate probation end date
        probation_end_date = employee.joining_date + relativedelta(
            months=employee.probation_period_time
        )

        # Send notifications from  10 days before probation end
        notification_date = probation_end_date - timedelta(days=10)
        if today >= notification_date:
            print(f"Today will be notified")
            for supervisor in employee.supervisor.all():
                if today > probation_end_date:
                    title = f"Probation Completed — {employee.employee_name or employee.user} on {probation_end_date}"
                    remarks = f"Probation period for {employee.employee_name} has ended. Please review."
                elif today >= notification_date:
                    title = f"Probation Ends Soon — {employee.employee_name or employee.user} on {probation_end_date}"
                    remarks = f"Probation period for {employee.employee_name} ends on {probation_end_date}. Please review."
                else:
                    continue
                Notification.objects.create(
                    title=title,
                    type="probation_period",
                    notification_id=employee.user.id,
                    employee=employee.user,
                    receiver=supervisor,
                    remarks=remarks,
                )


# Dashboard count utility functions


class HRDashboardAnalytics:
    """Class to generate all HR analytics with date range filtering"""

    @staticmethod
    def get_employee_counts(start_date=None, end_date=None):
        """
        Get total employee counts by status with date range filtering for new employees
        Returns: {
            'total_employees': int,
            'active_employees': int,
            'resigned_employees': int,
            'terminated_employees': int,
            'incomplete_employees': int,
            'new_joined': int,
            'new_resigned': int,
            'new_terminated': int
        }
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()

        # Base queryset - all employees (no date filtering)
        employees = Employee.objects.all()

        # Get all employee counts without date filtering
        counts = employees.aggregate(
            total_employees=Count("pk"),
            active_employees=Count("pk", filter=Q(status="active")),
            resigned_employees=Count("pk", filter=Q(status="resigned")),
            terminated_employees=Count("pk", filter=Q(status="terminated")),
            incomplete_employees=Count("pk", filter=Q(status="incomplete")),
        )

        # Get new employees based on date range
        new_counts = employees.aggregate(
            new_joined=Count(
                "pk", filter=Q(joining_date__range=[start_date, end_date])
            ),
            new_resigned=Count(
                "pk",
                filter=Q(
                    resign_terminated_date__range=[start_date, end_date],
                    status="resigned",
                ),
            ),
            new_terminated=Count(
                "pk",
                filter=Q(
                    resign_terminated_date__range=[start_date, end_date],
                    status="terminated",
                ),
            ),
        )

        # Combine both counts
        counts.update(new_counts)

        return counts

    @staticmethod
    def get_attendance_counts(start_date=None, end_date=None):
        """
        Get attendance-related counts for the date range
        Returns: {
            'present_count': int,
            'absent_count': int,
            'late_count': int,
            'on_leave_count': int,
            'holiday_count': int,
            'weekend_count': int
        }
        """
        # Only get attendance counts for today even though range is provided; this method is meant
        # for live dashboard numbers where past ranges are not needed.  (Date range is ignored.)
        start_date = date.today()
        end_date = date.today()

        # Get all active employees with related data in one query
        total_employee = (
            Employee.objects.filter(status__in=["active", "incomplete"])
            .select_related("employment_type", "department", "designation", "location")
            .prefetch_related("supervisor")
        )

        # Generate all date-employee combinations we need to check
        date_employee_combinations = []
        current_date = start_date
        delta = timedelta(days=1)

        while current_date <= end_date:
            for employee in total_employee:
                date_employee_combinations.append((current_date, employee))
            current_date += delta

        # Bulk fetch all attendance records for the date range
        attendance_records = AttendanceHistory.objects.filter(
            employee__in=total_employee, date__range=[start_date, end_date]
        ).select_related("employee")

        # Create a lookup dictionary for fast attendance checking
        attendance_lookup = {}
        for attendance in attendance_records:
            key = (attendance.date, attendance.employee.id)
            attendance_lookup[key] = attendance

        # Bulk fetch all approved leave requests that overlap with our date range
        leave_requests = (
            LeaveRequest.objects.filter(employee__in=total_employee, status="approved")
            .filter(Q(start_date__lte=end_date) & Q(end_date__gte=start_date))
            .select_related("employee")
        )

        # Create a lookup for leave requests
        leave_lookup = {}
        for leave in leave_requests:
            employee_id = leave.employee.id
            if employee_id not in leave_lookup:
                leave_lookup[employee_id] = []
            # Add all dates this leave covers within our range
            leave_start = max(leave.start_date, start_date)
            leave_end = min(leave.end_date, end_date)
            current_leave_date = leave_start
            while current_leave_date <= leave_end:
                leave_lookup[employee_id].append(current_leave_date)
                current_leave_date += timedelta(days=1)

        # Initialize counters
        present_count = 0
        absent_count = 0
        late_count = 0
        early_leave = 0
        on_leave_count = 0
        holiday_count = 0
        weekend_count = 0

        # Process all date-employee combinations
        for check_date, employee in date_employee_combinations:
            # Get weekend days for this employee (cached per employee)
            weekend_days = LeaveBalanceCalculator.get_weekend_days(employee)
            is_weekend = check_date.weekday() in weekend_days

            # Check if it's a holiday for this employee
            is_holiday = LeaveBalanceCalculator.is_holiday(check_date, employee)

            # Check if employee is on approved leave this day
            employee_leaves = leave_lookup.get(employee.id, [])
            is_on_leave = check_date in employee_leaves

            # Check if employee has attendance record (present)
            attendance_key = (check_date, employee.id)
            attendance = attendance_lookup.get(attendance_key)

            # Count as present only if there is a real check-in (i.e. not a generated absent/holiday/weekend record).
            present_record = attendance and attendance.check_in_time is not None
            if present_record:
                present_count += 1
                if attendance.is_late:
                    late_count += 1
                if attendance.status == "Early Leave":
                    early_leave += 1

            # Regardless of presence we still categorize the day for reporting
            if is_weekend:
                weekend_count += 1
            elif is_holiday:
                holiday_count += 1
            elif is_on_leave:
                on_leave_count += 1
            else:
                if not present_record:
                    absent_count += 1

        total_days = (end_date - start_date).days + 1
        total_employees = total_employee.count()
        return {
            "total_days": total_days,
            "total_employees": total_employees,
            "present_count": present_count,
            "absent_count": absent_count,
            "late_count": late_count,
            "early_leave": early_leave,
            "on_leave_count": on_leave_count,
            "holiday_count": holiday_count,
            "weekend_count": weekend_count,
        }

    @staticmethod
    def get_leave_counts(start_date=None, end_date=None):
        """
        Get leave-related counts for the date range
        Returns: {
            'total_leaves': int,
            'pending_leaves': int,
            'approved_leaves': int,
            'rejected_leaves': int,
            'cancelled_leaves': int
        }
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()

        # Filter leave requests that overlap with the date range
        leaves = LeaveRequest.objects.filter(
            Q(start_date__lte=end_date) & Q(end_date__gte=start_date)
        )

        counts = leaves.aggregate(
            total_leaves=Count("id"),
            pending_leaves=Count("id", filter=Q(status="pending")),
            approved_leaves=Count("id", filter=Q(status="approved")),
            rejected_leaves=Count("id", filter=Q(status="rejected")),
            cancelled_leaves=Count("id", filter=Q(status="cancelled")),
        )

        return counts

    @staticmethod
    def get_attendance_adjustment_counts(start_date=None, end_date=None):
        """
        Get attendance adjustment request counts for the date range
        Returns: {
            'total_adjustments': int,
            'pending_adjustments': int,
            'approved_adjustments': int,
            'rejected_adjustments': int
        }
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()

        # Filter adjustment requests by date range
        adjustments = AttendanceAdjustmentRequest.objects.filter(
            date__range=[start_date, end_date]
        )

        counts = adjustments.aggregate(
            total_adjustments=Count("id"),
            pending_adjustments=Count("id", filter=Q(status="pending")),
            approved_adjustments=Count("id", filter=Q(status="approved")),
            rejected_adjustments=Count("id", filter=Q(status="rejected")),
        )

        return counts

    @staticmethod
    def get_birthday_employees(start_date=None, end_date=None):
        """
        Get employees with birthdays in the date range
        Returns: List of employees with birthdays in range
        """
        if start_date is None:
            start_date = date.today()
        if end_date is None:
            end_date = start_date + timedelta(days=30)

        # Handle year wrapping (e.g., December to January)
        # Get all employees with birthdays in the month range
        month_day_pairs = []
        current_date = start_date
        delta = timedelta(days=1)

        while current_date <= end_date:
            month_day_pairs.append((current_date.month, current_date.day))
            current_date += delta

        # Create Q objects for each month/day pair
        birthday_filters = Q()
        for month, day in month_day_pairs:
            birthday_filters |= Q(date_of_birth__month=month, date_of_birth__day=day)

        return (
            Employee.objects.filter(birthday_filters, status="active")
            .select_related("department", "designation")
            .order_by("date_of_birth")
        )

    @staticmethod
    def get_all_counts(start_date=None, end_date=None):
        """
        Get all analytics counts in a single call
        Returns: {
            'employee_counts': {...},
            'attendance_counts': {...},
            'leave_counts': {...},
            'attendance_adjustment_counts': {...},
            'birthday_employees': [...]
        }
        """
        return {
            "employee_counts": HRDashboardAnalytics.get_employee_counts(
                start_date, end_date
            ),
            "attendance_counts": HRDashboardAnalytics.get_attendance_counts(
                start_date, end_date
            ),
            "leave_counts": HRDashboardAnalytics.get_leave_counts(start_date, end_date),
            "attendance_adjustment_counts": HRDashboardAnalytics.get_attendance_adjustment_counts(
                start_date, end_date
            ),
            "birthday_employees": list(
                HRDashboardAnalytics.get_birthday_employees(start_date, end_date)
                .select_related("department", "designation")
                .values(
                    "employee_id",
                    "employee_name",
                    "date_of_birth",
                    "department__name",
                    "designation__name",
                )
            ),
        }

    @staticmethod
    def get_individual_employee_data(employee_id, start_date=None, end_date=None):
        """
        Get comprehensive data for a specific employee
        Returns: {
            'employee_info': {...},
            'attendance_data': {...},
            'leave_data': {...}
        }
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()

        try:
            # Get the employee
            employee = Employee.objects.select_related(
                "department", "designation", "location", "office_time"
            ).get(employee_id=employee_id)
        except Employee.DoesNotExist:
            return {"error": "Employee not found"}

        # Employee basic info
        employee_info = {
            "employee_id": employee.employee_id,
            "employee_name": employee.employee_name,
            "department": employee.department.name if employee.department else None,
            "designation": employee.designation.name if employee.designation else None,
            "location": employee.location.name if employee.location else None,
            "joining_date": employee.joining_date,
            "status": employee.status,
            "email": employee.user.email if employee.user else None,
            "personal_mobile_number": employee.personal_mobile_number,
            "office_time": employee.office_time.name if employee.office_time else None,
            "probation_period": employee.probation_period,
            "date_of_birth": employee.date_of_birth,
        }

        # Get attendance data for this employee
        attendance_data = HRDashboardAnalytics._get_employee_attendance_data(
            employee, start_date, end_date
        )

        # Get leave data for this employee
        leave_data = HRDashboardAnalytics._get_employee_leave_data(
            employee, start_date, end_date
        )

        return {
            "employee_info": employee_info,
            "attendance_data": attendance_data,
            "leave_data": leave_data,
            "date_range": {"start_date": start_date, "end_date": end_date},
        }

    @staticmethod
    def _get_employee_attendance_data(employee, start_date, end_date):
        """Helper method to get attendance data for a specific employee"""
        # Get attendance records for this employee in one query
        attendance_records = AttendanceHistory.objects.filter(
            employee=employee, date__range=[start_date, end_date]
        ).order_by("-date")

        # Create lookup dictionary for fast access
        attendance_lookup = {att.date: att for att in attendance_records}

        # Get approved leave requests that overlap with the date range
        leave_requests = LeaveRequest.objects.filter(
            employee=employee, status="approved"
        ).filter(Q(start_date__lte=end_date) & Q(end_date__gte=start_date))

        # Create set of leave dates for fast lookup
        leave_dates = set()
        for leave in leave_requests:
            leave_start = max(leave.start_date, start_date)
            leave_end = min(leave.end_date, end_date)
            current_leave_date = leave_start
            while current_leave_date <= leave_end:
                leave_dates.add(current_leave_date)
                current_leave_date += timedelta(days=1)

        # Initialize counters
        present_count = 0
        absent_count = 0
        late_count = 0
        early_leave_count = 0
        on_leave_count = 0
        holiday_count = 0
        weekend_count = 0

        daily_records = []

        # Get weekend days for this employee (cached)
        weekend_days = LeaveBalanceCalculator.get_weekend_days(employee)

        # Iterate through date range
        current_date = start_date
        delta = timedelta(days=1)

        while current_date <= end_date:
            is_weekend = current_date.weekday() in weekend_days
            is_holiday = LeaveBalanceCalculator.is_holiday(current_date, employee)
            is_on_leave = current_date in leave_dates
            attendance = attendance_lookup.get(current_date)

            day_status = None
            present_record = attendance and attendance.check_in_time is not None
            if present_record:
                present_count += 1
                if attendance.is_late:
                    late_count += 1
                if (
                    attendance.status == "Early Leave"
                    or attendance.check_out_time is None
                ):
                    early_leave_count += 1

            # classify day
            if is_weekend:
                weekend_count += 1
                day_status = "Weekend"
            elif is_holiday:
                holiday_count += 1
                day_status = "Holiday"
            elif is_on_leave:
                on_leave_count += 1
                day_status = "On Leave"
            else:
                if present_record:
                    day_status = "Present"
                else:
                    absent_count += 1
                    day_status = "Absent"

            # Add to daily records (last 10 days only for performance)
            if len(daily_records) < 10:
                daily_records.append(
                    {
                        "date": current_date,
                        "status": day_status,
                        "is_late": attendance.is_late if attendance else False,
                        "check_in_time": (
                            attendance.check_in_time if attendance else None
                        ),
                        "check_out_time": (
                            attendance.check_out_time if attendance else None
                        ),
                    }
                )

            current_date += delta

        # Calculate working days and attendance percentage
        working_days = present_count + absent_count
        attendance_percentage = (
            (present_count / working_days * 100) if working_days > 0 else 0
        )
        total_days = (end_date - start_date).days + 1

        return {
            "summary": {
                "total_days": total_days,
                "present_count": present_count,
                "absent_count": absent_count,
                "late_count": late_count,
                "early_leave_count": early_leave_count,
                "on_leave_count": on_leave_count,
                "holiday_count": holiday_count,
                "weekend_count": weekend_count,
                "working_days": working_days,
                "attendance_percentage": round(attendance_percentage, 2),
            },
            "recent_records": daily_records,
        }

    @staticmethod
    def _get_employee_leave_data(employee, start_date, end_date):
        """Helper method to get leave data for a specific employee"""
        # Get leave requests for this employee
        leave_requests = (
            LeaveRequest.objects.filter(employee=employee)
            .filter(Q(start_date__lte=end_date) & Q(end_date__gte=start_date))
            .order_by("-start_date")
        )

        # Calculate summary
        total_leaves = leave_requests.count()
        approved_leaves = leave_requests.filter(status="approved").count()
        pending_leaves = leave_requests.filter(status="pending").count()
        rejected_leaves = leave_requests.filter(status="rejected").count()
        cancelled_leaves = leave_requests.filter(status="cancelled").count()

        # Get recent requests (last 5)
        recent_requests = []
        for leave in leave_requests[:5]:
            recent_requests.append(
                {
                    "id": leave.id,
                    "start_date": leave.start_date,
                    "end_date": leave.end_date,
                    "status": leave.status,
                    "reason": leave.reason,
                    "is_half_day": leave.is_half_day,
                    "leave_type": (
                        leave.leave_policy.leave_type_name
                        if leave.leave_policy
                        else None
                    ),
                    "created_at": leave.created_at,
                }
            )

        return {
            "summary": {
                "total_leaves": total_leaves,
                "approved_leaves": approved_leaves,
                "pending_leaves": pending_leaves,
                "rejected_leaves": rejected_leaves,
                "cancelled_leaves": cancelled_leaves,
            },
            "recent_requests": recent_requests,
        }

    @staticmethod
    def get_supervisor_dashboard_data(
        supervisor_identifier, start_date=None, end_date=None
    ):
        """
        Get dashboard data for all employees under a specific supervisor
        supervisor_identifier can be either User ID (int) or Employee ID (string)
        Returns aggregated data for all subordinates similar to get_all_counts
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()

        try:
            from authentication.models import User

            # Try to determine if it's a User ID (integer) or Employee ID (string)
            if str(supervisor_identifier).isdigit():
                # It's a User ID
                supervisor = User.objects.get(id=int(supervisor_identifier))
            else:
                # It's an Employee ID, get the user from employee
                supervisor_employee = Employee.objects.get(
                    employee_id=supervisor_identifier
                )
                supervisor = supervisor_employee.user

        except (User.DoesNotExist, Employee.DoesNotExist):
            return {"error": "Supervisor not found"}

        # Get all employees under this supervisor
        subordinates = Employee.objects.filter(supervisor=supervisor)

        if not subordinates.exists():
            return {"error": "No subordinates found for this supervisor"}

        # Get supervisor info
        supervisor_info = {
            "supervisor_id": supervisor.id,
            "supervisor_name": supervisor.email,
            "total_subordinates": subordinates.count(),
        }

        # Try to get supervisor employee info for better display
        try:
            supervisor_employee = Employee.objects.get(user=supervisor)
            supervisor_info.update(
                {
                    "supervisor_employee_id": supervisor_employee.employee_id,
                    "supervisor_employee_name": supervisor_employee.employee_name,
                    "supervisor_department": (
                        supervisor_employee.department.name
                        if supervisor_employee.department
                        else None
                    ),
                    "supervisor_designation": (
                        supervisor_employee.designation.name
                        if supervisor_employee.designation
                        else None
                    ),
                }
            )
        except Employee.DoesNotExist:
            pass

        # Add subordinate list with employee_id and employee_name
        subordinate_list = list(subordinates.values("employee_id", "employee_name"))
        supervisor_info["subordinate_list"] = subordinate_list

        # Get employee counts for subordinates only
        employee_counts = HRDashboardAnalytics._get_subordinate_employee_counts(
            subordinates, start_date, end_date
        )

        # Get attendance counts for subordinates only
        attendance_counts = HRDashboardAnalytics._get_subordinate_attendance_counts(
            subordinates, start_date, end_date
        )

        # Get leave counts for subordinates only
        leave_counts = HRDashboardAnalytics._get_subordinate_leave_counts(
            subordinates, start_date, end_date
        )

        # Get attendance adjustment counts for subordinates only
        adjustment_counts = HRDashboardAnalytics._get_subordinate_adjustment_counts(
            subordinates, start_date, end_date
        )

        # Get birthday employees from subordinates only
        birthday_employees = HRDashboardAnalytics._get_subordinate_birthday_employees(
            subordinates, start_date, end_date
        )

        return {
            "supervisor_info": supervisor_info,
            "employee_counts": employee_counts,
            "attendance_counts": attendance_counts,
            "leave_counts": leave_counts,
            "attendance_adjustment_counts": adjustment_counts,
            "birthday_employees": birthday_employees,
            "date_range": {"start_date": start_date, "end_date": end_date},
        }

    @staticmethod
    def _get_subordinate_employee_counts(subordinates, start_date, end_date):
        """Get employee counts for specific subordinates"""
        counts = subordinates.aggregate(
            total_employees=Count("employee_id"),
            active_employees=Count("employee_id", filter=Q(status="active")),
            resigned_employees=Count("employee_id", filter=Q(status="resigned")),
            terminated_employees=Count("employee_id", filter=Q(status="terminated")),
            incomplete_employees=Count("employee_id", filter=Q(status="incomplete")),
        )

        # Get new employees based on date range
        new_counts = subordinates.aggregate(
            new_joined=Count(
                "employee_id", filter=Q(joining_date__range=[start_date, end_date])
            ),
            new_resigned=Count(
                "employee_id",
                filter=Q(
                    resign_terminated_date__range=[start_date, end_date],
                    status="resigned",
                ),
            ),
            new_terminated=Count(
                "employee_id",
                filter=Q(
                    resign_terminated_date__range=[start_date, end_date],
                    status="terminated",
                ),
            ),
        )

        counts.update(new_counts)
        return counts

    @staticmethod
    def _get_subordinate_attendance_counts(subordinates, start_date, end_date):
        """Get attendance counts for specific subordinates"""
        # Get only active subordinates with related data
        active_subordinates = (
            subordinates.filter(status="active")
            .select_related("employment_type", "department", "designation", "location")
            .prefetch_related("supervisor")
        )

        # Bulk fetch all attendance records for subordinates in the date range
        attendance_records = AttendanceHistory.objects.filter(
            employee__in=active_subordinates, date__range=[start_date, end_date]
        ).select_related("employee")

        # Create lookup dictionary for attendance
        attendance_lookup = {}
        for attendance in attendance_records:
            key = (attendance.date, attendance.employee.id)
            attendance_lookup[key] = attendance

        # Bulk fetch all approved leave requests for subordinates
        leave_requests = (
            LeaveRequest.objects.filter(
                employee__in=active_subordinates, status="approved"
            )
            .filter(Q(start_date__lte=end_date) & Q(end_date__gte=start_date))
            .select_related("employee")
        )

        # Create lookup for leave dates
        leave_lookup = {}
        for leave in leave_requests:
            employee_id = leave.employee.id
            if employee_id not in leave_lookup:
                leave_lookup[employee_id] = set()
            # Add all dates this leave covers within our range
            leave_start = max(leave.start_date, start_date)
            leave_end = min(leave.end_date, end_date)
            current_leave_date = leave_start
            while current_leave_date <= leave_end:
                leave_lookup[employee_id].add(current_leave_date)
                current_leave_date += timedelta(days=1)

        # Initialize counters
        present_count = 0
        absent_count = 0
        late_count = 0
        early_leave = 0
        on_leave_count = 0
        holiday_count = 0
        weekend_count = 0

        # Generate all date-employee combinations
        date_employee_combinations = []
        current_date = start_date
        delta = timedelta(days=1)

        while current_date <= end_date:
            for employee in active_subordinates:
                date_employee_combinations.append((current_date, employee))
            current_date += delta

        # Process all combinations
        for check_date, employee in date_employee_combinations:
            # Get weekend days for this employee
            weekend_days = LeaveBalanceCalculator.get_weekend_days(employee)
            is_weekend = check_date.weekday() in weekend_days

            # Check if it's a holiday for this employee
            is_holiday = LeaveBalanceCalculator.is_holiday(check_date, employee)

            # Check if employee is on approved leave this day
            employee_leaves = leave_lookup.get(employee.id, set())
            is_on_leave = check_date in employee_leaves

            # Check if employee has attendance record
            attendance_key = (check_date, employee.id)
            attendance = attendance_lookup.get(attendance_key)

            present_record = attendance and attendance.check_in_time is not None
            if present_record:
                present_count += 1
                if attendance.is_late:
                    late_count += 1
                if attendance.status == "Early Leave":
                    early_leave += 1

            if is_weekend:
                weekend_count += 1
            elif is_holiday:
                holiday_count += 1
            elif is_on_leave:
                on_leave_count += 1
            else:
                if not present_record:
                    absent_count += 1

        total_days = (end_date - start_date).days + 1
        return {
            "total_days": total_days,
            "present_count": present_count,
            "absent_count": absent_count,
            "late_count": late_count,
            "early_leave": early_leave,
            "on_leave_count": on_leave_count,
            "holiday_count": holiday_count,
            "weekend_count": weekend_count,
        }

    @staticmethod
    def _get_subordinate_leave_counts(subordinates, start_date, end_date):
        """Get leave counts for specific subordinates"""
        # Filter leave requests for subordinates that overlap with the date range
        leaves = LeaveRequest.objects.filter(employee__in=subordinates).filter(
            Q(start_date__lte=end_date) & Q(end_date__gte=start_date)
        )

        counts = leaves.aggregate(
            total_leaves=Count("id"),
            pending_leaves=Count("id", filter=Q(status="pending")),
            approved_leaves=Count("id", filter=Q(status="approved")),
            rejected_leaves=Count("id", filter=Q(status="rejected")),
            cancelled_leaves=Count("id", filter=Q(status="cancelled")),
        )

        return counts

    @staticmethod
    def _get_subordinate_adjustment_counts(subordinates, start_date, end_date):
        """Get attendance adjustment counts for specific subordinates"""
        # Filter adjustment requests for subordinates by date range
        adjustments = AttendanceAdjustmentRequest.objects.filter(
            employee__in=subordinates, date__range=[start_date, end_date]
        )

        counts = adjustments.aggregate(
            total_adjustments=Count("id"),
            pending_adjustments=Count("id", filter=Q(status="pending")),
            approved_adjustments=Count("id", filter=Q(status="approved")),
            rejected_adjustments=Count("id", filter=Q(status="rejected")),
        )

        return counts

    @staticmethod
    def _get_subordinate_birthday_employees(subordinates, start_date, end_date):
        """Get birthday employees from specific subordinates"""
        # Get all subordinates with birthdays in the month range
        month_day_pairs = []
        current_date = start_date
        delta = timedelta(days=1)

        while current_date <= end_date:
            month_day_pairs.append((current_date.month, current_date.day))
            current_date += delta

        # Create Q objects for each month/day pair
        birthday_filters = Q()
        for month, day in month_day_pairs:
            birthday_filters |= Q(date_of_birth__month=month, date_of_birth__day=day)

        birthday_employees = subordinates.filter(
            birthday_filters, status="active"
        ).order_by("date_of_birth")

        return list(
            birthday_employees.values(
                "employee_id",
                "employee_name",
                "date_of_birth",
                "department__name",
                "designation__name",
            )
        )
