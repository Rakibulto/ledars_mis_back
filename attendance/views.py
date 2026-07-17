from django.db.models import Q
from django.forms import ValidationError
from rest_framework import generics
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from collections import defaultdict
from .models import (
    AttendanceData,
    AttendanceAdjustmentRequest,
    AttendanceAdjustmentApproval,
    AttendanceHistory,
    CutOff,
)
from authentication.models import Role, PreApprovedIP, AllowedAnyIPLogins
from notification.models import Notification
from employee.models import Employee
from .serializers import (
    AttendanceAdjustmentApprovalSerializer,
    AttendanceDataSerializer,
    EmployeeAttendanceReportSerializer,
    DailyAttendanceSerializer,
    AttendanceAdjustmentSerializer,
    AttendanceAdjustmentApprovalUpdateSerializer,
    CutOffSerializer,
)
from rest_framework.exceptions import PermissionDenied
import django_filters
from rest_framework import viewsets
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime
from django.utils.timezone import timedelta
from dateutil.relativedelta import relativedelta
from holiday.models import Holiday
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from rest_framework.exceptions import ValidationError, PermissionDenied
from leave.models import LeaveRequest
from .serializers import (
    AttendanceHistorySerialzier,
    EmployeeAttendanceTimeStampSerializer,
)
from django.db.models import Prefetch
from rest_framework.views import APIView, status
from django.utils.timezone import localtime
from .pagination import StandardResultsSetPagination

import logging

import logging

logger = logging.getLogger(__name__)


class EmployeeAttendanceFilter(django_filters.FilterSet):
    employee_name = django_filters.CharFilter(
        field_name="employee_name", lookup_expr="icontains"
    )
    rfid_no = django_filters.CharFilter(
        field_name="rfid_or_machine_code", lookup_expr="icontains"
    )
    department = django_filters.NumberFilter(
        field_name="department__id"
    )  # Filter by department ID
    branch = django_filters.NumberFilter(
        field_name="location__id"
    )  # Filter by branch ID
    # Date range filters will be handled manually in the serializer's get_attendance method context

    class Meta:
        model = Employee
        fields = ["employee_name", "rfid_no", "department", "branch"]


