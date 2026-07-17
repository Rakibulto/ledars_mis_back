from .models import (
    AttendanceData,
    AttendanceAdjustmentRequest,
    AttendanceAdjustmentApproval,
    AttendanceHistory,
    CutOff,
)
from rest_framework import serializers
from employee.models import Department, Branch


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["name"]


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["name"]


class AttendanceTimestampSerializer(serializers.Serializer):
    """
    Serializer for individual timestamps within a day's attendance.
    """

    timestamp = serializers.DateTimeField(format="%d-%m-%Y %H:%M:%S")
    local_ip_address = serializers.CharField(allow_blank=True, allow_null=True)
    location_name = serializers.CharField(allow_blank=True, allow_null=True)
    device_serial_number = serializers.CharField()


# Daily Attendance Serializer
class DailyAttendanceSerializer(serializers.Serializer):
    """
    Serializer for the attendance data aggregated by day for an employee.
    Calculates in/out times, late/early out, etc.
    """

    date = serializers.DateField(format="%d-%m-%Y")
    is_late = serializers.BooleanField(allow_null=True)
    # timestamps = AttendanceTimestampSerializer(many=True)
    check_in = serializers.DateTimeField(format="%d-%m-%Y %H:%M:%S", allow_null=True)
    check_out = serializers.DateTimeField(format="%d-%m-%Y %H:%M:%S", allow_null=True)
    late_by = serializers.CharField(allow_null=True, help_text="Duration late in")
    early_out_by = serializers.CharField(
        allow_null=True, help_text="Duration early out"
    )
    # actual_work_duration = serializers.CharField(allow_null=True, help_text="Actual time spent")
    # expected_work_duration = serializers.CharField(allow_null=True, help_text="Expected time as per duty_start/end_time")
    status = serializers.CharField(
        help_text="e.g., Present, Late, Early Out, Half Day, Absent"
    )
    remarks = serializers.CharField(allow_null=True)


# Employee Attendance Report Serializer
class EmployeeAttendanceReportSerializer(serializers.Serializer):
    """
    Main serializer for the employee attendance report.
    Processes pre-fetched attendance data for efficiency.
    Includes all days in the date range, marking absent days with status='Absent'.
    """

    employee_info = serializers.SerializerMethodField()
    attendance = serializers.SerializerMethodField()

    class Meta:
        pass  # Custom Serializer, not a ModelSerializer

    def get_employee_info(self, obj):
        return {
            "id": obj.pk,
            "employeeId": obj.employee_id,
            "employee_name": obj.employee_name,
            "email": obj.user.email if obj.user else None,
            "profile_picture": obj.profile_picture.url if obj.profile_picture else None,
            "department": obj.department.name if obj.department else None,
            "designation": obj.designation.name if obj.designation else None,
            "rfid_no": obj.rfid_or_machine_code if obj.rfid_or_machine_code else None,
            "employment_type": (
                obj.employment_type.name if obj.employment_type else None
            ),
            "branch": obj.location.name if obj.location else None,
            "status": obj.status,
        }

    def get_attendance(self, obj):
        """
        Calculates daily attendance using pre-fetched AttendanceData.
        Includes all days in the date range, with absent days marked as status='Absent'.
        'obj' is an Employee instance; data is in context['attendance_data'].
        """
        request = self.context.get("request")
        attendance_data = self.context.get("attendance_data", {})
        query_start_date = self.context.get("query_start_date")
        query_end_date = self.context.get("query_end_date")

        if not request or not query_start_date or not query_end_date:
            return []

        filters = {
            "filter_present": self.context.get("filter_present"),
            "filter_absent": self.context.get("filter_absent"),
            "filter_late_in": self.context.get("filter_late_in"),
            "filter_early_out": self.context.get("filter_early_out"),
            "filter_half_day": self.context.get("filter_half_day"),
            "filter_on_leave": request.query_params.get("on_leave", "false").lower()
            == "true",
        }
        holidays = self.context.get("holidays", [])

        # The 'view' instance is passed through the serializer context from the ViewSet
        view = self.context.get("view")
        if view and hasattr(view, "get_attendance_report_for_employee"):
            return view.get_attendance_report_for_employee(
                obj,
                attendance_data,
                query_start_date,
                query_end_date,
                filters,
                holidays,
            )
        return []


class AttendanceHistorySerialzier(serializers.ModelSerializer):
    class Meta:
        model = AttendanceHistory
        fields = "__all__"


