from rest_framework import serializers
from inventory.models import (
    Warehouse,
    StorageLocation,
    PutawayRule,
    RemovalStrategy,
    OperationType,
    Route,
    ShippingMethod,
)


class WarehouseSerializer(serializers.ModelSerializer):
    warehouse_type_label = serializers.CharField(
        source="get_warehouse_type_display", read_only=True
    )

    class Meta:
        model = Warehouse
        fields = "__all__"


class StorageLocationSerializer(serializers.ModelSerializer):
    office_name = serializers.CharField(source="office.name", read_only=True)
    office_code = serializers.CharField(source="office.code", read_only=True)
    office_type = serializers.CharField(source="office.type", read_only=True)
    location_type_label = serializers.CharField(
        source="get_location_type_display", read_only=True
    )
    child_count = serializers.SerializerMethodField()

    class Meta:
        model = StorageLocation
        fields = "__all__"

    def get_child_count(self, obj):
        # child_count may be annotated by the viewset; fall back to 0
        return getattr(obj, "child_count", 0)


class PutawayRuleSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    location_type_label = serializers.CharField(
        source="location.get_location_type_display", read_only=True
    )
    target_type = serializers.SerializerMethodField()
    target_name = serializers.SerializerMethodField()

    class Meta:
        model = PutawayRule
        fields = "__all__"

    def get_target_type(self, obj):
        if obj.product_id:
            return "product"

        if obj.category_id:
            return "category"

        return None

    def get_target_name(self, obj):
        if obj.product_id:
            return getattr(obj.product, "name", None)

        if obj.category_id:
            return getattr(obj.category, "name", None)

        return None

    def validate(self, attrs):
        product = attrs.get("product", getattr(self.instance, "product", None))
        category = attrs.get("category", getattr(self.instance, "category", None))
        warehouse = attrs.get("warehouse", getattr(self.instance, "warehouse", None))
        location = attrs.get("location", getattr(self.instance, "location", None))

        if bool(product) == bool(category):
            raise serializers.ValidationError(
                {
                    "target": "Select either a product or a category for this putaway rule."
                }
            )

        if warehouse and location and location.warehouse_id != warehouse.id:
            raise serializers.ValidationError(
                {"location": "Selected location must belong to the selected warehouse."}
            )

        return attrs


class RemovalStrategySerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    strategy_label = serializers.CharField(
        source="get_strategy_display", read_only=True
    )

    class Meta:
        model = RemovalStrategy
        fields = "__all__"


class OperationTypeSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    operation_type_label = serializers.CharField(
        source="get_operation_type_display", read_only=True
    )
    default_source_name = serializers.CharField(
        source="default_source.name", read_only=True
    )
    default_destination_name = serializers.CharField(
        source="default_destination.name", read_only=True
    )

    class Meta:
        model = OperationType
        fields = "__all__"

    def validate(self, attrs):
        warehouse = attrs.get("warehouse", getattr(self.instance, "warehouse", None))
        default_source = attrs.get(
            "default_source", getattr(self.instance, "default_source", None)
        )
        default_destination = attrs.get(
            "default_destination", getattr(self.instance, "default_destination", None)
        )

        if warehouse and default_source and default_source.warehouse_id != warehouse.id:
            raise serializers.ValidationError(
                {
                    "default_source": (
                        "Selected default source must belong to the selected warehouse."
                    )
                }
            )

        if (
            warehouse
            and default_destination
            and default_destination.warehouse_id != warehouse.id
        ):
            raise serializers.ValidationError(
                {
                    "default_destination": (
                        "Selected default destination must belong to the selected warehouse."
                    )
                }
            )

        return attrs


class RouteSerializer(serializers.ModelSerializer):
    step_count = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = "__all__"

    def get_step_count(self, obj):
        return len(obj.steps or [])


class ShippingMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingMethod
        fields = "__all__"
