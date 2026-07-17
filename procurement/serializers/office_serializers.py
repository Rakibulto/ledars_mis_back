# serializers.py

from django.db.models import Count
from rest_framework import serializers

from authentication.models import User
from inventory.models import Warehouse as InventoryWarehouse
from inventory.serializers.warehouse import (
    WarehouseSerializer as InventoryWarehouseSerializer,
)

from ..models.office_models import OfficeManagement, OfficeStaff, Warehouse


# =========================
# User Serializer
# =========================
class SimpleUserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "role"]

    def get_role(self, obj):
        if not obj.role:
            return None
        return obj.role.name


# =========================
# Warehouse Serializer
# =========================
class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = [
            "id",
            "warehouse_id",
            "name",
            "capacity",
            "address",
            "status",
            "office",
        ]
        read_only_fields = ["warehouse_id"]


# =========================
# Office Staff Serializer
# =========================
class OfficeStaffSerializer(serializers.ModelSerializer):
    office = serializers.PrimaryKeyRelatedField(
        queryset=OfficeManagement.objects.all(),
        allow_null=True,
        required=False,
    )
    office_details = serializers.SerializerMethodField(read_only=True)
    user = SimpleUserSerializer(many=True, read_only=True)
    user_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        write_only=True,
        source="user",
        required=False,
    )

    class Meta:
        model = OfficeStaff
        fields = [
            "id",
            "office",
            "office_details",
            "user",
            "user_ids",
            "status",
        ]

    def get_office_details(self, obj):
        if obj.office:
            return {
                "id": obj.office.id,
                "office_id": obj.office.office_id,
                "name": obj.office.name,
                "code": obj.office.code,
            }
        return None


# =========================
# =========================
# Nested Warehouse Serializer
# =========================
class WarehouseNestedSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="warehouse_id")
    address = serializers.CharField()

    class Meta:
        model = Warehouse
        fields = ["id", "name", "capacity", "address", "status"]


# =========================
# Office Management Serializer
# =========================
class OfficeManagementSerializer(serializers.ModelSerializer):
    staff = serializers.SerializerMethodField(read_only=True)
    warehouses = serializers.SerializerMethodField(read_only=True)
    headOfOffice = serializers.CharField(
        source="head_of_office", allow_null=True, allow_blank=True, required=False
    )
    office_contactPerson = serializers.PrimaryKeyRelatedField(
        source="office_contact_person",
        queryset=User.objects.all(),
        allow_null=True,
        required=False,
    )
    office_contactPerson_details = serializers.SerializerMethodField(read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)
    staffCount = serializers.SerializerMethodField(read_only=True)
    budgetAllocation = serializers.DecimalField(
        source="budget_allocation", max_digits=15, decimal_places=2,
        allow_null=True, required=False
    )
    budgetUtilized = serializers.DecimalField(
        source="budget_utilized", max_digits=15, decimal_places=2,
        allow_null=True, required=False
    )

    class Meta:
        model = OfficeManagement
        fields = [
            "id",
            "office_id",
            "name",
            "code",
            "district",
            "division",
            "address",
            "phone",
            "email",
            "type",
            "status",
            "headOfOffice",
            "office_contactPerson",
            "office_contactPerson_details",
            "staffCount",
            "budgetAllocation",
            "budgetUtilized",
            "staff",
            "warehouses",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "office_id",
            "staffCount",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_staff(self, obj):
        users = []
        seen_ids = set()
        for office_staff in obj.staff.prefetch_related("user").all():
            for user in office_staff.user.all():
                if user.id in seen_ids:
                    continue
                seen_ids.add(user.id)
                users.append(SimpleUserSerializer(user).data)
        return users

    def get_created_by(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_office_contactPerson_details(self, obj):
        user = obj.office_contact_person
        if not user:
            return None
        return SimpleUserSerializer(user).data

    def get_warehouses(self, obj):
        if not hasattr(self, "_inventory_warehouses_cache"):
            inventory_warehouses = InventoryWarehouse.objects.order_by("-created_at")
            self._inventory_warehouses_cache = InventoryWarehouseSerializer(
                inventory_warehouses,
                many=True,
                context=self.context,
            ).data

        return self._inventory_warehouses_cache

    def validate(self, attrs):
        office = (
            attrs.get("office")
            if "office" in attrs
            else getattr(self.instance, "office", None)
        )
        contact_person = (
            attrs.get("office_contact_person")
            if "office_contact_person" in attrs
            else getattr(self.instance, "office_contact_person", None)
        )

        if contact_person and office:
            if not OfficeStaff.objects.filter(
                office=office, user=contact_person
            ).exists():
                raise serializers.ValidationError(
                    {
                        "office_contactPerson": "Selected contact person must be a user assigned to this office's staff.",
                    }
                )
        return attrs

    def get_staffCount(self, obj):
        return len(self.get_staff(obj))
