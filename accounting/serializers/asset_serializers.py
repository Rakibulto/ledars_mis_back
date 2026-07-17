from rest_framework import serializers
from accounting.models import (
    AssetCategory,
    Asset,
    AssetDepreciation,
    AssetDisposal,
    AssetImpairment,
    AssetTransfer,
)


class AssetCategorySerializer(serializers.ModelSerializer):
    asset_account_name = serializers.CharField(
        source="asset_account.name", read_only=True, default=""
    )
    depreciation_account_name = serializers.CharField(
        source="depreciation_account.name", read_only=True, default=""
    )
    expense_account_name = serializers.CharField(
        source="expense_account.name", read_only=True, default=""
    )
    assets_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = AssetCategory
        fields = "__all__"


class AssetDepreciationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )

    class Meta:
        model = AssetDepreciation
        fields = "__all__"


class AssetDisposalSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(
        source="get_disposal_method_display", read_only=True
    )

    class Meta:
        model = AssetDisposal
        fields = "__all__"


class AssetImpairmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetImpairment
        fields = "__all__"
        extra_kwargs = {"asset": {"required": False}}


class AssetTransferSerializer(serializers.ModelSerializer):
    from_cost_center_name = serializers.CharField(
        source="from_cost_center.name", read_only=True, default=""
    )
    to_cost_center_name = serializers.CharField(
        source="to_cost_center.name", read_only=True, default=""
    )

    class Meta:
        model = AssetTransfer
        fields = "__all__"
        extra_kwargs = {"asset": {"required": False}}


class AssetListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source="category.name", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    cost_center_name = serializers.CharField(
        source="cost_center.name", read_only=True, default=""
    )
    vendor_name = serializers.CharField(
        source="vendor.name", read_only=True, default=""
    )

    class Meta:
        model = Asset
        fields = [
            "id", "name", "code", "category", "category_name",
            "purchase_date", "purchase_cost", "current_value", "salvage_value",
            "depreciation_method", "useful_life", "serial_number",
            "location", "custodian", "condition", "project_name", "schedule_revision",
            "status", "status_display",
            "vendor", "vendor_name",
            "cost_center", "cost_center_name",
            "created_at",
        ]


class AssetDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source="category.name", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    cost_center_name = serializers.CharField(
        source="cost_center.name", read_only=True, default=""
    )
    vendor_name = serializers.CharField(
        source="vendor.name", read_only=True, default=""
    )
    depreciation_lines = AssetDepreciationSerializer(many=True, read_only=True)
    disposal = AssetDisposalSerializer(read_only=True)
    impairments = AssetImpairmentSerializer(many=True, read_only=True)
    transfers = AssetTransferSerializer(many=True, read_only=True)

    class Meta:
        model = Asset
        fields = "__all__"