# Optimized AttendanceReportViewSet using Attendance History without timestamps
class AttendanceReportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeAttendanceReportSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        Customizes the queryset for both list and retrieve actions based on URL parameters.
        """
        # Ensure user is accessed from self.request
        user = self.request.user

        if not user.is_authenticated:
            raise PermissionDenied(
                "You must be authenticated to view attendance reports"
            )

        queryset = super().get_queryset()

        # Determine the query date range so that we can include resigned/terminated
        # employees who were still active at the start of the requested period.
        start_date_str = self.request.query_params.get("start_date")
        end_date_str = self.request.query_params.get("end_date")
        # use helper to parse; provides sensible defaults when values are missing
        query_start_date, query_end_date = self._parse_and_validate_dates(
            start_date_str, end_date_str
        )

        # Apply status filter: include only active/incomplete employees or
        # those whose resign/terminate date is on or after the *start* of the
        # requested period.  Previously `today` was used which excluded anyone
        # who had already resigned even if the report covered earlier days.
        queryset = queryset.filter(
            Q(status__in=["active", "incomplete"])
            | Q(
                status__in=["resigned", "terminated"],
                resign_terminated_date__gte=query_start_date,
            )
        )

        # If user has no role assigned but has "view_own_attendance" permission
        if not hasattr(user, "role"):
            if user.has_perm("attendance.view_own_attendance"):
                return queryset.filter(user=user).select_related("office_time")
            raise PermissionDenied(
                "You do not have permission to view attendance reports"
            )

        # If user role is "Admin", user can view all employee reports
        if user.role.name == "Admin":
            pass
        elif user.role.name == "Supervisor":
            # If Supervisor has "view_attendancedata" permission, view all reports
            if user.has_perm("attendance.view_attendancedata"):
                pass
            else:
                # Build filter conditions based on available permissions
                filter_conditions = []

                # If Supervisor has "view_subordinate_attendance" permission, include subordinates
                if user.has_perm("attendance.view_subordinate_attendance"):
                    filter_conditions.append(Q(supervisor=user))

                # If Supervisor has "view_own_attendance" permission, include own data
                if user.has_perm("attendance.view_own_attendance"):
                    filter_conditions.append(Q(user=user))

                if filter_conditions:
                    # Combine conditions with OR
                    combined_filter = filter_conditions[0]
                    for condition in filter_conditions[1:]:
                        combined_filter |= condition
                    queryset = queryset.filter(combined_filter)
                    # Always use distinct when filtering by ManyToMany relationships to prevent duplicates
                    queryset = queryset.distinct()
                else:
                    raise PermissionDenied(
                        "You do not have permission to view attendance reports"
                    )
        elif user.role.name == "Employee":
            # If Employee has "view_own_attendance" permission, view only own reports
            if user.has_perm("attendance.view_own_attendance"):
                queryset = queryset.filter(user=user)
            elif user.has_perm("attendance.view_attendancedata"):
                # If Employee has "view_attendancedata" permission, view all reports
                pass
            else:
                raise PermissionDenied(
                    "You do not have permission to view attendance reports"
                )
        else:
            raise PermissionDenied(
                "You do not have permission to view attendance reports"
            )

        if self.action == "retrieve":
            if "pk" in self.kwargs:
                queryset = queryset.filter(pk=self.kwargs["pk"])

        if self.action == "list":
            queryset = self._apply_employee_filters(queryset, self.request.query_params)

        # Prefetch office_time to avoid N+1 for shift details
        queryset = queryset.select_related("office_time")

        return queryset

    def list(self, request, *args, **kwargs):
        employees = self.get_queryset()
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        query_start_date, query_end_date = self._parse_and_validate_dates(
            start_date_str, end_date_str
        )
        pagination = request.query_params.get("pagination", "false").lower() == "true"
        batch_size = request.query_params.get("batch_size")

        # OPTIMIZATION: Apply pagination at database level BEFORE processing
        # This dramatically improves performance for large datasets
        paginated_employee_list = None
        if pagination:
            # Set page size from batch_size or use default
            page_size = batch_size if batch_size else 100
            try:
                page_size = int(page_size)
                if page_size <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                page_size = 100

            self.pagination_class.page_size = page_size

            # Paginate at database level - only fetch the employees for current page
            paginated_employee_list = self.paginate_queryset(employees)
            if paginated_employee_list is not None:
                # Get the PKs from paginated list and re-query to get a proper queryset
                employee_pks = [emp.pk for emp in paginated_employee_list]
                employees = Employee.objects.filter(pk__in=employee_pks).select_related(
                    "office_time"
                )

        employees = employees.prefetch_related(
            Prefetch(
                "attendance_history",
                queryset=AttendanceHistory.objects.filter(
                    date__range=[query_start_date, query_end_date]
                ),
                to_attr="_prefetched_attendance_history",
            ),
            Prefetch(
                "leave_requests",
                queryset=LeaveRequest.objects.filter(
                    status__iexact="approved",
                    start_date__lte=query_end_date,
                    end_date__gte=query_start_date,
                ),
                to_attr="_prefetched_approved_leaves",
            ),
        )

        # Pre-fetch holidays globally for the entire date range
        holidays = Holiday.objects.filter(
            from_date__lte=query_end_date, to_date__gte=query_start_date
        ).prefetch_related(
            "branches",
            "designations",
            "departments",
            "assigned_employees",
            "excluded_employees",
        )

        # Extract filter flags
        filters = {
            "filter_present": request.query_params.get("present", "false").lower()
            == "true",
            "filter_absent": request.query_params.get("absent", "false").lower()
            == "true",
            "filter_late_in": request.query_params.get("late_in", None),
            "filter_early_out": request.query_params.get("early_out", "false").lower()
            == "true",
            "filter_half_day": request.query_params.get("half_day", "false").lower()
            == "true",
            "filter_on_leave": request.query_params.get("on_leave", "false").lower()
            == "true",
        }

        # OPTIMIZED VERSION: Using efficient batch processing
        try:
            # Use the efficient processing function
            filtered_employees_for_report = self._filter_employees_efficiently(
                employees, query_start_date, query_end_date, holidays, filters
            )
        except Exception as e:
            # Fallback to original logic if optimization fails
            logger.warning(f"Optimization failed, falling back to original logic: {e}")
            filtered_employees_for_report = self._filter_employees_original(
                employees, query_start_date, query_end_date, holidays, filters
            )

        # ORIGINAL LOGIC (COMMENTED OUT FOR REFERENCE)
        # filtered_employees_for_report = []
        # for employee in employees:
        #     # Filter attendance history based on resign_terminated_date
        #     if employee.status in ['resigned', 'terminated'] and employee.resign_terminated_date:
        #         employee._prefetched_attendance_history = [
        #             entry for entry in employee._prefetched_attendance_history
        #             if entry.date < employee.resign_terminated_date
        #         ]
        #         employee._prefetched_approved_leaves = [
        #             leave for leave in employee._prefetched_approved_leaves
        #             if leave.start_date < employee.resign_terminated_date
        #         ]

        #     employee_attendance = {entry.date: entry for entry in employee._prefetched_attendance_history}
        #     employee_approved_leaves = employee._prefetched_approved_leaves

        #     meets_attendance_criteria = False
        #     current_date = query_start_date

        #     while current_date <= query_end_date:
        #         # Skip dates after resign_terminated_date for resigned/terminated employees
        #         if employee.status in ['resigned', 'terminated'] and employee.resign_terminated_date and current_date > employee.resign_terminated_date:
        #             current_date += timedelta(days=1)
        #             continue

        #         is_working_day = current_date.weekday() in self._get_working_days(employee.office_days)
        #         is_holiday = self._is_holiday_for_employee(current_date, employee, holidays)

        #         # Get the pre-calculated attendance history for this specific day
        #         daily_record = employee_attendance.get(current_date)

        #         # Calculate the daily status based on pre-calculated data and day type
        #         daily_data = self._calculate_daily_attendance_status(
        #             current_date, daily_record, employee, is_holiday, is_working_day, employee_approved_leaves
        #         )

        #         if self._day_meets_attendance_filter(daily_data, filters):
        #             meets_attendance_criteria = True
        #             break
        #         current_date += timedelta(days=1)

        #     if not any(filters.values()) or meets_attendance_criteria:
        #         filtered_employees_for_report.append(employee)

        # Handle batch_size for non-paginated requests
        if batch_size and not pagination:
            try:
                batch_size = int(batch_size)
                if batch_size <= 0:
                    raise ValueError
                filtered_employees_for_report = filtered_employees_for_report[
                    :batch_size
                ]
            except ValueError:
                raise ValidationError(
                    {"batch_size": "Invalid batch size. Must be a positive integer"}
                )

        serializer_context = {
            "request": request,
            "query_start_date": query_start_date,
            "query_end_date": query_end_date,
            **filters,
            "holidays": holidays,
            "view": self,
        }

        serializer = self.get_serializer(
            filtered_employees_for_report, many=True, context=serializer_context
        )

        # Return paginated response if pagination was applied at database level
        if pagination:
            return self.get_paginated_response(serializer.data)

        # Return non-paginated response
        return Response(serializer.data)

    # def retrieve(self, request, *args, **kwargs):
    #     instance = self.get_object()

    #     # Pre-fetch office_time for the single employee
    #     instance = instance.__class__.objects.select_related('office_time').get(pk=instance.pk)

    #     start_date_str = request.query_params.get('start_date')
    #     end_date_str = request.query_params.get('end_date')
    #     query_start_date, query_end_date = self._parse_and_validate_dates(start_date_str, end_date_str)

    #     # Pre-fetch attendance history for the single employee
    #     instance._prefetched_attendance_history = list(AttendanceHistory.objects.filter(
    #         employee=instance,
    #         date__range=[query_start_date, query_end_date]
    #     ).select_related('employee').order_by('date'))

    #     # Pre-fetch holidays
    #     holidays = Holiday.objects.filter(
    #         from_date__lte=query_end_date,
    #         to_date__gte=query_start_date
    #     ).prefetch_related('branches', 'designations', 'departments', 'assigned_employees', 'excluded_employees')

    #     # Pre-fetch approved leave requests for the single employee
    #     instance._prefetched_approved_leaves = list(LeaveRequest.objects.filter(
    #         employee=instance,
    #         status__iexact='approved',
    #         start_date__lte=query_end_date,
    #         end_date__gte=query_start_date
    #     ))

    #     serializer_context = {
    #         'request': request,
    #         'query_start_date': query_start_date,
    #         'query_end_date': query_end_date,
    #         'filter_present': request.query_params.get('present', 'false').lower() == 'true',
    #         'filter_absent': request.query_params.get('absent', 'false').lower() == 'true',
    #         'filter_late_in': request.query_params.get('late_in', None),
    #         'filter_early_out': request.query_params.get('early_out', 'false').lower() == 'true',
    #         'filter_half_day': request.query_params.get('half_day', 'false').lower() == 'true',
    #         'filter_on_leave': request.query_params.get('on_leave', 'false').lower() == 'true', # Added for consistency
    #         'view': self,
    #         'holidays': holidays,
    #     }

    #     serializer = self.get_serializer(instance, context=serializer_context)
    #     return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # Pre-fetch office_time for the single employee
        instance = instance.__class__.objects.select_related("office_time").get(
            pk=instance.pk
        )

        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        include_supervised = (
            request.query_params.get("include_supervised", "false").lower() == "true"
        )
        query_start_date, query_end_date = self._parse_and_validate_dates(
            start_date_str, end_date_str
        )

        # Initialize the response data
        response_data = []

        # Filter attendance history and leaves based on resign_terminated_date
        attendance_filter = Q(
            employee=instance, date__range=[query_start_date, query_end_date]
        )
        if (
            instance.status in ["resigned", "terminated"]
            and instance.resign_terminated_date
        ):
            attendance_filter &= Q(date__lte=instance.resign_terminated_date)

        # Pre-fetch attendance history and approved leaves for the requested employee
        instance._prefetched_attendance_history = list(
            AttendanceHistory.objects.filter(
                employee=instance, date__range=[query_start_date, query_end_date]
            )
            .select_related("employee")
            .order_by("date")
        )

        leave_filter = Q(
            employee=instance,
            status__iexact="approved",
            start_date__lte=query_end_date,
            end_date__gte=query_start_date,
        )

        if (
            instance.status in ["resigned", "terminated"]
            and instance.resign_terminated_date
        ):
            leave_filter &= Q(start_date__lte=instance.resign_terminated_date)

        instance._prefetched_approved_leaves = list(
            LeaveRequest.objects.filter(leave_filter)
        )

        # Pre-fetch holidays
        holidays = Holiday.objects.filter(
            from_date__lte=query_end_date, to_date__gte=query_start_date
        ).prefetch_related(
            "branches",
            "designations",
            "departments",
            "assigned_employees",
            "excluded_employees",
        )

        serializer_context = {
            "request": request,
            "query_start_date": query_start_date,
            "query_end_date": query_end_date,
            "filter_present": request.query_params.get("present", "false").lower()
            == "true",
            "filter_absent": request.query_params.get("absent", "false").lower()
            == "true",
            "filter_late_in": request.query_params.get("late_in", None),
            "filter_early_out": request.query_params.get("early_out", "false").lower()
            == "true",
            "filter_half_day": request.query_params.get("half_day", "false").lower()
            == "true",
            "filter_on_leave": request.query_params.get("on_leave", "false").lower()
            == "true",
            "view": self,
            "holidays": holidays,
        }

        # Add the requested employee's attendance data
        serializer = self.get_serializer(instance, context=serializer_context)
        response_data.append(serializer.data)

        # Check if the employee is a Supervisor and if include_supervised is true
        if include_supervised and instance.user.role.name == "Supervisor":
            # Fetch employees supervised by this employee
            supervised_employees = (
                Employee.objects.filter(supervisor=instance.user)
                .select_related("office_time")
                .prefetch_related(
                    Prefetch(
                        "attendance_history",
                        queryset=AttendanceHistory.objects.filter(
                            date__range=[query_start_date, query_end_date]
                        ).filter(
                            Q(employee__status__in=["active", "incomplete"])
                            | Q(
                                employee__status__in=["resigned", "terminated"],
                                date__lte=employee__resign_terminated_date,
                            )
                        ),
                        to_attr="_prefetched_attendance_history",
                    ),
                    Prefetch(
                        "leave_requests",
                        queryset=LeaveRequest.objects.filter(
                            status__iexact="approved",
                            start_date__lte=query_end_date,
                            end_date__gte=query_start_date,
                        ).filter(
                            Q(employee__status__in=["active", "incomplete"])
                            | Q(
                                employee__status__in=["resigned", "terminated"],
                                start_date__lte=employee__resign_terminated_date,
                            )
                        ),
                        to_attr="_prefetched_approved_leaves",
                    ),
                )
            )

            # Serialize attendance data for supervised employees
            for employee in supervised_employees:
                serializer = self.get_serializer(employee, context=serializer_context)
                response_data.append(serializer.data)

        return Response(response_data)

    def _calculate_daily_attendance_status(
        self,
        current_date,
        daily_record,
        employee,
        is_holiday,
        is_working_day,
        approved_leaves,
    ):
        """
        Calculates the status for a single day, incorporating holiday and weekend logic,
        primarily using pre-calculated data from AttendanceHistory.
        """
        # Initialize daily_data with default/pre-calculated values from AttendanceHistory
        daily_data = {
            "date": current_date.strftime("%d-%m-%Y"),
            # "timestamps": [],
            "is_late": daily_record.is_late if daily_record else False,
            "check_in": daily_record.check_in_time if daily_record else None,
            "check_out": daily_record.check_out_time if daily_record else None,
            "late_by": (
                str(daily_record.late_by)
                if daily_record and daily_record.late_by
                else None
            ),
            "early_out_by": (
                str(daily_record.early_out_by)
                if daily_record and daily_record.early_out_by
                else None
            ),
            "actual_work_duration": None,
            "expected_work_duration": None,
            "status": daily_record.status if daily_record else "Absent",
            "remarks": daily_record.remarks if daily_record else None,
        }

        # Calculate work durations if check-in and check-out exist
        if daily_data["check_in"] and daily_data["check_out"] and employee.office_time:
            shift_start_time = timezone.make_aware(
                datetime.combine(current_date, employee.office_time.office_start_time),
                timezone.get_current_timezone(),
            )
            is_overnight = (
                employee.office_time.office_end_time
                < employee.office_time.office_start_time
            )
            shift_end_time = timezone.make_aware(
                datetime.combine(current_date, employee.office_time.office_end_time),
                timezone.get_current_timezone(),
            )
            if is_overnight:
                shift_end_time += timedelta(days=1)

            shift_duration = (shift_end_time - shift_start_time).total_seconds()
            actual_duration = (
                daily_data["check_out"] - daily_data["check_in"]
            ).total_seconds()

            hours, remainder = divmod(actual_duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            daily_data["actual_work_duration"] = (
                f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
            )

            hours, remainder = divmod(shift_duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            daily_data["expected_work_duration"] = (
                f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
            )

        is_leave_day = any(
            leave.start_date <= current_date <= leave.end_date
            for leave in approved_leaves
        )
        is_half_day_leave = any(
            leave.start_date <= current_date <= leave.end_date and leave.is_half_day
            for leave in approved_leaves
        )

        # Override status for holidays, weekends, and leaves
        if is_holiday:
            daily_data["status"] = "Holiday"
        elif is_leave_day:
            daily_data["status"] = "Half Day Leave" if is_half_day_leave else "Leave"
        elif not is_working_day:
            daily_data["status"] = "Weekend"
        elif daily_record and daily_record.check_in_time:
            # If there's a record, and it's not a holiday/weekend/leave,
            daily_data["status"] = daily_record.status
        else:
            # If no daily record exists for a working day and not a leave/holiday
            daily_data["status"] = "Absent"

        return daily_data

    def _parse_and_validate_dates(self, start_date_str, end_date_str):
        today = timezone.localdate()
        query_start_date = None
        query_end_date = None

        if start_date_str:
            try:
                query_start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                raise serializers.ValidationError(
                    {"start_date": "Invalid date format. Use YYYY-MM-DD."}
                )
        if end_date_str:
            try:
                query_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                raise serializers.ValidationError(
                    {"end_date": "Invalid date format. Use YYYY-MM-DD."}
                )

        # Set default date range if not provided
        if not query_start_date and not query_end_date:
            query_end_date = today
            # Default to last 30 days including today
            query_start_date = today - timedelta(days=29)
        elif not query_start_date:
            query_start_date = query_end_date - timedelta(days=29)
        elif not query_end_date:
            query_end_date = query_start_date + timedelta(days=29)

        # Ensure dates are within logical bounds
        if query_end_date > today:
            query_end_date = today
        if query_start_date > query_end_date:
            query_start_date = query_end_date

        return query_start_date, query_end_date

    def get_attendance_report_for_employee(
        self,
        obj,
        attendance_data,
        query_start_date,
        query_end_date,
        filters,
        holidays=None,
    ):
        working_days = self._get_working_days(obj.office_days)
        holidays = holidays or []

        # Use the prefetched approved leaves from the employee object
        approved_leaves = getattr(obj, "_prefetched_approved_leaves", [])

        attendance_report = []
        effective_end_date = min(
            query_end_date,
            (
                obj.resign_terminated_date - timedelta(days=1)
                if obj.status in ["resigned", "terminated"]
                and obj.resign_terminated_date
                else query_end_date
            ),
        )
        current_date = query_start_date
        while current_date <= effective_end_date:
            if (
                obj.status in ["resigned", "terminated"]
                and obj.resign_terminated_date
                and current_date > obj.resign_terminated_date
            ):
                current_date += timedelta(days=1)
                continue
            is_working_day = current_date.weekday() in working_days
            is_holiday = self._is_holiday_for_employee(current_date, obj, holidays)

            # Get the pre-calculated attendance history for this specific day
            daily_record = next(
                (
                    ah
                    for ah in getattr(obj, "_prefetched_attendance_history", [])
                    if ah.date == current_date
                ),
                None,
            )

            daily_data = self._calculate_daily_attendance_status(
                current_date,
                daily_record,
                obj,
                is_holiday,
                is_working_day,
                approved_leaves,
            )

            # Apply final filter for inclusion in the report (this is `_should_add_to_report`)
            if self._should_add_to_report(daily_data, filters):
                serialized_data = DailyAttendanceSerializer(daily_data).data
                attendance_report.append(serialized_data)

            current_date += timedelta(days=1)

        attendance_report.sort(
            key=lambda x: datetime.strptime(x["date"], "%d-%m-%Y").date()
        )
        return attendance_report

    def _get_working_days(self, office_days_str):
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
                # Handle wrap-around (e.g., Friday-Wednesday means Friday, Saturday, Sunday, Monday, Tuesday, Wednesday)
                working_days = list(range(start_idx, 7)) + list(range(0, end_idx + 1))
        else:
            # Handle single day or comma-separated days (e.g., "Sunday", "Monday,Wednesday")
            working_days = [
                days_map.get(day.lower().strip(), 6)
                for day in office_days_str.split(",")
            ]
        return set(working_days)

    def _is_holiday_for_employee(self, date, employee, holidays):
        """
        Checks if the given date is a holiday for the employee based on the Holiday model.
        """
        for holiday in holidays:
            if holiday.from_date <= date <= holiday.to_date:
                if holiday.is_applicable_to_employee(employee):
                    return True
        return False

    def _apply_employee_filters(self, queryset, query_params):
        """
        Applies filters directly to the Employee queryset.
        """
        employee_id = query_params.get("employee_id")
        employee_name = query_params.get("employee_name")
        rfid = query_params.get("rfid")
        user_email = query_params.get("user_email")
        department_name = query_params.get("department")
        designation_name = query_params.get("designation")
        branch_name = query_params.get("branch")
        supervisor_id = query_params.get("supervisor")

        keywords = query_params.get("keywords")
        if keywords:
            keyword_filter = (
                Q(employee_name__icontains=keywords)
                | Q(employee_id__icontains=keywords)
                | Q(rfid_or_machine_code__icontains=keywords)
                | Q(user__email__icontains=keywords)
            )
            queryset = queryset.filter(keyword_filter)

        if employee_id:
            queryset = queryset.filter(employee_id__icontains=employee_id)
        if employee_name:
            queryset = queryset.filter(employee_name__icontains=employee_name)
        if rfid:
            queryset = queryset.filter(rfid_or_machine_code__icontains=rfid)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
        if department_name:
            queryset = queryset.filter(department__name__icontains=department_name)
        if designation_name:
            queryset = queryset.filter(designation__name__icontains=designation_name)
        if branch_name:
            queryset = queryset.filter(location__name__icontains=branch_name)
        if supervisor_id:
            try:
                supervisor_id = int(supervisor_id)
                queryset = queryset.filter(supervisor__id=supervisor_id)
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    {"supervisor": "Invalid supervisor ID. Must be a valid integer."}
                )
        return queryset

    def _day_meets_attendance_filter(self, daily_data, filters):
        """
        Checks if a single day's attendance data matches the requested filters.
        This is used for the *pre-filtering* of employees in the list method.
        """
        filter_present = filters["filter_present"]
        filter_absent = filters["filter_absent"]
        filter_late_in = filters["filter_late_in"]
        filter_early_out = filters["filter_early_out"]
        filter_half_day = filters["filter_half_day"]
        filter_on_leave = filters["filter_on_leave"]

        # If no attendance-specific filters are active, any day implicitly meets the criteria
        if not any(
            [
                filter_present,
                filter_absent,
                filter_late_in is not None,
                filter_early_out,
                filter_half_day,
                filter_on_leave,
            ]
        ):
            return True

        # Check against each active filter
        if filter_present and daily_data["status"] == "Present":
            return True

        if filter_absent and daily_data["status"] == "Absent":
            return True

        if filter_late_in is not None:
            if filter_late_in.lower() == "true" and daily_data["is_late"] is True:
                return True
            elif filter_late_in.lower() == "false" and daily_data["is_late"] is False:
                return True

        if filter_early_out and daily_data["early_out_by"] is not None:
            return True

        if filter_half_day and daily_data["status"] == "Half Day":
            return True

        # IMPORTANT: 'Leave' status will be set by _calculate_daily_attendance_status if a leave exists
        if filter_on_leave and daily_data["status"] in ["Leave", "Half Day Leave"]:
            return True

        return False

    def _should_add_to_report(self, daily_data, filters):
        """
        Applies filtering logic to decide if a daily attendance record should be included.
        """
        filter_present = filters["filter_present"]
        filter_absent = filters["filter_absent"]
        filter_late_in = filters["filter_late_in"]
        filter_early_out = filters["filter_early_out"]
        filter_half_day = filters["filter_half_day"]
        # Added filter_on_leave here for consistency
        filter_on_leave = filters["filter_on_leave"]

        # If no specific filters are applied, include all days
        if not any(
            [
                filter_present,
                filter_absent,
                filter_late_in is not None,
                filter_early_out,
                filter_half_day,
                filter_on_leave,
            ]
        ):
            return True
        else:
            if filter_present and daily_data["status"] == "Present":
                return True
            # No need for is_late check here
            if filter_absent and daily_data["status"] == "Absent":
                return True
            if filter_late_in is not None:
                if filter_late_in.lower() == "true" and daily_data["is_late"] is True:
                    return True
                elif (
                    filter_late_in.lower() == "false" and daily_data["is_late"] is False
                ):
                    return True
            if filter_early_out and daily_data["early_out_by"] is not None:
                return True
            if filter_half_day and daily_data["status"] == "Half Day":
                return True
            if filter_on_leave and daily_data["status"] in ["Leave", "Half Day"]:
                return True
        return False

    def process_attendance_efficiently(
        self,
        employees,
        start_date,
        end_date,
        holidays,
        from_date_filter,
        to_date_filter,
        filter_on_present,
        filter_on_absent,
        filter_on_leave,
        permission,
        user,
    ):
        """
        Efficient attendance processing using batch operations and dictionary lookups.
        """
        # Create date range once
        date_range = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)

        # Batch fetch all attendance data for all employees and date range
        attendance_data = AttendanceHistory.objects.filter(
            employee__in=employees, work_date__range=[start_date, end_date]
        ).select_related("employee")

        # Create attendance lookup dictionary for O(1) access
        attendance_lookup = defaultdict(dict)
        for attendance in attendance_data:
            attendance_lookup[attendance.employee.id][attendance.work_date] = {
                "check_in": attendance.check_in,
                "check_out": attendance.check_out,
                "duration": attendance.duration or "00:00",
                "on_time": attendance.on_time,
                "attendance_status": attendance.attendance_status,
            }

        # Batch fetch all leave data for the date range
        leave_data = (
            LeaveRequest.objects.filter(employee__in=employees, status="APPROVED")
            .filter(Q(start_date__lte=end_date) & Q(end_date__gte=start_date))
            .select_related("employee")
        )

        # Create leave lookup dictionary
        leave_lookup = defaultdict(list)
        for leave in leave_data:
            leave_lookup[leave.employee.id].append(
                {
                    "start_date": leave.start_date,
                    "end_date": leave.end_date,
                    "leave_type": leave.leave_type,
                }
            )

        # Create holiday lookup for fast checking
        holiday_lookup = {holiday.date: holiday for holiday in holidays}

        # Process each employee efficiently
        report_data = []
        for employee in employees:
            employee_data = {
                "employee_id": employee.id,
                "full_name": employee.full_name,
                "employee_id_label": employee.employee_id or "",
                "department": employee.department.name if employee.department else "",
                "designation": (
                    employee.designation.name if employee.designation else ""
                ),
                "location": employee.location.name if employee.location else "",
                "office_time": (
                    employee.office_time.name if employee.office_time else ""
                ),
                "total_present": 0,
                "total_late": 0,
                "total_absent": 0,
                "total_leave": 0,
                "working_days": 0,
                "attendance_data": [],
            }

            # Get employee-specific data
            employee_attendance = attendance_lookup.get(employee.id, {})
            employee_leaves = leave_lookup.get(employee.id, [])

            # Process each date for this employee
            for work_date in date_range:
                daily_data = {"date": work_date.strftime("%Y-%m-%d")}

                # Check if it's a holiday using fast lookup
                is_holiday = self._is_holiday_for_employee_fast(
                    work_date, holiday_lookup, employee
                )

                if is_holiday:
                    daily_data.update(
                        {
                            "check_in": None,
                            "check_out": None,
                            "duration": "00:00",
                            "on_time": None,
                            "status": "Holiday",
                        }
                    )
                else:
                    # Check attendance using fast lookup
                    attendance_record = employee_attendance.get(work_date)

                    if attendance_record:
                        daily_data.update(attendance_record)
                        daily_data["status"] = attendance_record["attendance_status"]

                        if attendance_record["attendance_status"] == "Present":
                            employee_data["total_present"] += 1
                            if not attendance_record["on_time"]:
                                employee_data["total_late"] += 1
                    else:
                        # Check for leave using efficient lookup
                        is_on_leave = any(
                            leave["start_date"] <= work_date <= leave["end_date"]
                            for leave in employee_leaves
                        )

                        if is_on_leave:
                            leave_type = next(
                                leave["leave_type"]
                                for leave in employee_leaves
                                if leave["start_date"] <= work_date <= leave["end_date"]
                            )
                            status = "Half Day" if leave_type == "Half Day" else "Leave"
                            employee_data["total_leave"] += 1
                        else:
                            # Check if it's a working day
                            working_days = (
                                employee.office_time.working_days
                                if employee.office_time
                                else []
                            )
                            weekday = (work_date.weekday() + 1) % 7
                            if weekday == 0:
                                weekday = 7

                            if str(weekday) in working_days:
                                status = "Absent"
                                employee_data["total_absent"] += 1
                            else:
                                status = "Weekend"

                        daily_data.update(
                            {
                                "check_in": None,
                                "check_out": None,
                                "duration": "00:00",
                                "on_time": None,
                                "status": status,
                            }
                        )

                    # Count working days
                    if not is_holiday:
                        working_days = (
                            employee.office_time.working_days
                            if employee.office_time
                            else []
                        )
                        weekday = (work_date.weekday() + 1) % 7
                        if weekday == 0:
                            weekday = 7

                        if str(weekday) in working_days:
                            employee_data["working_days"] += 1

                employee_data["attendance_data"].append(daily_data)

            # Apply filters using efficient checking
            if self._employee_meets_criteria_fast(
                employee_data, filter_on_present, filter_on_absent, filter_on_leave
            ):
                report_data.append(employee_data)

        return report_data

    def _employee_meets_criteria_fast(
        self, employee_data, filter_on_present, filter_on_absent, filter_on_leave
    ):
        """Fast filtering using pre-computed totals."""
        if filter_on_present and employee_data["total_present"] > 0:
            return True
        if filter_on_absent and employee_data["total_absent"] > 0:
            return True
        if filter_on_leave and employee_data["total_leave"] > 0:
            return True
        return False

    def _is_holiday_for_employee_fast(self, work_date, holiday_lookup, employee):
        """
        Fast holiday checking using dictionary lookup.
        Note: This method uses holiday.is_applicable_to_employee() for proper
        granular filtering based on branches, designations, departments, etc.
        """
        holiday = holiday_lookup.get(work_date)
        if not holiday:
            return False

        # Use the Holiday model's is_applicable_to_employee method for proper filtering
        return holiday.is_applicable_to_employee(employee)

    def _filter_employees_efficiently(
        self, employees, query_start_date, query_end_date, holidays, filters
    ):
        """
        Efficient filtering of employees using batch operations and optimized logic.
        Maintains the same filtering behavior as the original nested loop.
        """
        filtered_employees_for_report = []

        # Convert holidays to a set for faster lookup
        holiday_dates = set()
        for holiday in holidays:
            current_date = holiday.from_date
            while current_date <= holiday.to_date:
                holiday_dates.add(current_date)
                current_date += timedelta(days=1)

        for employee in employees:
            # Filter attendance history based on resign_terminated_date (same as original)
            if (
                employee.status in ["resigned", "terminated"]
                and employee.resign_terminated_date
            ):
                employee._prefetched_attendance_history = [
                    entry
                    for entry in employee._prefetched_attendance_history
                    if entry.date < employee.resign_terminated_date
                ]
                employee._prefetched_approved_leaves = [
                    leave
                    for leave in employee._prefetched_approved_leaves
                    if leave.start_date < employee.resign_terminated_date
                ]

            # Create lookup dictionaries for faster access
            employee_attendance = {
                entry.date: entry for entry in employee._prefetched_attendance_history
            }
            employee_approved_leaves = employee._prefetched_approved_leaves

            meets_attendance_criteria = False
            current_date = query_start_date

            # Use the same logic as original but with optimized lookups
            while current_date <= query_end_date:
                # Skip dates after resign_terminated_date for resigned/terminated employees
                if (
                    employee.status in ["resigned", "terminated"]
                    and employee.resign_terminated_date
                    and current_date > employee.resign_terminated_date
                ):
                    current_date += timedelta(days=1)
                    continue

                is_working_day = current_date.weekday() in self._get_working_days(
                    employee.office_days
                )
                is_holiday = self._is_holiday_for_employee(
                    current_date, employee, holidays
                )

                # Get the pre-calculated attendance history for this specific day
                daily_record = employee_attendance.get(current_date)

                # Calculate the daily status based on pre-calculated data and day type
                daily_data = self._calculate_daily_attendance_status(
                    current_date,
                    daily_record,
                    employee,
                    is_holiday,
                    is_working_day,
                    employee_approved_leaves,
                )

                if self._day_meets_attendance_filter(daily_data, filters):
                    meets_attendance_criteria = True
                    break
                current_date += timedelta(days=1)

            if not any(filters.values()) or meets_attendance_criteria:
                filtered_employees_for_report.append(employee)

        return filtered_employees_for_report

    def _filter_employees_original(
        self, employees, query_start_date, query_end_date, holidays, filters
    ):
        """
        Original filtering logic as fallback.
        """
        filtered_employees_for_report = []
        for employee in employees:
            # Filter attendance history based on resign_terminated_date
            if (
                employee.status in ["resigned", "terminated"]
                and employee.resign_terminated_date
            ):
                employee._prefetched_attendance_history = [
                    entry
                    for entry in employee._prefetched_attendance_history
                    if entry.date < employee.resign_terminated_date
                ]
                employee._prefetched_approved_leaves = [
                    leave
                    for leave in employee._prefetched_approved_leaves
                    if leave.start_date < employee.resign_terminated_date
                ]

            employee_attendance = {
                entry.date: entry for entry in employee._prefetched_attendance_history
            }
            employee_approved_leaves = employee._prefetched_approved_leaves

            meets_attendance_criteria = False
            current_date = query_start_date

            while current_date <= query_end_date:
                # Skip dates after resign_terminated_date for resigned/terminated employees
                if (
                    employee.status in ["resigned", "terminated"]
                    and employee.resign_terminated_date
                    and current_date > employee.resign_terminated_date
                ):
                    current_date += timedelta(days=1)
                    continue

                is_working_day = current_date.weekday() in self._get_working_days(
                    employee.office_days
                )
                is_holiday = self._is_holiday_for_employee(
                    current_date, employee, holidays
                )

                # Get the pre-calculated attendance history for this specific day
                daily_record = employee_attendance.get(current_date)

                # Calculate the daily status based on pre-calculated data and day type
                daily_data = self._calculate_daily_attendance_status(
                    current_date,
                    daily_record,
                    employee,
                    is_holiday,
                    is_working_day,
                    employee_approved_leaves,
                )

                if self._day_meets_attendance_filter(daily_data, filters):
                    meets_attendance_criteria = True
                    break
                current_date += timedelta(days=1)

            if not any(filters.values()) or meets_attendance_criteria:
                filtered_employees_for_report.append(employee)

        return filtered_employees_for_report


class AttendanceHirtory(generics.ListAPIView):
    serializer_class = AttendanceHistorySerialzier

    def get_queryset(self):
        return AttendanceHistory.objects.select_related("employee").all()


# Attendance create
class AttendanceListCreateView(generics.ListCreateAPIView):
    """
    API View for creating attendance records with:
    - Role-based access (Admin/Supervisor)
    - Granular permissions (add_attendance)
    """

    serializer_class = AttendanceDataSerializer

    def get_queryset(self):
        return AttendanceData.objects.select_related("employee", "employee__user")

    def perform_create(self, serializer):
        request = self.request
        login_type = serializer.validated_data.get(
            "login_type", "Device Login"
        )  # Get login type from validated data
        # Get IP as Device serial number on web login
        device_ip = serializer.validated_data.get("device_serial_number", None)

        employee = None

        if login_type == "Device Login":  # Handle Device Login
            rfid_code = serializer.validated_data.get("rfid_or_machine_code")
            if not rfid_code:
                raise ValidationError("RFID code is required for device login.")

            try:
                employee = Employee.objects.get(rfid_or_machine_code=rfid_code)
                created_by = employee
                serializer.validated_data["created_by"] = employee
            except Employee.DoesNotExist:
                raise ValidationError(f"No employee found with RFID code: {rfid_code}")
        else:  # Web Login
            attendance_employee = serializer.validated_data.get("employee")
            employee = Employee.objects.get(user=attendance_employee.user)
            if not employee:
                raise ValidationError("Employee is required for attendance record.")

            # Skip web login validations for admin users
            is_admin = (
                hasattr(request.user, "role") and request.user.role.name == "Admin"
            ) or request.user.is_superuser

            if not is_admin:
                if not employee.allow_web_login:
                    raise PermissionDenied(
                        "Web login is not allowed for this employee."
                    )

                if employee.allow_any_ip_attendance:
                    AllowedAnyIPLogins.objects.get_or_create(ip_address=device_ip)
                else:
                    # If allow_any_ip_attendance is False, check if IP is in pre-approved ip list
                    if employee.is_ip_restricted:
                        if not device_ip:
                            raise ValidationError(
                                "Device IP not provided in the request."
                            )
                        # Check if IP is pre-approved
                        if not PreApprovedIP.objects.filter(
                            ip_address=device_ip
                        ).exists():
                            raise PermissionDenied(
                                "Device IP is not pre-approved for Web Login."
                            )

            # Notify if someone else is adding other's the attendance
            if employee.user != request.user:
                timestamp = serializer.validated_data.get("timestamp")
                formatted_date = timestamp.strftime("%B %d, %Y at %I:%M %p")
                Notification.objects.create(
                    title=f"""Attendance has been added by {self.request.user} of {employee.user}. Attendance date: {formatted_date}""",
                    type="attendance",
                    receiver=employee.user,
                    remarks=f"Your attendance have been added by {request.user}",
                )
            # Get the employee instance for created_by
            created_by = Employee.objects.get(user=self.request.user)

        # Save the attendance record
        serializer.save(created_by=created_by)


# All Attendance Records (GET)


class AttendanceListView(generics.ListAPIView):
    """
    API View for retrieving all attendance records with:
    - Role-based access (Admin/Supervisor)
    - Filters: employee, attendance_status, date range, keyword search
    """

    serializer_class = AttendanceDataSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        queryset = AttendanceData.objects.select_related("employee", "employee__user")

        # If user has no role assigned but has "view_own_attendance" permission then user will only able to view only own attendance data.
        if not hasattr(user, "role"):
            if user.has_perm("view_own_attendance"):
                queryset = queryset.filter(employee__user=user)
            else:
                raise PermissionDenied(
                    "You do not have permission to view attendance records"
                )
        # If user role is "Admin", user will able to view all attendance data.
        elif user.role.name == "Admin":
            pass  # No filtering needed
        elif user.role.name == "Supervisor":
            # If user role is "Supervisor" and has "view_attendancedata" permission then user will able to view all attendance data.
            if user.has_perm("attendance.view_attendancedata"):
                pass  # No filtering needed
            # If user role is "Supervisor" and has "view_subordinate_attendance" permission then user will able to view all subordinate employee's attendance data along with his own data.
            elif user.has_perm("attendance.view_subordinate_attendance"):
                queryset = queryset.filter(
                    Q(employee__supervisor=user) | Q(employee__user=user)
                ).distinct()
            # If user role is "Supervisor" and has "view_own_attendance" permission then user will able to view only own attendance data.
            elif user.has_perm("attendance.view_own_attendance"):
                queryset = queryset.filter(employee__user=user)
            else:
                raise PermissionDenied(
                    "You do not have permission to view attendance records."
                )
        else:
            raise PermissionDenied(
                "You do not have permission to view attendance records."
            )

        # Apply filters
        queryset = self._apply_filters(queryset)

        return queryset.order_by("-created_at")

    def _apply_filters(self, queryset):
        """
        Apply filters based on query parameters:
        - employee: Filter by employee ID
        - attendance_status: Filter by attendance status (Present, Absent, etc.)
        - start_date: Filter attendance from this date
        - end_date: Filter attendance until this date
        - keyword: Search by employee name, ID, RFID, or device serial number
        """
        # Filter by employee ID
        employee_id = self.request.query_params.get("employee")
        if employee_id:
            queryset = queryset.filter(employee__employee_id=employee_id)

        # Filter by attendance status - FIXED
        attendance_status = self.request.query_params.get("attendance_status")
        if attendance_status:
            # Filter directly on AttendanceData.attendance_status field
            queryset = queryset.filter(attendance_status__iexact=attendance_status)

        # Filter by date range
        start_date_str = self.request.query_params.get("start_date")
        end_date_str = self.request.query_params.get("end_date")

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                queryset = queryset.filter(timestamp__date__gte=start_date)
            except ValueError:
                raise serializers.ValidationError(
                    {"start_date": "Invalid date format. Use YYYY-MM-DD."}
                )

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                queryset = queryset.filter(timestamp__date__lte=end_date)
            except ValueError:
                raise serializers.ValidationError(
                    {"end_date": "Invalid date format. Use YYYY-MM-DD."}
                )

        # Keyword search (employee name, ID, RFID, or device serial number)
        keyword = self.request.query_params.get("keyword")
        if keyword:
            queryset = queryset.filter(
                Q(employee__employee_name__icontains=keyword)
                | Q(employee__employee_id__icontains=keyword)
                | Q(employee__rfid_or_machine_code__icontains=keyword)
                | Q(device_serial_number__icontains=keyword)
            )

        return queryset


class EmployeeAttendanceListView(generics.ListAPIView):
    """
    API View for retrieving attendance records of an employee with:
    - Role-based access (Admin/Supervisor/Employee)
    - Granular permissions (view_own/view_all/view_subordinate)
    """

    # serializer_class = AttendanceDataSerializer
    serializer_class = EmployeeAttendanceTimeStampSerializer
    # permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        employee_id = self.kwargs.get("employee_id")
        employee = get_object_or_404(Employee, employee_id=employee_id)
        all_roles = [role.name for role in Role.objects.all()]

        if not hasattr(user, "role"):
            raise PermissionDenied(
                "You do not have permission to view this attendance data."
            )

        if user.role.name == "Admin":
            return AttendanceData.objects.filter(employee=employee).select_related(
                "employee", "employee__user"
            )

        if user.role.name in all_roles:
            # If user role is "Supervisor" and has "view_attendancedata" permission then user will able to view all attendance data.
            if user.has_perm("attendance.view_attendancedata"):
                return AttendanceData.objects.filter(employee=employee).select_related(
                    "employee", "employee__user"
                )

            # If user role is "Supervisor" and has "view_subordinate_attendance" permission then user will able to view all subordinate employee's attendance data along with his own data.
            if user.has_perm("attendance.view_subordinate_attendance"):
                if not employee.user == user:
                    if not employee.supervisor.filter(email=user):
                        raise PermissionDenied(
                            "You are not authorized to view this employee's attendance data."
                        )
                return AttendanceData.objects.filter(employee=employee).select_related(
                    "employee", "employee__user"
                )

            # If user role is "Supervisor" or "Employee" and has "view_own_attendance" permission then user will able to view only own attendance data.
            if user.has_perm("attendance.view_own_attendance"):
                loged_in_employee = get_object_or_404(Employee, user=user)
                if not str(employee_id) == str(loged_in_employee.employee_id):
                    raise PermissionDenied(
                        "You are not authorized to view this employee's attendance data."
                    )
                return AttendanceData.objects.filter(
                    employee__user=user
                ).select_related("employee", "employee__user")
        raise PermissionDenied(
            "You do not have permission to view this attendance data."
        )

    def list(self, request, *args, **kwargs):
        employee = get_object_or_404(
            Employee, employee_id=self.kwargs.get("employee_id")
        )
        date_str = request.query_params.get("date")

        # Parse and validate date
        if date_str:
            try:
                query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                raise serializers.ValidationError(
                    {"date": "Invalid date format. Use YYYY-MM-DD."}
                )
            if query_date > timezone.localdate():
                raise serializers.ValidationError(
                    {"date": "Date cannot be in the future."}
                )
        else:
            raise serializers.ValidationError({"date": "Date parameter is required."})

        # Fetch AttendanceData for the employee for the specified date (plus next day for overnight shifts)
        attendance_data = (
            self.get_queryset()
            .filter(
                timestamp__date__range=[query_date, query_date + timedelta(days=1)],
                timestamp__isnull=False,
            )
            .order_by("timestamp")
        )

        # Prepare data for the specified date
        daily_attendance = []
        employee_shift = employee.office_time

        daily_data = {"date": query_date, "timestamps": []}

        if employee_shift:
            is_overnight = (
                employee_shift.office_end_time < employee_shift.office_start_time
            )
            check_in_start_dt = timezone.make_aware(
                datetime.combine(query_date, employee_shift.check_in_start_time),
                timezone.get_current_timezone(),
            )
            check_out_end_dt = timezone.make_aware(
                datetime.combine(query_date, employee_shift.check_out_end_time),
                timezone.get_current_timezone(),
            )
            if is_overnight:
                check_out_end_dt += timedelta(days=1)

            # Collect timestamps within the shift window
            relevant_timestamps = []
            for record in attendance_data:
                ts = record.timestamp
                if ts and check_in_start_dt <= ts <= check_out_end_dt:
                    # For overnight shifts, ensure timestamps on next day belong to current shift
                    if is_overnight and ts.date() == query_date + timedelta(days=1):
                        prev_day = query_date - timedelta(days=1)
                        prev_check_out_end_dt = timezone.make_aware(
                            datetime.combine(
                                prev_day, employee_shift.check_out_end_time
                            ),
                            timezone.get_current_timezone(),
                        ) + timedelta(days=1)
                        if ts <= prev_check_out_end_dt:
                            continue  # Skip: belongs to previous day's shift
                    relevant_timestamps.append(
                        {
                            "timestamp": ts,
                            "local_ip_address": record.local_ip_address or "",
                            "location_name": record.location_name or "",
                            "device_serial_number": record.device_serial_number or "",
                        }
                    )

            daily_data["timestamps"] = sorted(
                relevant_timestamps, key=lambda x: x["timestamp"]
            )

        daily_attendance.append(daily_data)

        serializer = self.get_serializer(daily_attendance, many=True)
        return Response(serializer.data)


# Single Attendance Record by PK (GET, PUT, DELETE)


class AttendanceRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    API View for retrieving, updating, and deleting attendance records with:
    - Role-based access (Admin/Supervisor/Employee)
    - Granular permissions (view_own/view_all/view_subordinate)
    - Optimized queries (select_related + Q objects)
    """

    queryset = AttendanceData.objects.select_related("employee", "employee__user")
    serializer_class = AttendanceDataSerializer
    permission_classes = [IsAuthenticated]

    def check_permissions(self, request):
        """
        Enforces permission rules:
        - Admins: Full access
        - Supervisors: Needs specific permissions for update/delete
        - Regular users: Can only act on their own data with explicit permissions
        """
        super().check_permissions(request)
        user = request.user

        # Update permissions
        if self.request.method in ["PUT", "PATCH"]:
            if not (
                user.is_superuser or user.has_perm("attendance.change_attendancedata")
            ):
                raise PermissionDenied(
                    "You don't have permission to update attendance records"
                )

        # Delete permissions
        elif self.request.method == "DELETE":
            if not (
                user.is_superuser or user.has_perm("attendance.delete_attendancedata")
            ):
                raise PermissionDenied(
                    "You don't have permission to delete attendance records"
                )

    def get_queryset(self):
        """
        Filters data visibility based on:
        - view_attendancedata: See ALL records (global permission)
        - view_subordinate_attendance: See own + subordinate records (supervisors)
        - view_own_attendance: See only personal records
        - Admin: No filtering
        """
        user = self.request.user

        # Admins see everything
        if user.is_superuser:
            return self.queryset.all()

        # Global view permission
        if user.has_perm("attendance.view_attendancedata"):
            return self.queryset.all()

        # Supervisor with subordinate access
        if (
            getattr(user, "role", None)
            and user.role.name == "Supervisor"
            and user.has_perm("attendance.view_subordinate_attendance")
        ):
            queryset = self.queryset.filter(
                # Subordinates (supervisor is ManyToMany to User)
                Q(employee__supervisor=user)
                | Q(employee__user=user)  # Own records
            ).distinct()
            return queryset

        # Personal view permission
        if user.has_perm("attendance.view_own_attendance"):
            return self.queryset.filter(employee__user=user)

        # Default deny
        return self.queryset.none()


