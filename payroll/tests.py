"""
Comprehensive tests for the payroll-generation endpoint and utility functions.

Covers:
  1. Payload validation (missing/invalid fields)
  2. Permission checks (no perm → 403, with add_payroll perm → 200)
  3. Basic payroll generation for a single active employee
  4. Correct present / absent / late / weekend / holiday counting
  5. Leave integration (approved leaves reduce absent days)
  6. Deduction calculations (late_deduction × late_days, absence_deduction × absent_days)
      including late-count threshold and holiday/weekend-late policy
  7. Compensation calculations (holiday_compensation, weekday_compensation)
  8. Festival bonus & performance bonus toggling
  9. Re-generation (same month/year updates existing payrolls instead of duplicating)
  10. Leap-year handling (Feb 2024 → 29 days)
  11. No active employees → empty result
  12. Employee with no salary record → zero salary fields
  13. Multiple employees in one batch
  14. Half-day leave handling
  15. Edge: employee works on both holiday AND weekend
  16. Net salary clamping (never negative)
  17. API response structure
  18. Per-employee generation via employee_ids
  19. Salary effective date selection
  20. Async (threaded) generation
"""

import json
import time as _time
import math
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status as http_status

from attendance.models import AttendanceHistory
from employee.models import Branch, Department, Designation, Employee, Salary
from authentication.models import Role
from holiday.models import Holiday
from leave.models import LeaveGroup, LeavePolicy, LeaveRequest
from notification.models import Notification
from payroll.models import Payroll
from payroll.utils import (
    generate_payroll,
    generate_payroll_async,
    get_month_date_range,
    get_holidays_for_employee,
    MONTH_NAMES,
)
from leave.utils import LeaveBalanceCalculator
from shift.models import Shift

User = get_user_model()

# ---------------------------------------------------------------------------
# Base test set-up
# ---------------------------------------------------------------------------


class PayrollTestBase(TestCase):
    """Shared fixtures used by every payroll test class."""

    @classmethod
    def setUpTestData(cls):
        # ---- Role ----------------------------------------------------------
        cls.admin_role, _ = Role.objects.get_or_create(name="Admin")
        cls.employee_role, _ = Role.objects.get_or_create(name="Employee")

        # ---- Shift ---------------------------------------------------------
        cls.shift = Shift.objects.create(
            name="General",
            office_start_time=time(9, 0),
            office_end_time=time(17, 0),
            office_start_time_consideration=10,
            office_end_time_consideration=10,
            check_in_start_time=time(8, 0),
            check_in_end_time=time(10, 0),
            check_out_start_time=time(16, 0),
            check_out_end_time=time(18, 0),
        )

        # ---- Admin user (with add_payroll permission) ----------------------
        cls.admin_user = User.objects.create_user(
            email="admin@test.com",
            username="admin@test.com",
            password="adminpass123",
        )
        cls.admin_user.role = cls.admin_role
        cls.admin_user.is_active = True
        cls.admin_user.is_staff = True
        cls.admin_user.save(update_fields=["role", "is_active", "is_staff"])

        ct = ContentType.objects.get_for_model(Payroll)
        perm_add = Permission.objects.get(content_type=ct, codename="add_payroll")
        perm_change = Permission.objects.get(content_type=ct, codename="change_payroll")
        perm_view = Permission.objects.get(content_type=ct, codename="view_payroll")
        cls.admin_user.user_permissions.add(perm_add, perm_change, perm_view)

        # ---- Regular user (no payroll perm) --------------------------------
        cls.regular_user = User.objects.create_user(
            email="regular@test.com",
            username="regular@test.com",
            password="regularpass123",
        )
        cls.regular_user.role = cls.employee_role
        cls.regular_user.is_active = True
        cls.regular_user.save(update_fields=["role", "is_active"])

        # ---- Department / Designation / Branch -----------------------------
        cls.dept = Department.objects.create(name="Engineering")
        cls.desig = Designation.objects.create(name="Developer", department=cls.dept)
        cls.branch = Branch.objects.create(name="HQ", address="123 Main St")

        # ---- Leave group ---------------------------------------------------
        cls.leave_group = LeaveGroup.objects.create(name="General")

    # Helpers ---------------------------------------------------------------

    def _create_employee(self, user, eid="EMP001", office_days="Sunday-Thursday"):
        """Create an active Employee linked to the given user."""
        emp = Employee(
            user=user,
            employee_id=eid,
            employee_name=user.username,
            department=self.dept,
            designation=self.desig,
            location=self.branch,
            joining_date=date(2024, 1, 1),
            office_days=office_days,
            office_time=self.shift,
            status="active",
            present_address="Test",
            permanent_address="Test",
            personal_mobile_number="0123456789",
            gender="male",
            leave_group=self.leave_group,
        )
        # Use super().save() to skip signals that may depend on other data
        Employee.save(emp)
        return emp

    def _create_salary(self, employee, **overrides):
        defaults = dict(
            basic=Decimal("30000"),
            house_rent=Decimal("10000"),
            conveyance=Decimal("5000"),
            medical=Decimal("5000"),
            festival_bonus=Decimal("5000"),
            performance_bonus=Decimal("3000"),
            absence_deduction=Decimal("500"),
            late_deduction=Decimal("200"),
            # new salary configuration fields
            is_late_during_holiday=False,
            late_count_threshold=1,
            holiday_compensation=Decimal("1000"),
            weekday_compensation=Decimal("1500"),
        )
        defaults.update(overrides)
        return Salary.objects.create(
            employee=employee, creator=self.admin_user, **defaults
        )

    def _create_attendance(
        self,
        employee,
        d,
        status_val="Present",
        is_late=False,
        is_holiday=False,
        is_weekend=False,
    ):
        return AttendanceHistory.objects.create(
            employee=employee,
            date=d,
            status=status_val,
            is_late=is_late,
            is_holiday=is_holiday,
            is_weekend=is_weekend,
        )

    def _get_client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client


# ---------------------------------------------------------------------------
# 1. Utility function tests
# ---------------------------------------------------------------------------


class TestGetMonthDateRange(TestCase):
    def test_february_non_leap(self):
        s, e = get_month_date_range(2, 2026)
        self.assertEqual(s, date(2026, 2, 1))
        self.assertEqual(e, date(2026, 2, 28))


# ---------------------------------------------------------------------------
# 2. API filter tests
# ---------------------------------------------------------------------------


