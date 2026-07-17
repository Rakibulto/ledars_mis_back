from rest_framework import serializers
from inventory.models import ReorderRule, KittingBOM, KittingBOMLine, Product


class ReorderRuleSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    trigger_label = serializers.CharField(source="get_trigger_display", read_only=True)

    class Meta:
        model = ReorderRule
        fields = "__all__"

    def validate(self, attrs):
        min_qty = attrs.get("min_qty", getattr(self.instance, "min_qty", None))
        max_qty = attrs.get("max_qty", getattr(self.instance, "max_qty", None))
        reorder_qty = attrs.get("reorder_qty", getattr(self.instance, "reorder_qty", None))

        if min_qty is not None and min_qty < 0:
            raise serializers.ValidationError(
                {"min_qty": "Minimum quantity cannot be negative."}
            )

        if max_qty is not None and max_qty < 0:
            raise serializers.ValidationError(
                {"max_qty": "Maximum quantity cannot be negative."}
            )

        if reorder_qty is not None and reorder_qty <= 0:
            raise serializers.ValidationError(
                {"reorder_qty": "Reorder quantity must be greater than zero."}
            )

        if min_qty is not None and max_qty is not None and max_qty < min_qty:
            raise serializers.ValidationError(
                {"max_qty": "Maximum quantity must be greater than or equal to minimum quantity."}
            )

        return attrs


class KittingBOMLineSerializer(serializers.ModelSerializer):
    component_name = serializers.CharField(source="component.name", read_only=True)
    component_code = serializers.CharField(source="component.code", read_only=True)
    bom = serializers.PrimaryKeyRelatedField(read_only=True)
    component = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = KittingBOMLine
        fields = [
            "id",
            "bom",
            "component",
            "component_name",
            "component_code",
            "quantity",
            "unit_cost",
        ]
        read_only_fields = ["id", "bom", "component_name", "component_code"]


class KittingBOMSerializer(serializers.ModelSerializer):
    components = KittingBOMLineSerializer(many=True, required=False)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    component_count = serializers.SerializerMethodField()
    total_component_qty = serializers.SerializerMethodField()

    class Meta:
        model = KittingBOM
        fields = "__all__"

    def get_component_count(self, obj):
        return obj.components.count()

    def get_total_component_qty(self, obj):
        return sum(component.quantity for component in obj.components.all())

    def validate_components(self, value):
        seen_component_ids = set()

        for index, component_data in enumerate(value, start=1):
            component = component_data.get("component")
            quantity = component_data.get("quantity")
            unit_cost = component_data.get("unit_cost")

            if component is None:
                raise serializers.ValidationError(
                    {index - 1: {"component": "A component product is required."}}
                )

            if quantity is None or quantity <= 0:
                raise serializers.ValidationError(
                    {index - 1: {"quantity": "Quantity must be greater than zero."}}
                )

            if unit_cost is not None and unit_cost < 0:
                raise serializers.ValidationError(
                    {index - 1: {"unit_cost": "Unit cost cannot be negative."}}
                )

            if component.id in seen_component_ids:
                raise serializers.ValidationError(
                    {index - 1: {"component": "Each component can only appear once."}}
                )

            seen_component_ids.add(component.id)

        return value

    def _replace_components(self, bom, components_data):
        bom.components.all().delete()

        if not components_data:
            bom.total_cost = 0
            bom.save(update_fields=["total_cost"])
            return

        KittingBOMLine.objects.bulk_create(
            [KittingBOMLine(bom=bom, **component_data) for component_data in components_data]
        )

        bom.total_cost = sum(
            component_data["quantity"] * component_data.get("unit_cost", 0)
            for component_data in components_data
        )
        bom.save(update_fields=["total_cost"])

    def create(self, validated_data):
        components_data = validated_data.pop("components", [])
        bom = KittingBOM.objects.create(**validated_data)
        self._replace_components(bom, components_data)
        return bom

    def update(self, instance, validated_data):
        components_data = validated_data.pop("components", serializers.empty)

        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)

        instance.save()

        if components_data is not serializers.empty:
            self._replace_components(instance, components_data)

        return instance