class AttendanceAdjustmentCreateView(generics.ListCreateAPIView):
    """
    API View for creating attendance adjustment records.
    Optimized with select_related to eliminate N+1 queries.
    """

    serializer_class = AttendanceAdjustmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        employee = get_object_or_404(Employee, user=user)
        # Optimize with select_related for employee relation
        return AttendanceAdjustmentRequest.objects.select_related(
            "employee", "employee__user"
        ).filter(employee=employee)

    def create(self, request, *args, **kwargs):
        """
        Custom create method to handle:
        - Cut-off date restrictions
        - Employee validation
        """
        # Check if the user has permission to create attendance adjustments
        if not request.user.has_perm("attendance.add_attendanceadjustmentrequest"):
            raise PermissionDenied(
                "You do not have permission to create attendance adjustment requests."
            )

        # Check cut-off restriction before allowing creation
        today = timezone.now().date()
        adjustment_date_str = request.data.get("date")
        adjustment_date = timezone.datetime.strptime(
            adjustment_date_str, "%Y-%m-%d"
        ).date()

        # Cut-off date is applicable for everyone except superusers
        if request.user and not request.user.is_superuser:
            cutoff = CutOff.objects.all().first()
            if not cutoff:
                raise PermissionDenied("Cut-off date is not set for this month.")

            cut_off_start = (cutoff.cut_off - relativedelta(months=1)) + timedelta(
                days=1
            )
            cut_off_end = cutoff.cut_off

            if not (cut_off_end >= adjustment_date >= cut_off_start):
                raise PermissionDenied(
                    f"The cut-off for {cut_off_start} to {cut_off_end} has passed. "
                    f"You can no longer submit adjustments for that period."
                )

        return super().create(request, *args, **kwargs)


