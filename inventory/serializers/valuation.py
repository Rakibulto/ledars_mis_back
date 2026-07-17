from rest_framework import serializers
from inventory.models import InventoryValuation, LandedCost


class InventoryValuationSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = InventoryValuation
        fields = "__all__"


class LandedCostSerializer(serializers.ModelSerializer):
    grn_number = serializers.CharField(source="grn.grn_number", read_only=True)

    class Meta:
        model = LandedCost
        fields = "__all__"
