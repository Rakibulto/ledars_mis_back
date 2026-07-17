from django.test import TestCase
from django.utils import timezone
from django.utils import timezone
from unittest.mock import patch
from datetime import datetime, date
from rest_framework.test import APIClient
from django.urls import reverse

from .models import CutOff


class CutOffModelTest(TestCase):
    def test_default_cutoff_creation_and_update(self):
        # no record exists initially
        self.assertFalse(CutOff.objects.exists())
        with patch(
            "django.utils.timezone.now",
            return_value=timezone.make_aware(datetime(2026, 1, 10)),
        ):
            co = CutOff.update_cutoff()
        print("default creation ->", co.date, co.cut_off)
        self.assertEqual(co.date, 25)
        self.assertEqual(co.cut_off, date(2026, 1, 25))
        # default cutoff_start should be previous month 26 (because date=25)
        self.assertEqual(co.cut_off_start, date(2025, 12, 26))


class AttendanceReportResignationTest(TestCase):
    """Ensure resigned/terminated employees are included only when the
    requested date range intersects their active period.

    The bug was that get_queryset used `today` when filtering employees
    which meant a user asking for a report over earlier dates would not see
    anyone who had already resigned, even though their attendance should
    still appear.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from employee.models import Employee
        from attendance.models import AttendanceHistory

        User = get_user_model()
        # create roles that the custom user save method expects
        from authentication.models import Role

        Role.objects.create(name="Employee")
        Role.objects.create(name="Admin")

        # superuser to simplify permission requirements (CustomUserManager requires username)
        self.admin = User.objects.create_superuser(
            username="adminuser",
            email="admin@test.com",
            password="pass1234",
        )
        # make sure the account is active as create_superuser doesn't set is_active
        self.admin.is_active = True
        # set explicit Admin role so permission branches treat user correctly
        admin_role = Role.objects.get(name="Admin")
        self.admin.role = admin_role
        self.admin.save()

        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        # create a normal employee user; an Employee instance is auto-created by signal
        self.user = User.objects.create_user(
            username="empuser",
            email="emp@test.com",
            password="pass1234",
        )
        self.employee = Employee.objects.get(user=self.user)
        self.employee.employee_name = "Test Employee"
        self.employee.save()

        # attendance on 15 Feb 2026
        AttendanceHistory.objects.create(
            employee=self.employee,
            date=date(2026, 2, 15),
            check_in_time=timezone.make_aware(datetime(2026, 2, 15, 9, 0)),
            check_out_time=timezone.make_aware(datetime(2026, 2, 15, 17, 0)),
            status="Present",
        )

        # resign/terminate on 16 Feb 2026
        self.employee.status = "resigned"
        self.employee.resign_terminated_date = date(2026, 2, 16)
        self.employee.save()

    def test_report_includes_days_before_resignation(self):
        url = reverse("attendance-report")
        response = self.client.get(
            url, {"start_date": "2026-02-01", "end_date": "2026-02-28"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # ensure our employee is present in the results
        self.assertTrue(any(e["employee_info"]["id"] == self.employee.pk for e in data))
        emp_entry = [e for e in data if e["employee_info"]["id"] == self.employee.pk][0]
        attendance = emp_entry["attendance"]
        self.assertTrue(any(a["date"] == "15-02-2026" for a in attendance))

    def test_report_excludes_when_query_after_resignation(self):
        url = reverse("attendance-report")
        response = self.client.get(
            url, {"start_date": "2026-02-17", "end_date": "2026-02-28"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # employee should not appear at all
        self.assertFalse(
            any(e["employee_info"]["id"] == self.employee.pk for e in data)
        )

    def test_cutoff_day_31_february(self):
        # February with 28 days; date field 31 should clamp to 28
        CutOff.objects.create(date=31)
        with patch(
            "django.utils.timezone.now",
            return_value=timezone.make_aware(datetime(2026, 2, 1)),
        ):
            co = CutOff.update_cutoff()
        print("feb non-leap ->", co.cut_off)
        self.assertEqual(co.cut_off, date(2026, 2, 28))
        # when cutoff_day=31 we expect start = first of same month
        self.assertEqual(co.cut_off_start, date(2026, 2, 1))

    def test_cutoff_day_31_march(self):
        CutOff.objects.all().delete()
        CutOff.objects.create(date=31)
        with patch(
            "django.utils.timezone.now",
            return_value=timezone.make_aware(datetime(2026, 3, 1)),
        ):
            co = CutOff.update_cutoff()
        print("march ->", co.cut_off)
        self.assertEqual(co.cut_off, date(2026, 3, 31))
        self.assertEqual(co.cut_off_start, date(2026, 3, 1))

    def test_cutoff_day_31_april(self):
        CutOff.objects.all().delete()
        CutOff.objects.create(date=31)
        with patch(
            "django.utils.timezone.now",
            return_value=timezone.make_aware(datetime(2026, 4, 1)),
        ):
            co = CutOff.update_cutoff()
        print("april ->", co.cut_off)
        self.assertEqual(co.cut_off, date(2026, 4, 30))
        self.assertEqual(co.cut_off_start, date(2026, 4, 1))

    def test_cutoff_day_31_february_leap(self):
        # Feb 2024 is leap year; 31 should resolve to 29
        CutOff.objects.all().delete()
        CutOff.objects.create(date=31)
        with patch(
            "django.utils.timezone.now",
            return_value=timezone.make_aware(datetime(2024, 2, 1)),
        ):
            co = CutOff.update_cutoff()
        print("feb leap ->", co.cut_off)
        self.assertEqual(co.cut_off, date(2024, 2, 29))
        self.assertEqual(co.cut_off_start, date(2024, 2, 1))
        self.assertEqual(co.cut_off_start, date(2024, 2, 1))

    def test_normal_cutoff_behavior(self):
        # date other than 31 should still work as before
        CutOff.objects.all().delete()
        CutOff.objects.create(date=15)
        with patch(
            "django.utils.timezone.now",
            return_value=timezone.make_aware(datetime(2026, 5, 10)),
        ):
            co = CutOff.update_cutoff()
        print("normal ->", co.cut_off)
        self.assertEqual(co.cut_off, date(2026, 5, 15))
        # start should be previous month 16th
        self.assertEqual(co.cut_off_start, date(2026, 4, 16))


class AttendanceAdjustmentApprovalTest(TestCase):
    """Ensure check-out approvals validate presence of check-in history."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from employee.models import Employee
        from authentication.models import Role

        User = get_user_model()
        Role.objects.create(name="Employee")
        Role.objects.create(name="Admin")

        self.admin = User.objects.create_superuser(
            username="adminuser",
            email="admin@test.com",
            password="pass1234",
        )
        self.admin.is_active = True
        admin_role = Role.objects.get(name="Admin")
        self.admin.role = admin_role
        self.admin.save()

        self.user = User.objects.create_user(
            username="empuser",
            email="emp@test.com",
            password="pass1234",
        )
        self.employee = Employee.objects.get(user=self.user)
        self.employee.employee_name = "Test Employee"
        self.employee.save()

        # ensure signal-logic for adjustment approval can find a supervisor
        from leave.models import SupervisorLevel

        SupervisorLevel.objects.create(
            employee=self.employee,
            supervisor=self.admin,
            level=1,
        )

    def test_cannot_approve_checkout_without_checkin(self):
        from .models import (
            AttendanceAdjustmentRequest,
            AttendanceAdjustmentApproval,
        )
        from rest_framework.exceptions import ValidationError

        req = AttendanceAdjustmentRequest.objects.create(
            employee=self.employee,
            date=date(2026, 3, 1),
            check_type="check_out",
            actual_duty_start_time=timezone.make_aware(datetime(2026, 3, 1, 9, 0)),
            actual_arival_time=timezone.make_aware(datetime(2026, 3, 1, 17, 0)),
        )
        approval = AttendanceAdjustmentApproval.objects.create(
            adjustment_request=req,
            approver=self.admin,
            status="pending",
        )

        approval.status = "approved"
        with self.assertRaises(ValidationError) as cm:
            approval.save()
        self.assertIn(
            "check-in", str(cm.exception).lower()
        )  # message mentions check-in requirement

    def test_can_approve_checkout_with_checkin_history(self):
        from .models import (
            AttendanceAdjustmentRequest,
            AttendanceAdjustmentApproval,
            AttendanceHistory,
        )

        # create a check-in record for that date
        AttendanceHistory.objects.create(
            employee=self.employee,
            date=date(2026, 3, 1),
            check_in_time=timezone.make_aware(datetime(2026, 3, 1, 9, 0)),
        )

        req = AttendanceAdjustmentRequest.objects.create(
            employee=self.employee,
            date=date(2026, 3, 1),
            check_type="check_out",
            actual_duty_start_time=timezone.make_aware(datetime(2026, 3, 1, 9, 0)),
            actual_arival_time=timezone.make_aware(datetime(2026, 3, 1, 17, 0)),
        )
        approval = AttendanceAdjustmentApproval.objects.create(
            adjustment_request=req,
            approver=self.admin,
            status="pending",
        )

        approval.status = "approved"
        # should not raise
        approval.save()
        self.assertEqual(approval.status, "approved")