class TestPayrollListFilters(PayrollTestBase):
    def setUp(self):
        super().setUp()
        # prepare two additional users/employees
        self.user2 = User.objects.create_user(
            email="emp2@test.com",
            username="emp2@test.com",
            password="pass2",
        )
        self.user2.role = self.employee_role
        self.user2.is_active = True
        self.user2.save(update_fields=["role", "is_active"])
        self.emp1 = self._create_employee(self.regular_user, eid="EMP001")
        self.emp2 = self._create_employee(self.user2, eid="EMP002")

        Payroll.objects.create(
            creator=self.admin_user,
            employee=self.emp1,
            payroll_month="January",
            payroll_year=2026,
        )
        Payroll.objects.create(
            creator=self.admin_user,
            employee=self.emp2,
            payroll_month="February",
            payroll_year=2027,
        )
        self.client = self._get_client(self.admin_user)

    def test_filter_by_employee_id(self):
        url = reverse("payroll-list")
        resp = self.client.get(url, {"employee": "EMP001"})
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data), 1)

    def test_filter_by_employee_name(self):
        url = reverse("payroll-list")
        resp = self.client.get(url, {"employee": self.emp2.employee_name})
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data), 1)

    def test_filter_by_month_and_year(self):
        url = reverse("payroll-list")
        resp = self.client.get(
            url, {"payroll_month": "February", "payroll_year": "2027"}
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["payroll_month"], "February")
        self.assertEqual(data[0]["payroll_year"], 2027)

    def test_combined_filters(self):
        url = reverse("payroll-list")
        resp = self.client.get(
            url,
            {"employee": "EMP002", "payroll_month": "February", "payroll_year": "2027"},
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data), 1)

    def test_february_leap(self):
        s, e = get_month_date_range(2, 2024)
        self.assertEqual(s, date(2024, 2, 1))
        self.assertEqual(e, date(2024, 2, 29))

    def test_january(self):
        s, e = get_month_date_range(1, 2026)
        self.assertEqual(s, date(2026, 1, 1))
        self.assertEqual(e, date(2026, 1, 31))

    def test_december(self):
        s, e = get_month_date_range(12, 2026)
        self.assertEqual(s, date(2026, 12, 1))
        self.assertEqual(e, date(2026, 12, 31))


class TestMonthNames(TestCase):
    def test_all_months_present(self):
        self.assertEqual(len(MONTH_NAMES), 12)
        self.assertEqual(MONTH_NAMES[1], "January")
        self.assertEqual(MONTH_NAMES[12], "December")


# ---------------------------------------------------------------------------
# 2. Payload validation tests
# ---------------------------------------------------------------------------