class AttendanceAdjustmentRetrieveUpdateDestroyView(
    generics.RetrieveUpdateDestroyAPIView
):
    """
    API View for retrieving, updating, and deleting attendance adjustment records
    - Admin users can access and update all records
    - Regular users can only access their own records
    """

    serializer_class = AttendanceAdjustmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Admin users can access all attendance adjustment requests
        if user.is_superuser or (hasattr(user, "role") and user.role.name == "Admin"):
            return AttendanceAdjustmentRequest.objects.all()

        # Regular users can only access their own records
        employee = get_object_or_404(Employee, user=user)
        return AttendanceAdjustmentRequest.objects.filter(employee=employee)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # Allow superuser to update anytime
        if not request.user.is_superuser:
            if instance.status != "pending":
                raise PermissionDenied(
                    "You can only update attendance adjustment requests while status is 'pending'."
                )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        # Allow superuser to update anytime
        if not request.user.is_superuser:
            if instance.status != "pending":
                raise PermissionDenied(
                    "You can only update attendance adjustment requests while status is 'pending'."
                )
        return super().partial_update(request, *args, **kwargs)


class AttendanceAdjustmentApprovalListView(generics.ListAPIView):
    """
    API View for listing attendance adjustment approvals
    Optimized with select_related to eliminate N+1 queries
    """

    serializer_class = AttendanceAdjustmentApprovalSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # Optimize with select_related to fetch related objects in a single query
        # This prevents N+1 queries.
        queryset = (
            AttendanceAdjustmentApproval.objects.select_related(
                "adjustment_request",
                "adjustment_request__employee",
                "adjustment_request__employee__user",
                "adjustment_request__employee__department",
                "approver",
            )
            .all()
            .order_by("-created_at")
        )

        approver_id = self.request.query_params.get("approver_id")
        request_id = self.request.query_params.get("request_id")
        user_id = self.request.query_params.get("user_id")

        if approver_id:
            queryset = queryset.filter(approver=approver_id)

        if request_id:
            queryset = queryset.filter(adjustment_request__id=request_id)

        if user_id:
            queryset = queryset.filter(adjustment_request__employee__user=user_id)

        employee_name = self.request.query_params.get("employee_name")
        if employee_name:
            queryset = queryset.filter(
                adjustment_request__employee__employee_name__icontains=employee_name
            )

        department = self.request.query_params.get("department")
        if department:
            queryset = queryset.filter(
                adjustment_request__employee__department__name__icontains=department
            )

        adjustment_request_name = self.request.query_params.get(
            "adjustment_request_name"
        )
        if adjustment_request_name:
            queryset = queryset.filter(
                adjustment_request__adjustment_type__iexact=adjustment_request_name
            )

        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status__iexact=status)

        # Date range filtering on adjustment request date
        start_date_str = self.request.query_params.get("start_date")
        end_date_str = self.request.query_params.get("end_date")
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                queryset = queryset.filter(adjustment_request__date__gte=start_date)
            except ValueError:
                raise serializers.ValidationError(
                    {"start_date": "Invalid date format. Use YYYY-MM-DD."}
                )
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                queryset = queryset.filter(adjustment_request__date__lte=end_date)
            except ValueError:
                raise serializers.ValidationError(
                    {"end_date": "Invalid date format. Use YYYY-MM-DD."}
                )

        return queryset


