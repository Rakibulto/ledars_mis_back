from rest_framework import serializers
from authentication.models import User
from leave.models import LeaveGroup
from leave.serializers import (
    LeavePolicyEmployeeSerializer,
    LeaveGroupEmployeeSerializer,
)
from .models import (
    Employee,
    Salary,
    User,
    Department,
    Designation,
    Branch,
    Grade,
    Shift,
    EmergencyContact,
    Nominee,
)
from django.contrib.auth.models import Permission
from authentication.serializers import PermissionSerializer
from shift.serializers import ShiftSerializer


class EmployeePermissionSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    role = serializers.StringRelatedField()

    class Meta:
        model = User
        fields = ["id", "email", "username", "role", "permissions"]

    def get_permissions(self, obj):
        # Get both direct permissions and group permissions
        permissions = obj.user_permissions.all() | Permission.objects.filter(
            group__user=obj
        )
        permissions = permissions.distinct()
        return PermissionSerializer(permissions, many=True).data


class SimplifiedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "role"]


class DepartmentSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)

    class Meta:
        model = Department
        fields = ["id", "name", "created_at", "updated_at"]


class DesignationSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    created_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)

    class Meta:
        model = Designation
        fields = [
            "id",
            "name",
            "department",
            "department_name",
            "created_at",
            "updated_at",
        ]


class EmployeesSimpleSerializer(serializers.ModelSerializer):
    user = SimplifiedUserSerializer()
    designation = DesignationSerializer()

    class Meta:
        model = Employee
        fields = [
            "id",
            "user",
            "employee_name",
            "employee_id",
            "profile_picture",
            "signature",
            "designation",
            "joining_date",
            "confirmation_date",
            "location",
        ]


class BranchSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)

    class Meta:
        model = Branch
        fields = ["id", "name", "address", "created_at", "updated_at"]


class GradeSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)

    class Meta:
        model = Grade
        fields = ["id", "name", "created_at", "updated_at"]


class EmergencyContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyContact
        fields = "__all__"


class NomineeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nominee
        fields = "__all__"


class EmployeeSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ["id", "employee_name", "employee_id"]


class SalaryListSerializer(serializers.ModelSerializer):
    creator = serializers.StringRelatedField(read_only=True)
    employee = EmployeeSimpleSerializer(read_only=True)

    class Meta:
        model = Salary
        fields = [
            "id",
            "creator",
            "employee",
            "basic",
            "house_rent",
            "conveyance",
            "medical",
            "gross_salary",
            "festival_bonus",
            "absence_deduction",
            "is_late_during_holiday",
            "late_count_threshold",
            "late_deduction",
            "holiday_compensation",
            "weekday_compensation",
            "performance_bonus",
            "tax_percentage",
            "tax_amount_threshold",
            "created_at",
            "updated_at",
        ]


class SalaryCreateSerializer(serializers.ModelSerializer):
    creator = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Salary
        fields = [
            "id",
            "creator",
            "employee",
            "basic",
            "house_rent",
            "conveyance",
            "medical",
            "gross_salary",
            "festival_bonus",
            "is_late_during_holiday",
            "absence_deduction",
            "late_count_threshold",
            "late_deduction",
            "holiday_compensation",
            "weekday_compensation",
            "performance_bonus",
            "tax_percentage",
            "tax_amount_threshold",
            "created_at",
            "updated_at",
        ]


class EmployeeListSerializer(serializers.ModelSerializer):
    user = SimplifiedUserSerializer()
    department = DepartmentSerializer()
    designation = DesignationSerializer()
    grade = GradeSerializer()
    location = BranchSerializer()
    office_time = ShiftSerializer()
    supervisor = SimplifiedUserSerializer(many=True)
    leave_group = LeaveGroupEmployeeSerializer(read_only=True)
    employment_type = LeaveGroupEmployeeSerializer(read_only=True)
    emergency_contact = EmergencyContactSerializer(many=True, required=False)
    nominee = NomineeSerializer(many=True, required=False)

    class Meta:
        model = Employee
        fields = [
            "user",
            "department",
            "designation",
            "grade",
            "location",
            "office_time",
            "supervisor",
            "leave_group",
            "employment_type",
            "employee_id",
            "employee_name",
            "joining_date",
            "probation_period",
            "probation_period_time",
            "confirmation_date",
            "office_days",
            "official_mobile_number",
            "salary",
            "rfid_or_machine_code",
            "status",
            "resign_terminated_date",
            "resign_terminated_reason",
            "present_address",
            "permanent_address",
            "marital_status",
            "religion",
            "blood_group",
            "gender",
            "personal_mobile_number",
            "personal_email_id",
            "last_education",
            "educational_institute",
            "last_job_experience",
            "profile_picture",
            "signature",
            "date_of_birth",
            "bank_name",
            "bank_account_number",
            "bank_branch",
            "allow_web_login",
            "is_ip_restricted",
            "allow_any_ip_attendance",
            "emergency_contact",
            "nominee",
        ]


class EmployeeSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    department = DepartmentSerializer(read_only=True)
    designation = DesignationSerializer(read_only=True)
    location = BranchSerializer(read_only=True)
    office_time = ShiftSerializer(read_only=True)

    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
        required=False,
        allow_null=True,
    )
    designation_id = serializers.PrimaryKeyRelatedField(
        queryset=Designation.objects.all(),
        source="designation",
        write_only=True,
        required=False,
        allow_null=True,
    )
    location_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        source="location",
        write_only=True,
        required=False,
        allow_null=True,
    )
    grade_id = serializers.PrimaryKeyRelatedField(
        queryset=Grade.objects.all(),
        source="grade",
        write_only=True,
        required=False,
        allow_null=True,
    )
    employment_type = serializers.PrimaryKeyRelatedField(
        queryset=LeaveGroup.objects.all(), required=False, allow_null=True
    )
    office_time_id = serializers.PrimaryKeyRelatedField(
        queryset=Shift.objects.all(),
        source="office_time",
        write_only=True,
        required=False,
        allow_null=True,
    )
    supervisor_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="supervisor",
        many=True,
        write_only=True,
        required=False,
    )
    leave_group_id = serializers.PrimaryKeyRelatedField(
        queryset=LeaveGroup.objects.all(),
        source="leave_group",
        write_only=True,
        required=False,
        allow_null=True,
    )
    emergency_contact = EmergencyContactSerializer(many=True, required=False)
    nominee = NomineeSerializer(many=True, required=False)
    employee_perms = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = "__all__"
        extra_kwargs = {
            "employee_id": {
                "read_only": False
            },  # Allow employee_id to be set during creation
            # 'user': {'read_only': True}, # This is now handled by the nested User serializer
        }

    def get_employee_perms(self, obj):
        return EmployeePermissionSerializer(obj.user).data

    def create(self, validated_data):
        emergency_contact_data = validated_data.pop("emergency_contact", [])
        nominee_data = validated_data.pop("nominee", [])
        supervisor_ids = validated_data.pop("supervisor", [])

        # Create the Employee instance
        employee = Employee.objects.create(**validated_data)

        # Handle ManyToMany for EmergencyContact
        for contact_data in emergency_contact_data:
            contact, created = EmergencyContact.objects.get_or_create(**contact_data)
            employee.emergency_contact.add(contact)

        # Create nominees
        for nominee_data in nominee_data:
            nominee = Nominee.objects.create(**nominee_data)
            employee.nominee.add(nominee)

        # Handle ManyToMany for Supervisor
        if supervisor_ids:
            employee.supervisor.set(supervisor_ids)

        employee.update_status()
        return employee

    def update(self, instance, validated_data):
        # Pop ManyToMany and related fields only if they are provided in the payload
        emergency_contact_data = validated_data.pop("emergency_contact", None)
        nominee_data = validated_data.pop("nominee", None)
        supervisor_ids = validated_data.pop("supervisor", None)

        # Update scalar fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update ManyToMany for EmergencyContact only if provided
        if emergency_contact_data is not None:
            instance.emergency_contact.clear()
            for contact_data in emergency_contact_data:
                contact, created = EmergencyContact.objects.get_or_create(
                    **contact_data
                )
                instance.emergency_contact.add(contact)

        # Update ManyToMany for Nominee only if provided
        if nominee_data is not None:
            instance.nominee.clear()
            for nominee_data_item in nominee_data:
                nominee, created = Nominee.objects.get_or_create(**nominee_data_item)
                instance.nominee.add(nominee)

        # Update ManyToMany for Supervisor only if provided
        if supervisor_ids is not None:
            instance.supervisor.set(supervisor_ids)

        instance.update_status()
        return instance


class EmployeeDetailSerializer(serializers.ModelSerializer):
    user = EmployeePermissionSerializer()
    department = DepartmentSerializer()
    designation = DesignationSerializer()
    location = BranchSerializer()
    grade = GradeSerializer()
    office_time = ShiftSerializer()
    supervisor = SimplifiedUserSerializer(many=True)
    leave_group = LeaveGroupEmployeeSerializer(read_only=True)
    employment_type = LeaveGroupEmployeeSerializer(read_only=True)
    leave_policies = serializers.SerializerMethodField()
    emergency_contact = EmergencyContactSerializer(many=True, required=False)
    nominee = NomineeSerializer(many=True, required=False)

    class Meta:
        model = Employee
        fields = "__all__"

    def get_leave_policies(self, obj):
        """Return leave policies associated with the employee's leave group."""
        if obj.leave_group:
            leave_policies = obj.leave_group.leave_policies.all()
            return LeavePolicyEmployeeSerializer(leave_policies, many=True).data
        return []
