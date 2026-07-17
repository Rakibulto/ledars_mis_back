from django.urls import path
from .views import (
    AttendanceAdjustmentApprovalListView,
    AttendanceAdjustmentRetrieveUpdateDestroyView,
    AttendanceListView,
    AttendanceListCreateView,
    AttendanceRetrieveUpdateDestroyView,
    CutOffDateAutoCreateUpdateView,
    EmployeeAttendanceListView,
    AttendanceReportViewSet,
    AttendanceAdjustmentCreateView,
    AttendanceAdjustmentApprovalView,
    DeviceLastAttendanceView,
    CutOffDateListCreateView,
    CutOffDateRetrieveUpdateDestroyView,
    SingleDayAttendanceAPIView,
)

from .dashboard import HRDashboardView, IndividualEmployeeView, SupervisorDashboardView

attendance_viewset = AttendanceReportViewSet.as_view({"get": "list"})
attendance_viewset_sngle_employee = AttendanceReportViewSet.as_view({"get": "retrieve"})

urlpatterns = [
    path("attendance/", AttendanceListView.as_view(), name="all-attendance"),
    path("attendance-report/", attendance_viewset, name="attendance-report"),
    path(
        "attendance-report/<int:pk>/",
        attendance_viewset_sngle_employee,
        name="attendance-report-detail",
    ),
    path(
        "attendance-create/",
        AttendanceListCreateView.as_view(),
        name="attendance-create",
    ),
    path(
        "attendance/<str:employee_id>/",
        EmployeeAttendanceListView.as_view(),
        name="employee-attendance",
    ),
    path(
        "attendance-update-delete/<int:pk>/",
        AttendanceRetrieveUpdateDestroyView.as_view(),
        name="attendance-detail-update",
    ),
    # Attendance Adjustment api
    path(
        "attendance-adjustment-create/",
        AttendanceAdjustmentCreateView.as_view(),
        name="attendance-adjustment-create",
    ),
    path(
        "attendance-adjustment-update/<int:pk>/",
        AttendanceAdjustmentRetrieveUpdateDestroyView.as_view(),
        name="attendance-adjustment-update",
    ),
    # Attendance Adjustment Approval api
    path(
        "attendance_approval_list/",
        AttendanceAdjustmentApprovalListView.as_view(),
        name="attendance-approval-list",
    ),
    # User (?approver_id=user_id) params to filter approvals by approver
    # User (?request_id=leave_request_id) params to filter all supervisor who approved a leave request
    path(
        "attendance_approval_update/<int:pk>/",
        AttendanceAdjustmentApprovalView.as_view(),
        name="attendance-approval-detail",
    ),
    # Last attendance of a device
    path(
        "device_last_attendance/",
        DeviceLastAttendanceView.as_view(),
        name="device-last-attendance",
    ),
    ## Attendance Dashboard API {Comprehensive dashboard endpoint (all analytics in one call)}
    path("dashboard/", HRDashboardView.as_view(), name="hr_dashboard"),
    # Individual employee data
    path(
        "dashboard/employee/<str:employee_id>/",
        IndividualEmployeeView.as_view(),
        name="individual_employee",
    ),
    # Supervisor dashboard data
    path(
        "dashboard/supervisor/<str:supervisor_id>/",
        SupervisorDashboardView.as_view(),
        name="supervisor_dashboard",
    ),
    # CutOff Date API
    path(
        "cutoff-dates/",
        CutOffDateListCreateView.as_view(),
        name="cutoff-date-list-create",
    ),
    path(
        "cutoff-dates/<int:pk>/",
        CutOffDateRetrieveUpdateDestroyView.as_view(),
        name="cutoff-date-detail-update",
    ),
    # Auto Cut Off date Create Update Viewset
    path(
        "auto-cutoff-dates/",
        CutOffDateAutoCreateUpdateView.as_view(),
        name="auto_cutoff_dates",
    ),
    # single-day shift times endpoint
    path(
        "attendance-for-adjustment/",
        SingleDayAttendanceAPIView.as_view(),
        name="attendance-for-adjustment",
    ),
]
