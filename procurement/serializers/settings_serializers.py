from rest_framework import serializers
from django.db import transaction
from authentication.models import User, Role
from employee.models import Department, Employee
from ..models.settings_models import (
    ApprovalMatrix,
    EmailTemplate,
    ProcurementRole,
    ProcurementUserRole,
    NotificationSetting,
    UserManagement,
)


class ApprovalMatrixSerializer(serializers.ModelSerializer):
    approver_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)

    # Write: list of employee PKs; Read: list of {id, employee_name, designation}
    approver_ids = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="approvers",
        many=True,
        required=False,
    )
    approvers_info = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalMatrix
        fields = [
            "id",
            "type",
            "module",
            "approval_level",
            "min_amount",
            "max_amount",
            "approver_role",
            "approver",
            "approver_name",
            "approver_ids",
            "approvers_info",
            "department",
            "department_name",
            "approval_mode",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_approver_name(self, obj):
        if obj.approver:
            return obj.approver.employee_name
        return None

    def get_approvers_info(self, obj):
        return [
            {
                "id": emp.pk,
                "employee_name": emp.employee_name,
                "designation": emp.designation.name if emp.designation else None,
                "email": emp.user.email if emp.user else None,
            }
            for emp in obj.approvers.select_related("designation", "user").all()
        ]

    def create(self, validated_data):
        approvers = validated_data.pop("approvers", [])
        instance = super().create(validated_data)
        if approvers:
            instance.approvers.set(approvers)
        return instance

    def update(self, instance, validated_data):
        approvers = validated_data.pop("approvers", None)
        instance = super().update(instance, validated_data)
        if approvers is not None:
            instance.approvers.set(approvers)
        return instance


class EmailTemplateSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = EmailTemplate
        fields = [
            "id",
            "name",
            "module",
            "subject",
            "body",
            "is_active",
            "variables",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]


class ProcurementRoleSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(
        source="user_assignments.count", read_only=True
    )

    class Meta:
        model = ProcurementRole
        fields = [
            "id",
            "name",
            "description",
            "can_create_requisition",
            "can_approve_requisition",
            "can_create_rfq",
            "can_manage_vendors",
            "can_create_comparative",
            "can_approve_comparative",
            "can_create_award",
            "can_create_work_order",
            "can_approve_work_order",
            "can_create_grn",
            "can_create_payment",
            "can_approve_payment",
            "can_process_treasury",
            "can_view_reports",
            "can_manage_settings",
            "is_active",
            "user_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ProcurementUserRoleSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = ProcurementUserRole
        fields = ["id", "user", "username", "role", "role_name"]


class NotificationSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSetting
        fields = [
            "id",
            "module",
            "event_name",
            "email_enabled",
            "in_app_enabled",
            "sms_enabled",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class UserManagementSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    re_password = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    auth_user_id = serializers.IntegerField(source="user.id", read_only=True)
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), write_only=True, required=False, allow_null=True
    )
    role_name = serializers.CharField(source="role.name", read_only=True)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = UserManagement
        fields = [
            "id",
            "auth_user_id",
            "username",
            "email",
            "password",
            "re_password",
            "name",
            "role",
            "role_name",
            "department",
            "department_name",
            "phone",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "role_name", "department_name"]

    def validate(self, attrs):
        password = attrs.get("password")
        re_password = attrs.get("re_password")

        if self.instance is None:
            if not password or not re_password:
                raise serializers.ValidationError(
                    {"password": "Password and re_password are required for creation."}
                )
        elif password or re_password:
            if password != re_password:
                raise serializers.ValidationError(
                    {"re_password": "Passwords do not match."}
                )

        if "username" in attrs:
            username = attrs["username"]
            username_qs = User.objects.filter(username=username)
            if self.instance and self.instance.user_id:
                username_qs = username_qs.exclude(pk=self.instance.user_id)
            if username_qs.exists():
                raise serializers.ValidationError(
                    {"username": "A user with this username already exists."}
                )

        if "email" in attrs:
            email = attrs["email"]
            email_qs = User.objects.filter(email=email)
            if self.instance and self.instance.user_id:
                email_qs = email_qs.exclude(pk=self.instance.user_id)
            if email_qs.exists():
                raise serializers.ValidationError(
                    {"email": "A user with this email already exists."}
                )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.pop("re_password")

        username = validated_data["username"]
        email = validated_data["email"]
        status = validated_data.get("status", "active")

        # Create auth user directly via Django ORM (same as /api/auth/users/ POST)
        auth_user = User.objects.create_user(
            email=email,
            username=username,
            password=password,
            is_active=(status == "active"),
            role=validated_data.get("role"),
            department=validated_data.get("department"),
        )

        # Create the UserManagement profile linked to the auth user
        user_management = UserManagement.objects.create(
            user=auth_user,
            username=username,
            email=email,
            name=validated_data.get("name"),
            role=validated_data.get("role"),
            department=validated_data.get("department"),
            phone=validated_data.get("phone"),
            status=status,
        )
        return user_management

    @transaction.atomic
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        validated_data.pop("re_password", None)

        # Update cached fields on auth user if changed
        auth_user = instance.user
        if auth_user:
            new_username = validated_data.get("username", instance.username)
            new_email = validated_data.get("email", instance.email)
            if new_username != instance.username:
                auth_user.username = new_username
            if new_email != instance.email:
                auth_user.email = new_email

            if "status" in validated_data:
                auth_user.is_active = validated_data.get("status") == "active"

            if "role" in validated_data:
                auth_user.role = validated_data.get("role")

            if "department" in validated_data:
                auth_user.department = validated_data.get("department")

            if password:
                auth_user.set_password(password)

            auth_user.save()

        return super().update(instance, validated_data)


class SimpleUserSerializer(serializers.ModelSerializer):
    role_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "role_name",
            "department_name",
        ]

    def get_role_name(self, obj):
        user_management_profile = getattr(obj, "user_management_profile", None)
        if user_management_profile and getattr(user_management_profile, "role", None):
            return user_management_profile.role.name

        if getattr(obj, "role", None) and getattr(obj.role, "name", None):
            return obj.role.name

        return None

    def get_department_name(self, obj):
        user_management_profile = getattr(obj, "user_management_profile", None)
        if user_management_profile and getattr(
            user_management_profile, "department", None
        ):
            return user_management_profile.department.name

        if getattr(obj, "department", None) and getattr(obj.department, "name", None):
            return obj.department.name

        return None

    def get_full_name(self, obj):
        user_management_profile = getattr(obj, "user_management_profile", None)
        if user_management_profile and getattr(user_management_profile, "name", None):
            return user_management_profile.name

        employee = getattr(obj, "employee", None)
        if employee and getattr(employee, "employee_name", None):
            return employee.employee_name

        full_name = (getattr(obj, "get_full_name", lambda: None)() or "").strip()
        return full_name or obj.username or obj.email


class ApproverUserSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "full_name", "role_name"]

    def get_full_name(self, obj):
        employee = getattr(obj, "employee", None)
        if employee and getattr(employee, "employee_name", None):
            return employee.employee_name

        user_management_profile = getattr(obj, "user_management_profile", None)
        if user_management_profile and getattr(user_management_profile, "name", None):
            return user_management_profile.name

        full_name = (getattr(obj, "get_full_name", lambda: None)() or "").strip()
        return full_name or obj.username or obj.email