class SingleDayAttendanceAPITest(TestCase):
    """Tests for the /attendance-for-adjustment/ endpoint."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from employee.models import Employee, Shift
        from authentication.models import Role

        User = get_user_model()
        Role.objects.create(name="Employee")
        Role.objects.create(name="Admin")

        self.admin = User.objects.create_superuser(
            username="adminuser",
            email="admin@test.com",
            password="pass1234",
        )
        self.admin.is_active = True
        admin_role = Role.objects.get(name="Admin")
        self.admin.role = admin_role
        self.admin.save()

        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.user = User.objects.create_user(
            username="empuser",
            email="emp@test.com",
            password="pass1234",
        )
        self.employee = Employee.objects.get(user=self.user)
        self.employee.employee_name = "Test Employee"
        # create and assign a simple shift 09:00-18:00
        shift = Shift.objects.create(
            name="day",
            office_start_time="09:00:00",
            office_end_time="18:00:00",
            check_in_start_time="08:30:00",
            check_in_end_time="09:30:00",
            check_out_start_time="17:30:00",
            check_out_end_time="18:30:00",
        )
        self.employee.office_time = shift
        self.employee.save()

        # ensure there is at least one leave policy so LeaveRequest.save() works
        from leave.models import LeavePolicy

        self.leave_policy = LeavePolicy.objects.create(
            leave_type_name="Test Leave",
            total_leave_days=10,
        )

        # leave base date for tests
        self.target_date = date(2025, 3, 10)

    def _call(self, params):
        return self.client.get(reverse("attendance-for-adjustment"), params)

    def test_regular_shift_without_leave(self):
        resp = self._call({"employee": self.user.id, "date": self.target_date})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], self.employee.pk)
        self.assertEqual(data["employee_name"], "Test Employee")
        self.assertEqual(data["check_in"], "09:00 am")
        self.assertEqual(data["check_out"], "06:00 pm")

    def test_first_half_half_day_adjustment(self):
        from leave.models import LeaveRequest

        # create approved first-half leave covering target_date
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_policy=self.leave_policy,
            start_date=self.target_date,
            end_date=self.target_date,
            is_half_day=True,
            half_day_period="first half",
            status="approved",
        )
        resp = self._call({"employee": self.user.id, "date": self.target_date})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # midpoint of 9-18 is 13:30 -> 01:30 pm
        self.assertEqual(data["check_in"], "01:30 pm")
        self.assertEqual(data["check_out"], "06:00 pm")

    def test_second_half_half_day_adjustment(self):
        from leave.models import LeaveRequest

        # create approved second-half leave covering target_date
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_policy=self.leave_policy,
            start_date=self.target_date,
            end_date=self.target_date,
            is_half_day=True,
            half_day_period="second half",
            status="approved",
        )
        resp = self._call({"employee": self.user.id, "date": self.target_date})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["check_in"], "09:00 am")
        self.assertEqual(data["check_out"], "01:30 pm")

    def test_half_day_with_capitalized_status(self):
        # verify that status case doesn't matter
        from leave.models import LeaveRequest

        LeaveRequest.objects.create(
            employee=self.employee,
            leave_policy=self.leave_policy,
            start_date=self.target_date,
            end_date=self.target_date,
            is_half_day=True,
            half_day_period="first half",
            status="Approved",  # capitalized
        )
        resp = self._call({"employee": self.user.id, "date": self.target_date})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # midpoint of 9-18 is 13:30
        self.assertEqual(data["check_in"], "01:30 pm")
