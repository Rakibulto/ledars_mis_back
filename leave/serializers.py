from rest_framework import serializers
import calendar
from leave.models import (
    LeavePolicy,
    LeaveGroup,
    LeaveRequest,
    LeaveApproval,
    SupervisorLevel,
    LeaveReset,
    SpecialLeavePolicy,
)
from .utils import LeaveBalanceCalculator
from .models import CompensatoryLeaveBalance, CompensatoryLeaveEarned
from django.utils import timezone


class LeaveGroupEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveGroup
        fields = ["id", "name", "description", "created_at", "updated_at"]


class LeavePolicyEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeavePolicy
        fields = [
            "id",
            "leave_type_name",
            "total_leave_days",
            "gender",
            "apply_before_days",
            "effective_from",
            "max_days_per_request",
            "min_days_per_request",
            "allow_half_day",
            "count_holidays",
            "count_weekends",
            "is_active",
            "created_at",
            "updated_at",
        ]


class LeaveGroupSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveGroup
        fields = ["id", "name"]


class LeavePolicySerializer(serializers.ModelSerializer):
    leave_groups = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=LeaveGroup.objects.all(),
    )
    leave_groups_detail = LeaveGroupSimpleSerializer(
        source="leave_groups", many=True, read_only=True
    )
    created_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)

    class Meta:
        model = LeavePolicy
        fields = [
            "id",
            "leave_groups",
            "leave_groups_detail",
            "leave_type_name",
            "total_leave_days",
            "gender",
            "apply_before_days",
            "effective_from",
            "max_days_per_request",
            "min_days_per_request",
            "allow_half_day",
            "count_holidays",
            "count_weekends",
            "is_active",
            "created_at",
            "updated_at",
        ]


class LeaveRequestSerializer(serializers.ModelSerializer):
    creator = serializers.StringRelatedField(read_only=True)
    leave_policy_name = serializers.CharField(
        source="leave_policy.leave_type_name", read_only=True
    )
    employee_name = serializers.CharField(
        source="employee.employee_name", read_only=True
    )
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    department_name = serializers.CharField(
        source="employee.department.name", read_only=True
    )
    branch_name = serializers.CharField(source="employee.location.name", read_only=True)
    profile_picture = serializers.ImageField(
        source="employee.profile_picture", read_only=True
    )
    present_address = serializers.CharField(
        source="employee.present_address", read_only=True
    )
    signature = serializers.ImageField(
        source="employee.signature", read_only=True
    )
    requested_days = serializers.SerializerMethodField()
    status_tracking_date = serializers.DateTimeField(
        format="%d-%m-%Y, %H:%M:%S", read_only=True
    )
    updated_by = serializers.StringRelatedField(read_only=True)
    created_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "creator",
            "employee",
            "employee_name",
            "employee_id",
            "profile_picture",
            "department_name",
            "branch_name",
            "leave_policy",
            "leave_policy_name",
            "start_date",
            "end_date",
            "requested_days",
            "is_half_day",
            "half_day_period",
            "reason",
            "status",
            "status_tracking_date",
            "updated_by",
            "created_at",
            "updated_at",
            "present_address",
            "signature",
            "admin_check_sign",
            "req_unit_head_sign",
            "req_excutive_sign",
            "joining_excutive_sign",
            "joining_employee_sign",
            "actual_joining_date",
            "as_per_leave_joining_date",
        ]

    def get_requested_days(self, obj):
        """Calculate requested_days for the leave request"""
        return LeaveBalanceCalculator.calculate_leave_days(
            start_date=obj.start_date,
            end_date=obj.end_date,
            employee=obj.employee,
            policy=obj.leave_policy,
            is_half_day=obj.is_half_day,
        )


class SupervisorLevelSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source="employee.employee_name", read_only=True
    )
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    supervisor_name = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)

    class Meta:
        model = SupervisorLevel
        fields = [
            "id",
            "employee",
            "employee_id",
            "employee_name",
            "supervisor",
            "supervisor_name",
            "level",
            "created_at",
            "updated_at",
        ]

    def get_supervisor_name(self, obj):
        # Check if supervisor exists
        if not obj.supervisor:
            return None
        # Assumes supervisor has a related employee object
        if hasattr(obj.supervisor, "employee"):
            return getattr(
                obj.supervisor.employee, "employee_name", obj.supervisor.username
            )
        return obj.supervisor.username


class LeaveApprovalSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source="leave_request.employee.employee_name", read_only=True
    )
    employee_id = serializers.StringRelatedField(
        source="leave_request.employee.employee_id", read_only=True
    )
    department_name = serializers.CharField(
        source="leave_request.employee.department.name", read_only=True
    )
    branch_name = serializers.CharField(
        source="leave_request.employee.location.name", read_only=True
    )
    leave_from = serializers.DateField(
        source="leave_request.start_date", format="%d-%m-%Y", read_only=True
    )
    leave_to = serializers.DateField(
        source="leave_request.end_date", format="%d-%m-%Y", read_only=True
    )
    leave_request_name = serializers.CharField(
        source="leave_request.leave_policy.leave_type_name", read_only=True
    )
    leave_policy = serializers.IntegerField(
        source="leave_request.leave_policy.id", read_only=True
    )
    reason = serializers.CharField(source="leave_request.reason", read_only=True)
    approver_name = serializers.CharField(
        source="approver.employee.employee_name", read_only=True
    )
    requested_days = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)

    class Meta:
        model = LeaveApproval
        fields = [
            "id",
            "leave_request",
            "leave_request_name",
            "leave_policy",
            "reason",
            "leave_from",
            "leave_to",
            "requested_days",
            "employee_id",
            "employee_name",
            "department_name",
            "branch_name",
            "approver",
            "approver_name",
            "level",
            "status",
            "comments",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "leave_request",
            "employee_id",
            "employee_name",
            "department_name",
            "branch_name",
            "approver",
            "level",
            "approver_name",
            "leave_policy",
            "reason",
            "created_at",
            "updated_at",
        ]

    def get_requested_days(self, obj):
        """Calculate requested_days for the leave request"""
        leave_request = obj.leave_request
        return LeaveBalanceCalculator.calculate_leave_days(
            start_date=obj.leave_request.start_date,
            end_date=obj.leave_request.end_date,
            employee=leave_request.employee,
            policy=leave_request.leave_policy,
            is_half_day=leave_request.is_half_day,
        )


class LeaveResetSerializer(serializers.ModelSerializer):
    from_date = serializers.SerializerMethodField()
    to_date = serializers.SerializerMethodField()
    start_month_name = serializers.SerializerMethodField()
    end_month_name = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)

    class Meta:
        model = LeaveReset
        fields = [
            "id",
            "start_month",
            "start_month_name",
            "start_day",
            "end_month",
            "end_month_name",
            "end_day",
            "from_date",
            "to_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_from_date(self, obj):
        year = obj.created_at.year if obj.created_at else None
        if obj.start_month and obj.start_day and year:
            return f"{year}-{obj.start_month:02d}-{obj.start_day:02d}"
        return None

    def get_to_date(self, obj):
        year = obj.created_at.year if obj.created_at else None
        if obj.end_month and obj.end_day and year:
            end_year = year
            if obj.start_month and obj.end_month < obj.start_month:
                end_year += 1
            return f"{end_year}-{obj.end_month:02d}-{obj.end_day:02d}"
        return None

    def get_start_month_name(self, obj):
        if obj.start_month:
            return calendar.month_name[obj.start_month]
        return None

    def get_end_month_name(self, obj):
        if obj.end_month:
            return calendar.month_name[obj.end_month]
        return None


class CompensatoryLeaveBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source="employee.employee_name", read_only=True
    )
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)

    class Meta:
        model = CompensatoryLeaveBalance
        fields = [
            "employee",
            "employee_name",
            "employee_id",
            "total_earned",
            "total_used",
            "current_balance",
            "last_updated",
        ]
        read_only_fields = [
            "total_earned",
            "total_used",
            "current_balance",
            "last_updated",
        ]


class CompensatoryLeaveEarnedSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source="employee.employee_name", read_only=True
    )

    class Meta:
        model = CompensatoryLeaveEarned
        fields = [
            "id",
            "employee",
            "employee_name",
            "earned_date",
            "expires_on",
            "is_used",
            "used_date",
            "is_expired",
            "created_at",
        ]
        read_only_fields = ["is_used", "used_date", "is_expired", "created_at"]


class SpecialLeavePolicySerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.username", read_only=True)
    leave_policy_name = serializers.CharField(
        source="leave_policy.leave_type_name", read_only=True
    )
    available_policies_detail = LeavePolicyEmployeeSerializer(
        source="available_policies", many=True, read_only=True
    )
    created_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)

    class Meta:
        model = SpecialLeavePolicy
        fields = [
            "id",
            "creator",
            "creator_name",
            "leave_policy",
            "leave_policy_name",
            "available_policies",
            "available_policies_detail",
            "created_at",
            "updated_at",
        ]