class TestPayloadValidation(PayrollTestBase):
    def test_missing_month(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={"year": 2026, "basic_payroll": True},
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_missing_year(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={"month": 2, "basic_payroll": True},
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_month_out_of_range(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={"month": 13, "year": 2026, "basic_payroll": True},
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_month_zero(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={"month": 0, "year": 2026, "basic_payroll": True},
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_valid_payload(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={"month": 2, "year": 2026, "basic_payroll": True},
            format="json",
        )
        self.assertIn(resp.status_code, [http_status.HTTP_200_OK])

    # Date-range validation ------------------------------------------------
    def test_start_date_without_end_date_is_invalid(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={"start_date": "2026-02-10", "basic_payroll": True},
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_start_date_after_end_date_is_invalid(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={
                "start_date": "2026-02-20",
                "end_date": "2026-02-10",
                "basic_payroll": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_valid_date_range_payload(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={
                "start_date": "2026-02-10",
                "end_date": "2026-02-25",
                "basic_payroll": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        data = resp.json()
        # returned period should echo the request
        self.assertEqual(data.get("start_date"), "2026-02-10")
        self.assertEqual(data.get("end_date"), "2026-02-25")
        # and payroll object should use the 16-day range
        if data.get("payrolls"):
            p = data["payrolls"][0]
            self.assertEqual(p.get("days_of_month"), 16)
            # working_days should not exceed the range length
            self.assertLessEqual(p.get("working_days"), 16)


# ---------------------------------------------------------------------------
# 3. Permission tests
# ---------------------------------------------------------------------------


class TestPermissions(PayrollTestBase):
    def test_unauthenticated(self):
        client = APIClient()
        resp = client.post(
            "/api/payrolls/generate/",
            data={"month": 2, "year": 2026, "basic_payroll": True},
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_no_permission(self):
        client = self._get_client(self.regular_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={"month": 2, "year": 2026, "basic_payroll": True},
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_with_permission(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={"month": 2, "year": 2026, "basic_payroll": True},
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# 4. Basic payroll generation
# ---------------------------------------------------------------------------


class TestBasicPayrollGeneration(PayrollTestBase):
    def setUp(self):
        self.emp = self._create_employee(self.admin_user, eid="EMP001")
        self.sal = self._create_salary(self.emp)

    def test_generates_payroll_for_active_employee(self):
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        self.assertEqual(len(result), 1)
        p = result[0]
        self.assertEqual(p.payroll_month, "February")
        self.assertEqual(p.payroll_year, 2026)
        self.assertEqual(p.employee, self.emp)

    def test_days_of_month_february_2026(self):
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        self.assertEqual(result[0].days_of_month, 28)

    def test_partial_range_reports_range_lengths(self):
        # when a start/end range is supplied, the payroll record should reflect
        # the actual span rather than defaulting to the full calendar month.
        start = date(2026, 2, 1)
        end = date(2026, 2, 15)
        result = generate_payroll(
            start_date=start, end_date=end, creator=self.admin_user
        )
        p = result[0]
        self.assertEqual(p.days_of_month, (end - start).days + 1)

        # compute expected working days manually using the same weekend logic
        weekend_nums = LeaveBalanceCalculator.get_weekend_days(self.emp)
        expected_work = 0
        d = start
        while d <= end:
            if d.weekday() not in weekend_nums:
                expected_work += 1
            d += timedelta(days=1)
        self.assertEqual(p.working_days, expected_work)

    def test_salary_components_are_set(self):
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = result[0]
        self.assertEqual(p.basic, Decimal("30000"))
        self.assertEqual(p.house_rent, Decimal("10000"))
        self.assertEqual(p.conveyance, Decimal("5000"))
        self.assertEqual(p.medical, Decimal("5000"))
        self.assertEqual(p.gross_salary, Decimal("50000"))
        # no tax settings by default should result in zero tax deduction
        self.assertEqual(p.tax_deduction, Decimal("0"))
        self.assertEqual(p.total_transfer_amount, p.net_salary)


# ---------------------------------------------------------------------------
# 5. Attendance counting (present, late, absent)
# ---------------------------------------------------------------------------


class TestAttendanceCounting(PayrollTestBase):
    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="empcount@test.com",
            username="empcount@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        self.emp = self._create_employee(
            self.emp_user, eid="EMP002", office_days="Sunday-Thursday"
        )
        self.sal = self._create_salary(self.emp)

    def test_present_days_counted(self):
        # Feb 2026: 1st is Sunday → working day for Sun-Thu schedule
        self._create_attendance(self.emp, date(2026, 2, 1), "Present")
        self._create_attendance(self.emp, date(2026, 2, 2), "Present")  # Monday
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.present_days, 2)

    def test_holiday_weekend_presence_counted(self):
        # create a global holiday on Feb 1 and treat Feb 6 as weekend for Sun-Thu
        Holiday.objects.create(
            name="Test Holiday",
            from_date=date(2026, 2, 1),
            to_date=date(2026, 2, 1),
            is_global=True,
        )
        # Present on working day, holiday, and weekend
        self._create_attendance(self.emp, date(2026, 2, 2), "Present")  # Monday
        self._create_attendance(self.emp, date(2026, 2, 1), "Present", is_holiday=True)
        self._create_attendance(self.emp, date(2026, 2, 6), "Present", is_weekend=True)
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        # all three punches count towards present_days
        self.assertEqual(p.present_days, 3)
        # absent days should only consider working days: only one working present
        self.assertEqual(p.absent_days, p.working_days - 1)

    def test_late_days_counted_and_still_present(self):
        self._create_attendance(self.emp, date(2026, 2, 1), "Late", is_late=True)
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        # Late counts as present too
        self.assertEqual(p.present_days, 1)
        self.assertEqual(p.late_days, 1)
        self.assertEqual(p.late_deduction, Decimal("200"))  # 1 × 200

    def test_absent_days_calculated(self):
        # No attendance at all → all working days are absent
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertGreater(p.absent_days, 0)
        self.assertEqual(p.present_days, 0)


# ---------------------------------------------------------------------------
# 6. Deduction calculations
# ---------------------------------------------------------------------------


class TestDeductions(PayrollTestBase):
    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="empded@test.com",
            username="empded@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        self.emp = self._create_employee(
            self.emp_user, eid="EMP003", office_days="Sunday-Thursday"
        )
        self.sal = self._create_salary(
            self.emp, late_deduction=Decimal("500"), absence_deduction=Decimal("1000")
        )

    def test_late_deduction_per_day(self):
        # default threshold is 1, so deduction is per day as before
        self._create_attendance(self.emp, date(2026, 2, 1), "Late", is_late=True)
        self._create_attendance(self.emp, date(2026, 2, 2), "Late", is_late=True)
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.late_days, 2)
        self.assertEqual(p.late_deduction, Decimal("1000"))  # 2 × 500

    def test_late_deduction_with_threshold_and_holiday_policy(self):
        # setup salary with threshold=3 and deduction 200
        self.sal = self._create_salary(
            self.emp,
            late_deduction=Decimal("200"),
            late_count_threshold=3,
            is_late_during_holiday=False,
        )
        # create a holiday on Feb 1
        Holiday.objects.create(
            name="Test Holiday",
            from_date=date(2026, 2, 1),
            to_date=date(2026, 2, 1),
            is_global=True,
        )
        # 7 late attendance records: include holiday (Feb1) and weekend (Feb6=Friday)
        # Sun-Thu schedule means Fri/Sat are weekends
        # Use days 1-5 plus day 6 (Friday=weekend) plus day 8 (Sunday=working)
        for d in [1, 2, 3, 4, 5, 6, 8]:
            is_hol = d == 1
            is_wknd = d == 6  # Friday is a weekend for Sun-Thu schedule
            self._create_attendance(
                self.emp,
                date(2026, 2, d),
                "Late",
                is_late=True,
                is_holiday=is_hol,
                is_weekend=is_wknd,
            )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        # holiday and weekend lateness should be ignored; late_days counts only
        # normal working lates = 5 (days 2,3,4,5,8)
        self.assertEqual(p.late_days, 5)
        # threshold groups -> floor(5/3)=1 so deduction = 200
        self.assertEqual(p.late_deduction, Decimal("200"))

        # now enable holiday/weekend late policy and regenerate
        self.sal.is_late_during_holiday = True
        self.sal.save(update_fields=["is_late_during_holiday"])
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        # late_days should now include holiday+weekend = 7
        self.assertEqual(p.late_days, 7)
        # effective late count now 7 (holiday+weekend included) -> floor(7/3)=2
        self.assertEqual(p.late_deduction, Decimal("400"))

    def test_absence_deduction_per_day(self):
        # Mark exactly 2 working days as present, rest are absent
        self._create_attendance(self.emp, date(2026, 2, 1), "Present")
        self._create_attendance(self.emp, date(2026, 2, 2), "Present")
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        expected_absences = p.working_days - 2
        self.assertEqual(p.absent_days, expected_absences)
        self.assertEqual(p.absence_deduction, Decimal("1000") * expected_absences)


# ---------------------------------------------------------------------------
# 7. Compensation calculations
# ---------------------------------------------------------------------------


class TestCompensations(PayrollTestBase):
    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="empcomp@test.com",
            username="empcomp@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        # Sun-Thu schedule → Fri/Sat are weekends
        self.emp = self._create_employee(
            self.emp_user, eid="EMP004", office_days="Sunday-Thursday"
        )
        self.sal = self._create_salary(
            self.emp,
            holiday_compensation=Decimal("1000"),
            weekday_compensation=Decimal("1500"),
        )

    def test_weekend_compensation(self):
        # Feb 6 2026 is Friday → weekend for Sun-Thu
        self._create_attendance(self.emp, date(2026, 2, 6), "Present", is_weekend=True)
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.weekday_compensation, Decimal("1500"))

    def test_holiday_compensation(self):
        # Create a global holiday on a working day
        Holiday.objects.create(
            name="Test Holiday",
            from_date=date(2026, 2, 1),
            to_date=date(2026, 2, 1),
            is_global=True,
        )
        self._create_attendance(self.emp, date(2026, 2, 1), "Present", is_holiday=True)
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.holiday_compensation, Decimal("1000"))


# ---------------------------------------------------------------------------
# 8. Festival & performance bonus toggling
# ---------------------------------------------------------------------------


class TestBonusToggle(PayrollTestBase):
    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="empbonus@test.com",
            username="empbonus@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        self.emp = self._create_employee(self.emp_user, eid="EMP005")
        self.sal = self._create_salary(
            self.emp,
            festival_bonus=Decimal("5000"),
            performance_bonus=Decimal("3000"),
        )

    def test_both_false(self):
        result = generate_payroll(
            month=2,
            year=2026,
            creator=self.admin_user,
            include_festival_bonus=False,
            include_performance_bonus=False,
        )
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.festival_bonus, Decimal("0"))
        self.assertEqual(p.performance_bonus, Decimal("0"))

    def test_festival_true_performance_false(self):
        result = generate_payroll(
            month=2,
            year=2026,
            creator=self.admin_user,
            include_festival_bonus=True,
            include_performance_bonus=False,
        )
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.festival_bonus, Decimal("5000"))
        self.assertEqual(p.performance_bonus, Decimal("0"))

    def test_both_true(self):
        result = generate_payroll(
            month=2,
            year=2026,
            creator=self.admin_user,
            include_festival_bonus=True,
            include_performance_bonus=True,
        )
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.festival_bonus, Decimal("5000"))
        self.assertEqual(p.performance_bonus, Decimal("3000"))


# ---------------------------------------------------------------------------
# 9. Re-generation updates instead of creating duplicates
# ---------------------------------------------------------------------------


class TestRegeneration(PayrollTestBase):
    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="empregen@test.com",
            username="empregen@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        self.emp = self._create_employee(self.emp_user, eid="EMP006")
        self._create_salary(self.emp)

    def test_no_duplicate_payrolls(self):
        generate_payroll(month=2, year=2026, creator=self.admin_user)
        self.assertEqual(
            Payroll.objects.filter(
                employee=self.emp, payroll_month="February", payroll_year=2026
            ).count(),
            1,
        )

        # Re-generate
        generate_payroll(month=2, year=2026, creator=self.admin_user)
        self.assertEqual(
            Payroll.objects.filter(
                employee=self.emp, payroll_month="February", payroll_year=2026
            ).count(),
            1,
        )

    def test_regeneration_updates_values(self):
        generate_payroll(month=2, year=2026, creator=self.admin_user)
        p_before = Payroll.objects.get(
            employee=self.emp, payroll_month="February", payroll_year=2026
        )
        old_net = p_before.net_salary

        # Add some attendance and re-generate
        self._create_attendance(self.emp, date(2026, 2, 1), "Present")
        generate_payroll(month=2, year=2026, creator=self.admin_user)
        p_after = Payroll.objects.get(pk=p_before.pk)
        # Net salary should change (fewer absences → less deduction → higher net)
        self.assertNotEqual(p_after.net_salary, old_net)
        self.assertGreater(p_after.net_salary, old_net)

    def test_regeneration_via_api(self):
        client = self._get_client(self.admin_user)
        payload = {"month": 2, "year": 2026, "basic_payroll": True}
        resp1 = client.post("/api/payrolls/generate/", data=payload, format="json")
        self.assertEqual(resp1.status_code, http_status.HTTP_200_OK)

        resp2 = client.post("/api/payrolls/generate/", data=payload, format="json")
        self.assertEqual(resp2.status_code, http_status.HTTP_200_OK)

        self.assertEqual(
            Payroll.objects.filter(
                employee=self.emp, payroll_month="February", payroll_year=2026
            ).count(),
            1,
        )


# ---------------------------------------------------------------------------
# 10. Leap year handling
# ---------------------------------------------------------------------------


class TestLeapYear(PayrollTestBase):
    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="empleap@test.com",
            username="empleap@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        self.emp = self._create_employee(self.emp_user, eid="EMP007")
        self._create_salary(self.emp)

    def test_february_leap_year_29_days(self):
        result = generate_payroll(month=2, year=2024, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.days_of_month, 29)

    def test_february_non_leap_year_28_days(self):
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.days_of_month, 28)


# ---------------------------------------------------------------------------
# 11. No active employees → empty result
# ---------------------------------------------------------------------------


class TestNoActiveEmployees(PayrollTestBase):
    def test_empty_result_when_no_active_employees(self):
        # Don't create any employees
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        self.assertEqual(len(result), 0)
        self.assertEqual(Payroll.objects.count(), 0)


# ---------------------------------------------------------------------------
# 12. Employee with no salary record → zero salary fields
# ---------------------------------------------------------------------------


class TestNoSalaryRecord(PayrollTestBase):
    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="empnosal@test.com",
            username="empnosal@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        self.emp = self._create_employee(self.emp_user, eid="EMP008")
        # No salary record created

    def test_zero_salary_fields(self):
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.basic, Decimal("0"))
        self.assertEqual(p.gross_salary, Decimal("0"))
        self.assertEqual(p.net_salary, Decimal("0"))
        self.assertEqual(p.late_deduction, Decimal("0"))
        self.assertEqual(p.absence_deduction, Decimal("0"))


# ---------------------------------------------------------------------------
# 13. Multiple employees in one batch
# ---------------------------------------------------------------------------


class TestMultipleEmployees(PayrollTestBase):
    def setUp(self):
        self.users = []
        self.emps = []
        for i in range(3):
            u = User.objects.create_user(
                email=f"multi{i}@test.com",
                username=f"multi{i}@test.com",
                password="pass123",
            )
            u.role = self.employee_role
            u.is_active = True
            u.save(update_fields=["role", "is_active"])
            emp = self._create_employee(u, eid=f"MULTI{i:03d}")
            self._create_salary(emp)
            self.users.append(u)
            self.emps.append(emp)

    def test_generates_for_all_active(self):
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        self.assertEqual(len(result), 3)
        generated_pks = {p.employee_id for p in result}
        expected_pks = {e.pk for e in self.emps}
        self.assertEqual(generated_pks, expected_pks)


# ---------------------------------------------------------------------------
# 14. Leave integration
# ---------------------------------------------------------------------------


class TestLeaveIntegration(PayrollTestBase):
    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="empleave@test.com",
            username="empleave@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        self.emp = self._create_employee(
            self.emp_user, eid="EMP009", office_days="Sunday-Thursday"
        )
        self._create_salary(self.emp, absence_deduction=Decimal("500"))

        # Create a leave policy
        self.policy = LeavePolicy.objects.create(
            leave_type_name="Casual Leave",
            total_leave_days=10,
            gender="any",
        )
        self.policy.leave_groups.add(self.leave_group)

    def test_approved_leave_reduces_absent(self):
        # Feb 1, 2026 = Sunday (working day for Sun-Thu)
        # Take approved leave on Feb 1
        LeaveRequest.objects.create(
            creator=self.emp_user,
            employee=self.emp,
            leave_policy=self.policy,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 1),
            status="approved",
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        # All working days minus leave days = absent days
        self.assertEqual(p.absent_days, p.working_days - 1)
        self.assertIn("Casual Leave", p.leave_breakdown)

    def test_pending_leave_not_counted(self):
        LeaveRequest.objects.create(
            creator=self.emp_user,
            employee=self.emp,
            leave_policy=self.policy,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 1),
            status="pending",
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        # Pending leave is not considered → all working days are absent
        self.assertEqual(p.absent_days, p.working_days)

    def test_half_day_leave(self):
        LeaveRequest.objects.create(
            creator=self.emp_user,
            employee=self.emp,
            leave_policy=self.policy,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 1),
            is_half_day=True,
            status="approved",
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertIn("Casual Leave", p.leave_breakdown)
        self.assertEqual(p.leave_breakdown["Casual Leave"], 0.5)


