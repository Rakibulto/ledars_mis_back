from django.contrib.auth.models import Permission
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from djoser.serializers import UserCreateSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from authentication.models import User, Role
from employee.models import Department
from .models import CompanyInfo, User, Role, PreApprovedIP, Module, ModulePermission, PermissionGroup


# Dynamic Company Name Name and Logo Serializer
class CompanyInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyInfo
        fields = "__all__"


# Serializer for Custom User Model with Role-Based Permissions
class CustomUserSerializer(UserCreateSerializer):
    user_permissions_list = serializers.SerializerMethodField()
    user_role = serializers.PrimaryKeyRelatedField(
        source="role", queryset=Role.objects.all(), write_only=True, required=False
    )
    role = serializers.StringRelatedField(read_only=True)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    department_name = serializers.CharField(source="department.name", read_only=True)
    re_password = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    profile_picture = serializers.ImageField(
        source="employee.profile_picture", read_only=True
    )
    signature = serializers.ImageField(
        source="employee.signature", read_only=True
    )

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = list(UserCreateSerializer.Meta.fields) + [
            "user_permissions_list",
            "is_active",
            "is_staff",
            "is_superuser",
            "role",
            "user_role",
            "department",
            "department_name",
            "employee_id",
            "profile_picture",
            "signature",
            "re_password",
        ]
        extra_kwargs = {
            "password": {"write_only": True, "required": False},
            "re_password": {"write_only": True, "required": False},
        }

    def get_user_permissions_list(self, obj):
        # Combine direct permissions and permissions from groups
        permissions = obj.user_permissions.all() | Permission.objects.filter(
            group__user=obj
        )
        permissions = permissions.distinct()
        serializer = PermissionSerializer(permissions, many=True)
        return serializer.data

    def validate(self, attrs):
        attrs = super().validate(attrs)
        password = attrs.get("password")
        re_password = attrs.get("re_password")

        if self.instance is None:
            if not password or not re_password:
                raise serializers.ValidationError(
                    {"password": "Password and re_password are required for creation."}
                )
        elif password and re_password:
            if password != re_password:
                raise serializers.ValidationError(
                    {"re_password": "Passwords do not match."}
                )
        return attrs

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        validated_data.pop("re_password", None)

        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance


class PermissionSerializer(serializers.ModelSerializer):
    app_label = serializers.CharField(source="content_type.app_label", read_only=True)
    model = serializers.CharField(source="content_type.model", read_only=True)

    class Meta:
        model = Permission
        fields = ["id", "name", "codename", "app_label", "model"]


class PreApprovedIPSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreApprovedIP
        fields = "__all__"


class UserRoleSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%d-%m-%Y, %H:%M:%S", read_only=True)

    class Meta:
        model = Role
        fields = ["id", "name", "created_at", "updated_at"]


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ["id", "name", "code", "created_at", "updated_at"]


class ModulePermissionSerializer(serializers.ModelSerializer):
    module_name = serializers.CharField(source="module.name", read_only=True)
    module_code = serializers.CharField(source="module.code", read_only=True)

    class Meta:
        model = ModulePermission
        fields = [
            "id",
            "module",
            "module_name",
            "module_code",
            "can_create",
            "can_update",
            "can_delete",
            "can_add",
            "can_view",
            "created_at",
            "updated_at",
        ]


class PermissionGroupSerializer(serializers.ModelSerializer):
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    permissions = PermissionSerializer(many=True, read_only=True)
    module_keys = serializers.SerializerMethodField()

    class Meta:
        model = PermissionGroup
        fields = [
            "id",
            "name",
            "description",
            "permissions",
            "permission_ids",
            "module_keys",
            "created_at",
            "updated_at",
        ]

    def get_module_keys(self, obj):
        return sorted(
            {
                perm.content_type.app_label
                for perm in obj.permissions.select_related("content_type").all()
            }
        )

    def create(self, validated_data):
        permission_ids = validated_data.pop("permission_ids", [])
        group = PermissionGroup.objects.create(**validated_data)
        if permission_ids:
            group.permissions.set(Permission.objects.filter(id__in=permission_ids))
        return group

    def update(self, instance, validated_data):
        permission_ids = validated_data.pop("permission_ids", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if permission_ids is not None:
            instance.permissions.set(Permission.objects.filter(id__in=permission_ids))
        return instance


class UserSerializer(serializers.ModelSerializer):
    module_permissions = ModulePermissionSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = "__all__"


class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class VendorTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer that only allows users whose role is 'Vendor'.
    All other users receive a 401 Unauthorized response.
    """

    def validate(self, attrs):
        data = super().validate(attrs)

        user = self.user
        role_name = user.role.name if user.role else None

        if role_name is None or role_name.lower() != "vendor":
            raise AuthenticationFailed(
                detail="Access denied. Only vendor accounts are allowed to login here.",
                code="not_vendor",
            )

        return data
