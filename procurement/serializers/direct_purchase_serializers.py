from rest_framework import serializers

from employee.models import Department
from project_managements.models import ProjectManagementProject

from ..models.direct_purchase_models import (
    Shop,
    DirectPurchase,
    DirectPurchaseItem,
    DirectPurchaseStatusLog,
)
from ..models.account_models import Account
from ..models.budget_models import Budget
from ..models.office_models import OfficeManagement


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ["id", "name", "phone", "email", "address"]


class DirectPurchaseItemSerializer(serializers.ModelSerializer):
    extended_amount = serializers.SerializerMethodField()

    class Meta:
        model = DirectPurchaseItem
        fields = [
            "id",
            "item",
            "description",
            "specification",
            "unit",
            "quantity",
            "unit_price",
            "extended_amount",
            "remarks",
        ]

    def get_extended_amount(self, obj):
        return float((obj.quantity or 0) * (obj.unit_price or 0))


class DirectPurchaseStatusLogSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(
        source="changed_by.username", read_only=True, default=""
    )

    class Meta:
        model = DirectPurchaseStatusLog
        fields = ["id", "from_status", "to_status", "changed_by_name", "comments", "changed_at"]


class DirectPurchaseSerializer(serializers.ModelSerializer):
    # Write-only nested items
    dp_items_data = DirectPurchaseItemSerializer(many=True, write_only=True, required=False)
    # Read items
    dp_items = DirectPurchaseItemSerializer(many=True, read_only=True)
    status_logs = DirectPurchaseStatusLogSerializer(many=True, read_only=True)

    # FK read helpers
    department_name = serializers.CharField(source="department.name", read_only=True, default="")
    shop_name = serializers.CharField(source="shop.name", read_only=True, default="")
    # Free-text shop creation: if no existing shop ID is provided, use this name to get_or_create
    shop_name_create = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    category_name = serializers.SerializerMethodField()
    project_info = serializers.SerializerMethodField()
    budget_code_display = serializers.SerializerMethodField()
    account_code_display = serializers.SerializerMethodField()
    requesting_office_info = serializers.SerializerMethodField()
    delivery_location_info = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True, default=""
    )
    item_count = serializers.IntegerField(source="dp_items.count", read_only=True)

    # FK writable
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=ProjectManagementProject.objects.all(), required=False, allow_null=True
    )
    shop = serializers.PrimaryKeyRelatedField(
        queryset=Shop.objects.all(), required=False, allow_null=True
    )
    budget_code = serializers.PrimaryKeyRelatedField(
        queryset=Budget.objects.all(), required=False, allow_null=True
    )
    account_code = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), required=False, allow_null=True
    )
    requesting_office = serializers.PrimaryKeyRelatedField(
        queryset=OfficeManagement.objects.all(), required=False, allow_null=True
    )
    delivery_location = serializers.PrimaryKeyRelatedField(
        queryset=OfficeManagement.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = DirectPurchase
        fields = [
            "id",
            "dp_number",
            # Basic info
            "department",
            "department_name",
            "project",
            "project_info",
            "category",
            "category_name",
            "priority",
            "fiscal_year",
            "purpose",
            # Shop / budget
            "shop",
            "shop_name",
            "shop_name_create",
            "reference_number",
            "budget_code",
            "budget_code_display",
            "account_code",
            "account_code_display",
            # BOQ
            "dp_items",
            "dp_items_data",
            "item_count",
            "total_amount",
            # Specs
            "specifications",
            "preferred_brand",
            "alternative_brands",
            "warranty_period",
            "country_of_origin",
            "quality_standards",
            # Delivery
            "requesting_office",
            "requesting_office_info",
            "delivery_location",
            "delivery_location_info",
            "purchase_date",
            "expected_delivery_date",
            "payment_terms",
            "contact_person",
            "contact_phone",
            "special_instruction",
            "justification",
            "remarks",
            # Status
            "status",
            "attachment",
            # Meta
            "created_by_username",
            "created_at",
            "updated_at",
            "status_logs",
        ]
        read_only_fields = ["id", "dp_number", "created_at", "updated_at"]

    # ── computed helpers ───────────────────────────────────────────────────

    def get_category_name(self, obj):
        if obj.category:
            return obj.category.name
        return ""

    def get_project_info(self, obj):
        if obj.project:
            return {"id": obj.project.id, "name": obj.project.title, "code": obj.project.code}
        return None

    def get_budget_code_display(self, obj):
        if obj.budget_code:
            return {"id": obj.budget_code.id, "code": obj.budget_code.code, "name": obj.budget_code.name}
        return None

    def get_account_code_display(self, obj):
        if obj.account_code:
            return {"id": obj.account_code.id, "code": obj.account_code.code, "name": obj.account_code.name}
        return None

    def get_requesting_office_info(self, obj):
        if obj.requesting_office:
            return {"id": obj.requesting_office.id, "name": obj.requesting_office.name}
        return None

    def get_delivery_location_info(self, obj):
        if obj.delivery_location:
            return {"id": obj.delivery_location.id, "name": obj.delivery_location.name}
        return None

    # ── create / update with nested items ─────────────────────────────────

    def _resolve_shop(self, validated_data):
        """If no shop FK given but shop_name_create is provided, get_or_create the shop."""
        shop_name = validated_data.pop("shop_name_create", None) or ""
        if not validated_data.get("shop") and shop_name.strip():
            shop, _ = Shop.objects.get_or_create(name=shop_name.strip())
            validated_data["shop"] = shop

    def create(self, validated_data):
        items_data = validated_data.pop("dp_items_data", [])
        self._resolve_shop(validated_data)
        instance = super().create(validated_data)
        self._save_items(instance, items_data)
        instance.recalculate_total()
        return instance

    def update(self, instance, validated_data):
        items_data = validated_data.pop("dp_items_data", None)
        self._resolve_shop(validated_data)
        instance = super().update(instance, validated_data)
        if items_data is not None:
            instance.dp_items.all().delete()
            self._save_items(instance, items_data)
        instance.recalculate_total()
        return instance

    def _save_items(self, instance, items_data):
        for item_data in items_data:
            DirectPurchaseItem.objects.create(direct_purchase=instance, **item_data)
