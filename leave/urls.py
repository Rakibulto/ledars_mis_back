from rest_framework.routers import DefaultRouter
from django.urls import include, path, re_path
from .views import (
    CompensatoryLeaveViewSet,
    EmployeeLeaveBalanceAPI,
    EmployeeLeavePolicyListAPIView,
    EmployeeLeaveRequestListAPIView,
    EmployeeSupervisorsAPIView,
    LeaveApprovalAPIView,
    LeaveApprovalRetrieveUpdateDestroyAPIView,
    LeaveGroupListCreateAPIView,
    LeaveGroupRetrieveUpdateDestroyAPIView,
    LeavePolicyListCreateAPIView,
    LeavePolicyRetrieveUpdateDestroyAPIView,
    LeaveRequestListCreateAPIView,
    LeaveRequestRetrieveUpdateDestroyAPIView,
    LeaveResetPeriodRetrieveUpdateDestroyAPIView,
    LeaveResetPeriodViewSet,
    SpecialLeavePolicyListCreateAPIView,
    SpecialLeavePolicyRetrieveUpdateDestroyAPIView,
    SupervisorLevelListCreateAPIView,
    SupervisorLevelRetrieveUpdateDestroyAPIView,
)


router = DefaultRouter()
router.register(r'compensatory-leave', CompensatoryLeaveViewSet, basename='compensatory-leave')

urlpatterns = [
    path('', include(router.urls)),
    # Leave Groups URLs
    path('leave-groups/', LeaveGroupListCreateAPIView.as_view(), name='leave-groups-list-create'),
    path('leave-groups/<int:pk>/', LeaveGroupRetrieveUpdateDestroyAPIView.as_view(), name='leave-groups-retrieve-update-destroy'),
    # Leave Policies URLs
    path('employees/<str:employee_id>/leave-policies/', EmployeeLeavePolicyListAPIView.as_view(), name='employee-leave-policies'),
    path('leave-policies/', LeavePolicyListCreateAPIView.as_view(), name='leave-policies-list-create'),
    path('leave-policies/<int:pk>/', LeavePolicyRetrieveUpdateDestroyAPIView.as_view(), name='leave-policies-retrieve-update-destroy'),
    # Leave Requests URLs
    path('employees/<str:employee_id>/leave-requests/', EmployeeLeaveRequestListAPIView.as_view(), name='employee-leave-policies'),
    # To fetch subordinate leave requests,use (include_subordinates=true) params in the API.
    path('leave-requests/', LeaveRequestListCreateAPIView.as_view(), name='leave-requests-list-create'),
    path('leave-requests/<int:pk>/', LeaveRequestRetrieveUpdateDestroyAPIView.as_view(), name='leave-requests-retrieve-update-destroy'),
    # Supervisor Levels URLs
    path('employee/<str:employee_id>/supervisors/', EmployeeSupervisorsAPIView.as_view(), name='employee-supervisors'), # Endpoint to get supervisors for an employee
    path('supervisor-level-list-create/', SupervisorLevelListCreateAPIView.as_view(), name='supervisor-level-list-create'),
    path('supervisor-level-list-create/<int:pk>/', SupervisorLevelRetrieveUpdateDestroyAPIView.as_view(), name='supervisor-level-retrieve-update-destroy'),
    # Leave Approval URLs
    path('leave-approval/', LeaveApprovalAPIView.as_view(), name='leave-approval'), 
    # User (?approver_id=user_id) params to filter approvals by approver
    # User (?leave_request_id=leave_request_id) params to filter all supervisor who approved a leave request
    path('leave-approval/<int:pk>/', LeaveApprovalRetrieveUpdateDestroyAPIView.as_view(), name='leave-requests-retrieve-update-destroy'),
    
    # Leave Balance URLs
    path('leave-balance/', EmployeeLeaveBalanceAPI.as_view(), name='all_employee_leave_balance'),
    # Use this params to filter with date ranges (?from_date=2024-01-01&to_date=2025-12-31)
    
    path('leave-balance/<str:employee_id>/', EmployeeLeaveBalanceAPI.as_view(), name='employee_leave_balance'),
    # Use this params to filter subordinate leave balance (?http://127.0.0.1:8000/api/leave-balance/<supervisor_id>/?include_subordinates=true)
    
    # Leave Reset Periods URLs
    path('leave-reset-periods/', LeaveResetPeriodViewSet.as_view(), name='leave-reset-periods-list-create'),
    path('leave-reset-periods/<int:pk>', LeaveResetPeriodRetrieveUpdateDestroyAPIView.as_view(), name='leave-reset-periods-retrieve-update-destroy'),
    
    # Special Leave Policies URLs
    path('special-leave-policies/', SpecialLeavePolicyListCreateAPIView.as_view(), name='special-leave-policies-list-create'),
    path('special-leave-policies/<int:pk>/', SpecialLeavePolicyRetrieveUpdateDestroyAPIView.as_view(), name='special-leave-policies-retrieve-update-destroy'),
]