class AttendanceAdjustmentApprovalView(RetrieveUpdateAPIView):
    queryset = AttendanceAdjustmentApproval.objects.select_related(
        "adjustment_request__employee"
    )
    serializer_class = AttendanceAdjustmentApprovalUpdateSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch"]  # Only allow GET and PATCH

    @transaction.atomic
    def perform_update(self, serializer):
        """
        Custom update method to handle:
        - User permissions
        - Status validation
        - Cut-off date restrictions
        """
        # Check if the user has permission to approve attendance adjustments
        if not self.request.user.has_perm(
            "attendance.change_attendanceadjustmentapproval"
        ):
            raise PermissionDenied(
                "You do not have permission to approve attendance adjustments."
            )

        # Allow admin users to bypass cut-off restrictions
        if self.request.user.is_superuser:
            instance = self.get_object()
            new_status = serializer.validated_data.get("status")

            if new_status not in ["pending", "approved", "rejected"]:
                raise ValidationError(
                    "Status must be either 'pending', 'approved', or 'rejected'"
                )

            if instance.status == new_status:
                raise ValidationError(f"Status is already {new_status}")

            serializer.save(approver=self.request.user, action_date=timezone.now())
            return

        today = timezone.now().date()
        approval_instance = self.get_object()
        adjustment_request = approval_instance.adjustment_request
        adjustment_date = adjustment_request.date
        new_status = serializer.validated_data.get("status")

        # Get current cut-off information
        current_cut_off = CutOff.objects.latest("created_at")
        current_cut_off_end = current_cut_off.cut_off
        current_cut_off_start = (
            current_cut_off_end - relativedelta(months=1)
        ) + timedelta(days=1)

        # Check if adjustment date falls in the CURRENT cut-off period
        is_in_current_period = (
            current_cut_off_start <= adjustment_date <= current_cut_off_end
        )

        # Check if today's date has PASSED the cut-off end date
        cut_off_has_passed = today > current_cut_off_end

        # Apply cut-off restrictions for non-superusers
        if is_in_current_period and cut_off_has_passed:
            # Current period but cut-off date passed - only allow rejection
            if new_status != "rejected":
                raise PermissionDenied(
                    f"The cut-off date for this period ({current_cut_off_end}) has passed. "
                    f"You can only reject adjustment requests from this period, not approve them."
                )
        elif not is_in_current_period:
            # Adjustment is from a previous period - only allow rejection
            if new_status != "rejected":
                raise PermissionDenied(
                    f"The adjustment date ({adjustment_date}) is from a previous cut-off period. "
                    f"You can only reject this request, not approve it."
                )

        # Additional business logic validation
        if new_status not in ["approved", "rejected"]:
            raise ValidationError("Status must be either 'approved' or 'rejected'")

        instance = self.get_object()
        if instance.status == new_status:
            raise ValidationError(f"Status is already {new_status}")

        # Update approval record
        serializer.save(approver=self.request.user, action_date=timezone.now())


