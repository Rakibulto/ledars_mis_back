from django.test import TestCase
from datetime import date
from attendance.models import AttendanceHistory
from employee.models import Employee
from employee.utils import HRDashboardAnalytics
from leave.models import LeaveRequest
from holiday.models import Holiday
from django.contrib.auth import get_user_model


User = get_user_model()


class AttendanceDashboardTests(TestCase):
    def setUp(self):
        # ensure default employee role exists for user creation
        from authentication.models import Role

        Role.objects.get_or_create(name="Employee")
        # create a minimal user; employee record will be auto-created by signal
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="pass"
        )
        # retrieve and update the generated employee
        self.employee = Employee.objects.get(user=user)
        self.employee.employee_id = "TEST001"
        self.employee.employee_name = "Test User"
        self.employee.status = "active"
        # make sure no special office_days so weekends are sat/sun
        self.employee.office_days = None
        self.employee.save()

        # Add a holiday within our range
        Holiday.objects.create(
            name="Test Holiday",
            from_date=date(2026, 2, 11),
            to_date=date(2026, 2, 11),
            is_global=True,
        )

        # Create attendance history entries similar to bug scenario
        # Jan 26 - present late
        AttendanceHistory.objects.create(
            employee=self.employee,
            date=date(2026, 1, 26),
            check_in_time="2026-01-26T09:16:00Z",
            is_late=True,
            status="Present",
        )
        # Jan 27 - present
        AttendanceHistory.objects.create(
            employee=self.employee,
            date=date(2026, 1, 27),
            check_in_time="2026-01-27T08:42:00Z",
            status="Present",
        )
        # Jan 30 weekend with check_in
        AttendanceHistory.objects.create(
            employee=self.employee,
            date=date(2026, 1, 30),
            check_in_time="2026-01-30T09:14:00Z",
            status="Weekend",
            is_weekend=True,
        )
        # Feb 1 absent record (should not count as present)
        AttendanceHistory.objects.create(
            employee=self.employee,
            date=date(2026, 2, 1),
            status="Absent",
        )

    def test_individual_attendance_counts(self):
        # use only the dates for which we seeded attendance records above
        stats = HRDashboardAnalytics._get_employee_attendance_data(
            self.employee, date(2026, 1, 26), date(2026, 1, 30)
        )
        summary = stats["summary"]

        # total days should equal range length (26-30 inclusive = 5)
        self.assertEqual(summary.get("total_days"), 5)
        # present records created for 26, 27 and 30 Jan
        self.assertEqual(summary["present_count"], 3)
        # absent days are 28 and 29 Jan
        self.assertEqual(summary["absent_count"], 2)
        # late count should include only Jan 26
        self.assertEqual(summary["late_count"], 1)
        # no weekend dates within 26‑30 Jan 2026 (Friday‑Thursday)
        self.assertEqual(summary["weekend_count"], 0)
        # no holidays in the shortened range
        self.assertEqual(summary["holiday_count"], 0)