class AttendanceDataSerializer(serializers.ModelSerializer):
    """
    Serializer for AttendanceData model.
    """

    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.CharField(
        source="employee.user.username", read_only=True
    )
    department = serializers.CharField(
        source="employee.department.name", read_only=True
    )
    branch = serializers.CharField(source="employee.location.name", read_only=True)
    rfid = serializers.CharField(source="employee.rfid_or_machine_code", read_only=True)
    login_type = serializers.CharField(required=False, default="Device Login")
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = AttendanceData
        fields = [
            "id",
            "employee",
            "employee_id",
            "employee_name",
            "department",
            "branch",
            "rfid",
            "login_type",
            "attendance_status",
            "rfid_or_machine_code",
            "local_ip_address",
            "latitude",
            "longitude",
            "location_accuracy",
            "location_name",
            "device_serial_number",
            "timestamp",
            "created_by",
            "created_at",
            "updated_at",
        ]


class EmployeeAttendanceTimeStampSerializer(serializers.ModelSerializer):
    """
    Serializer for day wise attendance data
    """

    date = serializers.DateField(format="%Y-%m-%d")
    timestamps = AttendanceTimestampSerializer(many=True)

    class Meta:
        model = AttendanceData
        fields = ["date", "timestamps"]


class AttendanceAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceAdjustmentRequest
        fields = [
            "id",
            "employee",
            "date",
            "check_type",
            "actual_duty_start_time",
            "actual_arival_time",
            "adjustment_type",
            "remarks",
            "status",
            "created_at",
        ]


class AttendanceAdjustmentApprovalSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(
        source="adjustment_request.employee.user.id", read_only=True
    )
    employee_name = serializers.CharField(
        source="adjustment_request.employee.employee_name", read_only=True
    )
    employee_id = serializers.CharField(
        source="adjustment_request.employee.employee_id", read_only=True
    )
    department = serializers.CharField(
        source="adjustment_request.employee.department.name", read_only=True
    )
    actual_duty_start_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    actual_arrival_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    requested_arrival_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    check_type = serializers.CharField(
        source="adjustment_request.check_type", read_only=True
    )
    action_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    adjustment_request_name = serializers.CharField(
        source="adjustment_request.adjustment_type", read_only=True
    )
    approver_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceAdjustmentApproval
        fields = [
            "id",
            "user_id",
            "employee_id",
            "employee_name",
            "department",
            "adjustment_request",
            "adjustment_request_name",
            "approver",
            "approver_name",
            "check_type",
            "actual_duty_start_time",
            "actual_arrival_time",
            "requested_arrival_time",
            "status",
            "comments",
            "remarks",
            "action_date",
            "created_at",
        ]

    def get_approver_name(self, obj):
        if obj.approver:
            return obj.approver.username
        return None


class AttendanceAdjustmentApprovalUpdateSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source="adjustment_request.employee.user.get_full_name", read_only=True
    )
    employee_id = serializers.CharField(
        source="adjustment_request.employee.employee_id", read_only=True
    )
    employee = serializers.PrimaryKeyRelatedField(
        source="adjustment_request.employee", read_only=True
    )
    adjustment_request_name = serializers.CharField(
        source="adjustment_request.adjustment_type", read_only=True
    )

    class Meta:
        model = AttendanceAdjustmentApproval
        fields = [
            "id",
            "employee",
            "employee_id",
            "employee_name",
            "adjustment_request",
            "adjustment_request_name",
            "remarks",
            "status",
            "comments",
            "actual_duty_start_time",
            "actual_arrival_time",
            "requested_arrival_time",
            "action_date",
        ]
        extra_kwargs = {"status": {"required": True}, "comments": {"required": False}}

    def validate_status(self, value):
        if value not in ["approved", "rejected"]:
            raise serializers.ValidationError(
                "Status must be either 'approved' or 'rejected'"
            )
        return value


class AttendanceHistoryCountSerializer(serializers.ModelSerializer):
    count = serializers.IntegerField()

    class Meta:
        model = AttendanceHistory
        fields = ["status", "count"]


class AttendanceAdjustmentCountSerializer(serializers.ModelSerializer):
    count = serializers.IntegerField()

    class Meta:
        model = AttendanceAdjustmentRequest
        fields = ["status", "count"]


class CutOffSerializer(serializers.ModelSerializer):
    """
    Serializer for CutOff model.
    """

    class Meta:
        model = CutOff
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


# Custom serializer for the single-day attendance endpoint, which returns expected check-in/out times for a given employee/date, adjusted for half-day leaves and overnight shifts.
class SingleDayShiftSerializer(serializers.Serializer):
    """Return scheduled check-in/out times for a single employee/date.

    Values are adjusted for approved half-day leaves when applicable.
    """

    id = serializers.IntegerField()
    employee_name = serializers.CharField()
    check_in = serializers.CharField()
    check_out = serializers.CharField()
