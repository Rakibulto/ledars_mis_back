# Test
from rest_framework import serializers
from attendance.models import AttendanceData


class AttendanceDataSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source="employee.user.get_full_name", read_only=True
    )
    employee_email = serializers.CharField(source="employee.user.email", read_only=True)

    class Meta:
        model = AttendanceData
        fields = [
            "id",
            "employee",
            "employee_name",
            "employee_email",
            "rfid_or_machine_code",
            "local_ip_address",
            "device_serial_number",
            "login_type",
            "timestamp",
            "attendance_status",
            "remarks",
            "created_at",
            "updated_at",
            "created_by",
        ]
        read_only_fields = [
            "attendance_status",  # calculated in model.save()
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        employee = attrs.get("employee")
        rfid = attrs.get("rfid_or_machine_code")
        if not employee and not rfid:
            raise serializers.ValidationError(
                "Either employee or rfid_or_machine_code must be provided."
            )
        return attrs
