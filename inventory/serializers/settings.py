from rest_framework import serializers
from inventory.models import InventorySettings


class InventorySettingsSerializer(serializers.ModelSerializer):
    default_warehouse_name = serializers.CharField(
        source="default_warehouse.name", read_only=True
    )

    class Meta:
        model = InventorySettings
        fields = "__all__"