# ---------------------------------------------------------------------------
# 15. Holiday and weekend classification
# ---------------------------------------------------------------------------


class TestHolidayWeekendClassification(PayrollTestBase):
    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="emphol@test.com",
            username="emphol@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        self.emp = self._create_employee(
            self.emp_user, eid="EMP010", office_days="Sunday-Thursday"
        )
        self._create_salary(self.emp)

    def test_holidays_counted(self):
        Holiday.objects.create(
            name="National Day",
            from_date=date(2026, 2, 1),
            to_date=date(2026, 2, 2),
            is_global=True,
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        # At least 2 holiday days (some may also be weekends)
        self.assertGreaterEqual(p.holidays, 1)

    def test_weekends_counted(self):
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        # Feb 2026 with Sun-Thu → Fri+Sat are weekends → should be 8 weekend days
        self.assertGreater(p.weekend_days, 0)

    def test_working_days_excludes_weekends_and_holidays(self):
        Holiday.objects.create(
            name="Test Hol",
            from_date=date(2026, 2, 3),  # Tuesday
            to_date=date(2026, 2, 3),
            is_global=True,
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(
            p.days_of_month,
            p.working_days + p.weekend_days + p.holidays,
        )


# ---------------------------------------------------------------------------
# 16. Net salary calculation
# ---------------------------------------------------------------------------


class TestNetSalary(PayrollTestBase):
    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="empnet@test.com",
            username="empnet@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        self.emp = self._create_employee(
            self.emp_user, eid="EMP011", office_days="Sunday-Thursday"
        )
        self._create_salary(
            self.emp,
            basic=Decimal("30000"),
            house_rent=Decimal("10000"),
            conveyance=Decimal("5000"),
            medical=Decimal("5000"),
            absence_deduction=Decimal("500"),
            late_deduction=Decimal("200"),
            holiday_compensation=Decimal("1000"),
            weekday_compensation=Decimal("1500"),
            festival_bonus=Decimal("5000"),
            performance_bonus=Decimal("3000"),
        )

    def test_net_salary_formula(self):
        # Add one late day and one weekend work day
        self._create_attendance(self.emp, date(2026, 2, 1), "Late", is_late=True)
        # Feb 6 is Friday → weekend
        self._create_attendance(self.emp, date(2026, 2, 6), "Present", is_weekend=True)
        result = generate_payroll(
            month=2,
            year=2026,
            creator=self.admin_user,
            include_festival_bonus=True,
            include_performance_bonus=True,
        )
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.late_days, 1)
        expected_net = (
            p.gross_salary
            + p.festival_bonus
            + p.performance_bonus
            + p.holiday_compensation
            + p.weekday_compensation
            - p.late_deduction
            - p.absence_deduction
        )
        self.assertEqual(p.net_salary, expected_net)
        # net salary must never be negative
        self.assertGreaterEqual(p.net_salary, Decimal("0"))

    def test_net_salary_never_negative_when_deductions_exceed_earnings(self):
        # Create a salary with very large deductions so net would be negative
        self._create_salary(
            self.emp,
            basic=Decimal("1000"),
            house_rent=Decimal("0"),
            conveyance=Decimal("0"),
            medical=Decimal("0"),
            absence_deduction=Decimal("10000"),
            late_deduction=Decimal("5000"),
            festival_bonus=Decimal("0"),
            performance_bonus=Decimal("0"),
        )
        # No attendance → all working days are absent (large deduction)
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertGreaterEqual(p.absence_deduction, Decimal("0"))
        # Net salary must be clamped to zero
        self.assertEqual(p.net_salary, Decimal("0"))