class DeviceLastAttendanceView(APIView):
    """
    API View for getting the last attendance record for a device
    """

    def get(self, request, *args, **kwargs):
        device_serial_number = request.query_params.get("device_serial_number")

        if not device_serial_number:
            raise ValidationError("Device serial number is required")

        try:
            last_attendance = (
                AttendanceData.objects.filter(device_serial_number=device_serial_number)
                .order_by("-timestamp")
                .first()
            )
            serializer = AttendanceDataSerializer(last_attendance)

            if not last_attendance:
                return Response([], status=status.HTTP_200_OK)

            # Convert timestamp to local timezone (Asia/Dhaka)
            local_timestamp = localtime(last_attendance.timestamp)

            # Format in 12-hour format with AM/PM
            formatted_time = local_timestamp.strftime("%I:%M:%S %p, %Y-%m-%d")

            return Response([{"timestamp": formatted_time}], status=status.HTTP_200_OK)

        except AttendanceData.DoesNotExist:
            return Response(
                {"detail": "No attendance record found for this device."},
                status=status.HTTP_404_NOT_FOUND,
            )


class CutOffDateListCreateView(generics.ListCreateAPIView):
    """
    API View for listing and creating cut-off dates
    """

    serializer_class = CutOffSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CutOff.objects.all().order_by("-cut_off")

    def perform_create(self, serializer):
        """
        Validates and saves a new cut-off date.
        - Ensures the user has permission to create cut-off dates.
        - Ensures only one cut-off date can be created per month.
        """
        # Validate if the user is allowed to create cut-off dates
        if not self.request.user.has_perm("attendance.add_cutoff"):
            raise PermissionDenied(
                "You do not have permission to create cut-off dates."
            )

        # Ensure only one cut-off date per month
        today = timezone.now().date()
        if CutOff.objects.filter(
            cut_off__year=today.year, cut_off__month=today.month
        ).exists():
            raise ValidationError("Cut-off date for this month already exists.")
        serializer.save()


class CutOffDateRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    API View for retrieving, updating, and deleting a specific cut-off date
    """

    queryset = CutOff.objects.all()
    serializer_class = CutOffSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        """
        Validates and updates a cut-off date.
        - Ensures the user has permission to change cut-off dates.
        - Ensures only one cut-off date can be updated per month.
        """
        if not self.request.user.has_perm("attendance.change_cutoff"):
            raise PermissionDenied("You do not have permission to perform this action.")

        # Ensure only one cut-off date per month
        today = timezone.now().date()
        if (
            CutOff.objects.filter(cut_off__year=today.year, cut_off__month=today.month)
            .exclude(id=self.get_object().id)
            .exists()
        ):
            raise ValidationError("Cut-off date for this month already exists.")

        serializer.save()


# ----------- Auto Cut Off date Create Update Viewset -------------------


class CutOffDateAutoCreateUpdateView(generics.ListAPIView):
    """
    API View for automatically creating or updating cut-off dates.
    """

    serializer_class = CutOffSerializer

    def get_queryset(self):
        CutOff.update_cutoff()
        return CutOff.objects.all().order_by("-cut_off")


# Custom API view to return expected shift check-in/check-out times for one employee/date, accounting for half-day leaves and overnight shifts.
class SingleDayAttendanceAPIView(APIView):
    """Return expected shift check-in/check-out times for one employee/date.

    Query params:
    - employee: user id
    - date: YYYY-MM-DD

    Response example:
    {
        "id": 1,
        "employee_name": "Tamim Islam",
        "check_in": "09:00 am",
        "check_out": "06:00 pm"
    }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        emp_id = request.query_params.get("employee")
        date_str = request.query_params.get("date")
        if not emp_id or not date_str:
            raise ValidationError({"detail": "employee and date query params required"})

        try:
            shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError({"date": "Invalid date format, expected YYYY-MM-DD"})

        # fetch employee and related shift in one query
        try:
            employee = Employee.objects.select_related("user", "office_time").get(
                user__id=emp_id
            )
        except Employee.DoesNotExist:
            raise ValidationError({"employee": "Employee not found"})

        if not employee.office_time:
            raise ValidationError({"detail": "No shift assigned for employee"})

        # compute base shift datetimes
        shift = employee.office_time
        from .signals import (
            _get_half_day_adjusted_start_time,
            _get_half_day_adjusted_end_time,
        )

        # determine adjusted times if half-day leave present
        adjusted_start = _get_half_day_adjusted_start_time(employee, shift_date, shift)
        adjusted_end = _get_half_day_adjusted_end_time(employee, shift_date, shift)

        if adjusted_start:
            check_in_dt = adjusted_start
        else:
            check_in_dt = timezone.make_aware(
                datetime.combine(shift_date, shift.office_start_time),
                timezone.get_current_timezone(),
            )
        if adjusted_end:
            check_out_dt = adjusted_end
        else:
            check_out_dt = timezone.make_aware(
                datetime.combine(shift_date, shift.office_end_time),
                timezone.get_current_timezone(),
            )

        def fmt(dt):
            return dt.strftime("%I:%M %p").lower()

        data = {
            "id": employee.pk,
            "employee_name": employee.employee_name,
            "check_in": fmt(check_in_dt),
            "check_out": fmt(check_out_dt),
        }
        return Response(data)