# ---------------------------------------------------------------------------
# 16.5 Tax deduction logic


class TestTaxDeduction(PayrollTestBase):
    """Verify that payroll calculates tax deductions correctly based on
    salary configuration.
    """

    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="emptax@test.com",
            username="emptax@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        self.emp = self._create_employee(
            self.emp_user, eid="EMP012T", office_days="Sunday-Thursday"
        )

    def test_no_tax_when_threshold_not_met(self):
        # Net salary (50000) is below threshold (60000)
        self._create_salary(
            self.emp,
            basic=Decimal("30000"),
            house_rent=Decimal("10000"),
            conveyance=Decimal("5000"),
            medical=Decimal("5000"),
            tax_percentage=5,
            tax_amount_threshold=Decimal("60000"),
            absence_deduction=Decimal("0"),
            late_deduction=Decimal("0"),
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = result[0]
        self.assertEqual(p.net_salary, Decimal("50000"))
        self.assertEqual(p.tax_deduction, Decimal("0"))
        self.assertEqual(p.total_transfer_amount, p.net_salary)

    def test_tax_applied_when_threshold_met_exact(self):
        # Gross/net salary will be 40000, threshold 40000 → tax applies
        self._create_salary(
            self.emp,
            basic=Decimal("30000"),
            house_rent=Decimal("10000"),
            conveyance=Decimal("0"),
            medical=Decimal("0"),
            tax_percentage=5,
            tax_amount_threshold=Decimal("40000"),
            absence_deduction=Decimal("0"),
            late_deduction=Decimal("0"),
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = result[0]
        self.assertEqual(p.net_salary, Decimal("40000"))
        self.assertEqual(p.tax_deduction, Decimal("2000"))
        self.assertEqual(p.total_transfer_amount, Decimal("38000"))

    def test_tax_applied_when_above_threshold(self):
        # Net salary 50000 > threshold 40000
        self._create_salary(
            self.emp,
            basic=Decimal("30000"),
            house_rent=Decimal("10000"),
            conveyance=Decimal("5000"),
            medical=Decimal("5000"),
            tax_percentage=10,
            tax_amount_threshold=Decimal("40000"),
            absence_deduction=Decimal("0"),
            late_deduction=Decimal("0"),
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = result[0]
        self.assertEqual(p.net_salary, Decimal("50000"))
        # 10% of 50000
        self.assertEqual(p.tax_deduction, Decimal("5000"))
        self.assertEqual(p.total_transfer_amount, Decimal("45000"))


# ---------------------------------------------------------------------------
# 17. API response structure
# ---------------------------------------------------------------------------


class TestAPIResponse(PayrollTestBase):
    def setUp(self):
        self.emp = self._create_employee(self.admin_user, eid="EMP012")
        self._create_salary(self.emp)

    def test_response_structure(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={"month": 2, "year": 2026, "basic_payroll": True},
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("message", data)
        self.assertIn("month", data)
        self.assertIn("year", data)
        self.assertIn("count", data)
        self.assertIn("payrolls", data)
        self.assertEqual(data["month"], 2)
        self.assertEqual(data["year"], 2026)
        self.assertGreaterEqual(data["count"], 1)
        # ensure new fields are included in each payroll object
        for p in data["payrolls"]:
            self.assertIn("tax_deduction", p)
            self.assertIn("total_transfer_amount", p)


# ---------------------------------------------------------------------------
# 17.5 Lock/unlock API tests


class TestPayrollLocking(PayrollTestBase):
    def setUp(self):
        self.emp = self._create_employee(self.admin_user, eid="EMP013")
        self._create_salary(self.emp)
        # generate initial payroll for Feb 2026 via utility
        generate_payroll(month=2, year=2026, creator=self.admin_user)

    def test_lock_endpoint_sets_flag(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/lock/",
            data={"month": "February", "year": 2026, "is_lock": True},
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["locked_count"], 1)
        self.assertTrue(data["is_locked"])
        p = Payroll.objects.get(payroll_month="February", payroll_year=2026)
        self.assertTrue(p.is_locked)

    def test_locked_period_prevents_regeneration(self):
        # lock via utility (skip API)
        Payroll.objects.filter(payroll_month="February", payroll_year=2026).update(
            is_locked=True
        )
        # attempt to regenerate should raise ValueError for full month
        with self.assertRaises(ValueError):
            generate_payroll(month=2, year=2026, creator=self.admin_user)

        # also try using a date range within February
        with self.assertRaises(ValueError):
            generate_payroll(
                start_date=date(2026, 2, 1),
                end_date=date(2026, 2, 15),
                creator=self.admin_user,
            )

        # api call for month should return 400
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={"month": 2, "year": 2026, "basic_payroll": True},
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn("locked", resp.json().get("error", "").lower())

        # api call for date range should also return 400
        resp2 = client.post(
            "/api/payrolls/generate/",
            data={
                "start_date": "2026-02-01",
                "end_date": "2026-02-15",
                "basic_payroll": True,
            },
            format="json",
        )
        self.assertEqual(resp2.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn("locked", resp2.json().get("error", "").lower())

    def test_unlock_endpoint_clears_flag(self):
        # first lock
        Payroll.objects.filter(payroll_month="February", payroll_year=2026).update(
            is_locked=True
        )
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/lock/",
            data={"month": 2, "year": 2026, "is_lock": False},
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        p = Payroll.objects.get(payroll_month="February", payroll_year=2026)
        self.assertFalse(p.is_locked)
        # now generation should succeed
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        self.assertTrue(result)  # not empty


# ---------------------------------------------------------------------------
# 18. Per-employee generation via employee_ids
# ---------------------------------------------------------------------------


class TestPerEmployeeGeneration(PayrollTestBase):
    """Test the optional employee_ids filter in payroll generation."""

    def setUp(self):
        self.users = []
        self.emps = []
        for i in range(3):
            u = User.objects.create_user(
                email=f"pergen{i}@test.com",
                username=f"pergen{i}@test.com",
                password="pass123",
            )
            u.role = self.employee_role
            u.is_active = True
            u.save(update_fields=["role", "is_active"])
            emp = self._create_employee(u, eid=f"PER{i:03d}")
            self._create_salary(emp)
            self.users.append(u)
            self.emps.append(emp)

    def test_generate_for_specific_employees(self):
        """Only employees in employee_ids should get a payroll."""
        target_ids = [self.emps[0].pk, self.emps[2].pk]
        result = generate_payroll(
            month=2, year=2026, creator=self.admin_user, employee_ids=target_ids
        )
        generated_pks = {p.employee_id for p in result}
        self.assertEqual(generated_pks, set(target_ids))
        self.assertEqual(len(result), 2)

    def test_generate_single_employee(self):
        target_ids = [self.emps[1].pk]
        result = generate_payroll(
            month=2, year=2026, creator=self.admin_user, employee_ids=target_ids
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].employee, self.emps[1])

    def test_empty_employee_ids_generates_nothing(self):
        result = generate_payroll(
            month=2, year=2026, creator=self.admin_user, employee_ids=[]
        )
        self.assertEqual(len(result), 0)

    def test_none_employee_ids_generates_all(self):
        result = generate_payroll(
            month=2, year=2026, creator=self.admin_user, employee_ids=None
        )
        generated_pks = {p.employee_id for p in result}
        expected_pks = {e.pk for e in self.emps}
        self.assertEqual(generated_pks, expected_pks)

    def test_non_existent_id_is_ignored(self):
        result = generate_payroll(
            month=2, year=2026, creator=self.admin_user, employee_ids=[99999]
        )
        self.assertEqual(len(result), 0)

    def test_inactive_employee_id_is_ignored(self):
        # Deactivate the employee
        emp = self.emps[0]
        Employee.objects.filter(pk=emp.pk).update(status="resigned")
        result = generate_payroll(
            month=2, year=2026, creator=self.admin_user, employee_ids=[emp.pk]
        )
        self.assertEqual(len(result), 0)

    def test_employee_ids_via_api(self):
        client = self._get_client(self.admin_user)
        target_ids = [self.emps[0].pk]
        resp = client.post(
            "/api/payrolls/generate/",
            data={
                "month": 2,
                "year": 2026,
                "basic_payroll": True,
                "employee_ids": target_ids,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["count"], 1)


# ---------------------------------------------------------------------------
# 19. Salary effective-date selection
# ---------------------------------------------------------------------------


class TestSalaryEffectiveDate(PayrollTestBase):
    """Test that the correct salary record is used based on effective_date."""

    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="empeffdt@test.com",
            username="empeffdt@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        self.emp = self._create_employee(self.emp_user, eid="EMPEFF01")

    def test_picks_salary_effective_before_month_end(self):
        """Old salary (effective Jan 1) should be used for Jan payroll."""
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("20000"),
            effective_date=date(2026, 1, 1),
        )
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("30000"),
            effective_date=date(2026, 3, 1),
        )
        # Generate for Feb 2026 → should use the Jan salary (20000)
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.basic, Decimal("20000"))

    def test_future_salary_not_used(self):
        """Salary effective after the payroll month is not picked."""
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("10000"),
            effective_date=date(2026, 1, 1),
        )
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("50000"),
            effective_date=date(2026, 6, 1),
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.basic, Decimal("10000"))

    def test_most_recent_effective_date_wins(self):
        """When multiple salaries are effective before month end, latest wins."""
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("10000"),
            effective_date=date(2025, 6, 1),
        )
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("25000"),
            effective_date=date(2026, 2, 1),
        )
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("15000"),
            effective_date=date(2026, 1, 15),
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        # Feb 2026 end → 2026-02-28; effective 2026-02-01 is latest eligible
        self.assertEqual(p.basic, Decimal("25000"))

    def test_null_effective_date_fallback_to_latest_pk(self):
        """Records without effective_date fall back to highest PK."""
        s1 = Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("10000"),
            effective_date=None,
        )
        s2 = Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("20000"),
            effective_date=None,
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        # s2 has the higher PK
        self.assertEqual(p.basic, Decimal("20000"))

    def test_effective_date_takes_priority_over_null(self):
        """A record with a valid effective_date beats a null-dated record."""
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("99999"),
            effective_date=None,
        )
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("15000"),
            effective_date=date(2026, 1, 1),
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        self.assertEqual(p.basic, Decimal("15000"))

    def test_mid_month_revision_picks_latest_before_end(self):
        """Mid-month salary revision: effective Feb 15 is used for Feb payroll."""
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("20000"),
            effective_date=date(2026, 1, 1),
        )
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("35000"),
            effective_date=date(2026, 2, 15),
        )
        result = generate_payroll(month=2, year=2026, creator=self.admin_user)
        p = [r for r in result if r.employee == self.emp][0]
        # Feb 15 is <= Feb 28 → should pick the revision
        self.assertEqual(p.basic, Decimal("35000"))


# ---------------------------------------------------------------------------
# Date-range generation
# ---------------------------------------------------------------------------


class TestDateRangeGeneration(PayrollTestBase):
    def setUp(self):
        self.emp_user = User.objects.create_user(
            email="daterange@test.com",
            username="daterange@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])
        self.emp = self._create_employee(self.emp_user, eid="EMPDATER1")
        self._create_salary(self.emp, basic=Decimal("20000"))

    def test_days_of_month_and_working_days_use_range(self):
        start = date(2026, 2, 10)
        end = date(2026, 2, 25)
        result = generate_payroll(
            start_date=start, end_date=end, creator=self.admin_user
        )
        p = [r for r in result if r.employee == self.emp][0]
        # days_of_month should match the length of the supplied range
        self.assertEqual(p.days_of_month, (end - start).days + 1)
        # payroll month/year still come from end_date
        self.assertEqual(p.payroll_month, "February")
        self.assertEqual(p.payroll_year, 2026)
        # working_days should be computed only within the provided range
        weekend_nums = LeaveBalanceCalculator.get_weekend_days(self.emp)
        # fetch holidays overlapping the range (not the full month)
        holidays = get_holidays_for_employee(
            self.emp,
            Holiday.objects.filter(from_date__lte=end, to_date__gte=start),
        )
        expected_range_working = 0
        d = start
        while d <= end:
            if d.weekday() not in weekend_nums and d not in holidays:
                expected_range_working += 1
            d += timedelta(days=1)
        self.assertEqual(p.working_days, expected_range_working)
        # absent days should also be based on the range
        expected_absent = expected_range_working - p.present_days
        self.assertEqual(p.absent_days, expected_absent)

    def test_proration_factor_applies_for_partial_range(self):
        # create a salary with sizable components
        self._create_salary(
            self.emp,
            basic=Decimal("30000"),
            house_rent=Decimal("15000"),
            conveyance=Decimal("5000"),
            medical=Decimal("3000"),
        )
        # Feb 2026 full working days count (no holidays)
        full_start, full_end = get_month_date_range(2, 2026)
        weekend_nums = LeaveBalanceCalculator.get_weekend_days(self.emp)
        expected_full_working = 0
        d = full_start
        while d <= full_end:
            if d.weekday() not in weekend_nums:
                expected_full_working += 1
            d += timedelta(days=1)
        # add attendance for 7 working days within first half of month
        days = [date(2026, 2, d) for d in range(1, 16)]
        present_days = 0
        for d in days:
            is_wknd = d.weekday() in weekend_nums
            if not is_wknd and present_days < 7:
                self._create_attendance(self.emp, d, "Present")
                present_days += 1
            else:
                self._create_attendance(self.emp, d, "Absent")
        result = generate_payroll(
            start_date=full_start, end_date=date(2026, 2, 15), creator=self.admin_user
        )
        p = [r for r in result if r.employee == self.emp][0]
        # components should remain at their original values
        self.assertEqual(p.basic, Decimal("30000"))
        self.assertEqual(p.house_rent, Decimal("15000"))
        self.assertEqual(p.conveyance, Decimal("5000"))
        self.assertEqual(p.medical, Decimal("3000"))
        # gross should equal per-day rate times actual present days.
        # proration uses the *full*-month working days, even though the
        # payroll record reports the range's working_days field.
        gross_orig = p.basic + p.house_rent + p.conveyance + p.medical
        daily_rate = gross_orig / Decimal(expected_full_working)
        expected_gross = (daily_rate * Decimal(p.present_days)).quantize(
            Decimal("0.01")
        )
        self.assertEqual(p.gross_salary, expected_gross)
        # net salary should reflect the proration (no deductions applied)
        self.assertTrue(p.net_salary <= p.gross_salary)

    def test_salary_selection_uses_end_date(self):
        # Salary revision on Feb 20 should be picked when end_date >= Feb 20
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("15000"),
            effective_date=date(2026, 1, 1),
        )
        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("30000"),
            effective_date=date(2026, 2, 20),
        )

        # end_date before revision → older salary
        r1 = generate_payroll(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 15),
            creator=self.admin_user,
        )
        p1 = [x for x in r1 if x.employee == self.emp][0]
        self.assertEqual(p1.basic, Decimal("15000"))

        # end_date on/after revision → new salary
        r2 = generate_payroll(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 25),
            creator=self.admin_user,
        )
        p2 = [x for x in r2 if x.employee == self.emp][0]
        self.assertEqual(p2.basic, Decimal("30000"))

    def test_date_range_with_employee_ids(self):
        other = self._create_employee(self.admin_user, eid="EMPDATER2")
        self._create_salary(other)
        start = date(2026, 2, 1)
        end = date(2026, 2, 10)
        result = generate_payroll(
            start_date=start,
            end_date=end,
            creator=self.admin_user,
            employee_ids=[self.emp.pk],
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].employee, self.emp)

    def test_api_date_range_endpoint(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={
                "start_date": "2026-02-10",
                "end_date": "2026-02-25",
                "basic_payroll": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("start_date", data)
        self.assertIn("end_date", data)
        self.assertEqual(data["start_date"], "2026-02-10")
        self.assertEqual(data["end_date"], "2026-02-25")
        # payroll object should reflect the 16-day span
        self.assertIn("payrolls", data)
        if data["payrolls"]:
            p = data["payrolls"][0]
            self.assertEqual(p.get("days_of_month"), 16)
            self.assertLessEqual(p.get("working_days"), 16)


# ---------------------------------------------------------------------------
# 20. Async (threaded) generation
# ---------------------------------------------------------------------------


class TestAsyncGeneration(TransactionTestCase):
    """Test background thread payroll generation.

    Uses TransactionTestCase because Django's TestCase wraps each test in a
    transaction that is invisible to spawned threads.  TransactionTestCase
    commits to the actual DB so the background thread can see the data.
    """

    def setUp(self):
        # ---- Role ----------------------------------------------------------
        self.admin_role, _ = Role.objects.get_or_create(name="Admin")
        self.employee_role, _ = Role.objects.get_or_create(name="Employee")

        # ---- Shift ---------------------------------------------------------
        self.shift = Shift.objects.create(
            name="General",
            office_start_time=time(9, 0),
            office_end_time=time(17, 0),
            office_start_time_consideration=10,
            office_end_time_consideration=10,
            check_in_start_time=time(8, 0),
            check_in_end_time=time(10, 0),
            check_out_start_time=time(16, 0),
            check_out_end_time=time(18, 0),
        )

        # ---- Admin user (with add_payroll permission) ----------------------
        self.admin_user = User.objects.create_user(
            email="asyncadmin@test.com",
            username="asyncadmin@test.com",
            password="adminpass123",
        )
        self.admin_user.role = self.admin_role
        self.admin_user.is_active = True
        self.admin_user.is_staff = True
        self.admin_user.save(update_fields=["role", "is_active", "is_staff"])

        ct = ContentType.objects.get_for_model(Payroll)
        perm = Permission.objects.get(content_type=ct, codename="add_payroll")
        self.admin_user.user_permissions.add(perm)

        # ---- Department / Designation / Branch / Leave group ---------------
        self.dept = Department.objects.create(name="Async Dept")
        self.desig = Designation.objects.create(name="Async Dev", department=self.dept)
        self.branch = Branch.objects.create(name="Async HQ", address="456 St")
        self.leave_group = LeaveGroup.objects.create(name="Async General")

        # ---- Employee + salary ---------------------------------------------
        self.emp_user = User.objects.create_user(
            email="empasync@test.com",
            username="empasync@test.com",
            password="pass123",
        )
        self.emp_user.role = self.employee_role
        self.emp_user.is_active = True
        self.emp_user.save(update_fields=["role", "is_active"])

        self.emp = Employee(
            user=self.emp_user,
            employee_id="EMPASYNC1",
            employee_name="empasync",
            department=self.dept,
            designation=self.desig,
            location=self.branch,
            joining_date=date(2024, 1, 1),
            office_days="Sunday-Thursday",
            office_time=self.shift,
            status="active",
            present_address="Test",
            permanent_address="Test",
            personal_mobile_number="0123456789",
            gender="male",
            leave_group=self.leave_group,
        )
        Employee.save(self.emp)

        Salary.objects.create(
            employee=self.emp,
            creator=self.admin_user,
            basic=Decimal("30000"),
            house_rent=Decimal("10000"),
            conveyance=Decimal("5000"),
            medical=Decimal("5000"),
            festival_bonus=Decimal("5000"),
            performance_bonus=Decimal("3000"),
            absence_deduction=Decimal("500"),
            late_deduction=Decimal("200"),
            holiday_compensation=Decimal("1000"),
            weekday_compensation=Decimal("1500"),
        )

    def _get_client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_async_creates_payroll(self):
        thread = generate_payroll_async(
            month=2, year=2026, creator_id=self.admin_user.pk
        )
        thread.join(timeout=60)
        self.assertFalse(thread.is_alive(), "Thread should have completed")

        payrolls = Payroll.objects.filter(
            employee=self.emp, payroll_month="February", payroll_year=2026
        )
        self.assertEqual(payrolls.count(), 1)

    def test_async_creates_notification(self):
        thread = generate_payroll_async(
            month=2, year=2026, creator_id=self.admin_user.pk
        )
        thread.join(timeout=60)
        self.assertFalse(thread.is_alive())

        notif = Notification.objects.filter(
            receiver=self.admin_user, type="payroll"
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn("February", notif.title)
        self.assertIn("2026", notif.title)
        self.assertIn("Generated", notif.title)

    def test_async_with_employee_ids(self):
        thread = generate_payroll_async(
            month=2,
            year=2026,
            creator_id=self.admin_user.pk,
            employee_ids=[self.emp.pk],
        )
        thread.join(timeout=60)
        self.assertFalse(thread.is_alive())

        payrolls = Payroll.objects.filter(
            employee=self.emp, payroll_month="February", payroll_year=2026
        )
        self.assertEqual(payrolls.count(), 1)

    def test_async_via_api_returns_202(self):
        client = self._get_client(self.admin_user)
        resp = client.post(
            "/api/payrolls/generate/",
            data={
                "month": 2,
                "year": 2026,
                "basic_payroll": True,
                "async_generation": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, http_status.HTTP_202_ACCEPTED)
        data = resp.json()
        self.assertTrue(data["async"])
        self.assertIn("background", data["message"].lower())

        # Wait for the thread to finish
        _time.sleep(5)

        payrolls = Payroll.objects.filter(
            employee=self.emp, payroll_month="February", payroll_year=2026
        )
        self.assertEqual(payrolls.count(), 1)

    def test_async_with_bonus_flags(self):
        thread = generate_payroll_async(
            month=2,
            year=2026,
            creator_id=self.admin_user.pk,
            include_festival_bonus=True,
            include_performance_bonus=True,
        )
        thread.join(timeout=60)
        self.assertFalse(thread.is_alive())

        p = Payroll.objects.get(
            employee=self.emp, payroll_month="February", payroll_year=2026
        )
        self.assertGreater(p.festival_bonus, Decimal("0"))
        self.assertGreater(p.performance_bonus, Decimal("0"))
