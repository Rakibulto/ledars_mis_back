from rest_framework import serializers
from inventory.models import (
    DonorFundedInventory,
    FieldDistribution,
    LossDamageClaim,
    LossDamageClaimItem,
    EmergencyReserve,
    EmergencyReserveItem,
    CommodityTracking,
    PipelineTracking,
    CustomsImportTracking,
    HumanitarianKit,
    DisposalRecord,
    VehicleDispatch,
    VehicleDispatchCargo,
    BeneficiaryDistributionList,
    BeneficiaryDistributionItem,
    Waybill,
    WaybillItem,
    FieldWarehouse,
)


class DonorFundedInventorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = DonorFundedInventory
        fields = "__all__"


class FieldDistributionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    distributed_by_name = serializers.CharField(
        source="distributed_by.username", read_only=True
    )

    class Meta:
        model = FieldDistribution
        fields = "__all__"


# ── Loss & Damage Claims ──
class LossDamageClaimItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)

    class Meta:
        model = LossDamageClaimItem
        fields = ["id", "product_id", "product", "qty", "value", "description"]
        extra_kwargs = {"product": {"write_only": True, "required": False}}


class LossDamageClaimItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LossDamageClaimItem
        fields = ["product", "qty", "value", "description"]


class LossDamageClaimReadSerializer(serializers.ModelSerializer):
    items = LossDamageClaimItemSerializer(many=True, read_only=True)

    class Meta:
        model = LossDamageClaim
        fields = "__all__"


class LossDamageClaimWriteSerializer(serializers.ModelSerializer):
    items = LossDamageClaimItemWriteSerializer(many=True, required=False)

    class Meta:
        model = LossDamageClaim
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        claim = LossDamageClaim.objects.create(**validated_data)
        for item_data in items_data:
            LossDamageClaimItem.objects.create(claim=claim, **item_data)
        return claim

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                LossDamageClaimItem.objects.create(claim=instance, **item_data)
        return instance


# ── Emergency Reserves ──
class EmergencyReserveItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)

    class Meta:
        model = EmergencyReserveItem
        fields = ["id", "product_id", "product", "reserved", "min_reserve"]
        extra_kwargs = {"product": {"write_only": True, "required": False}}


class EmergencyReserveItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyReserveItem
        fields = ["product", "reserved", "min_reserve"]


class EmergencyReserveReadSerializer(serializers.ModelSerializer):
    items = EmergencyReserveItemSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    warehouse_id = serializers.IntegerField(source="warehouse.id", read_only=True)

    class Meta:
        model = EmergencyReserve
        fields = "__all__"


class EmergencyReserveWriteSerializer(serializers.ModelSerializer):
    items = EmergencyReserveItemWriteSerializer(many=True, required=False)

    class Meta:
        model = EmergencyReserve
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        reserve = EmergencyReserve.objects.create(**validated_data)
        for item_data in items_data:
            EmergencyReserveItem.objects.create(reserve=reserve, **item_data)
        return reserve

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                EmergencyReserveItem.objects.create(reserve=instance, **item_data)
        return instance


# ── Commodity Tracking ──
class CommodityTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommodityTracking
        fields = "__all__"


# ── Pipeline Tracking ──
class PipelineTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PipelineTracking
        fields = "__all__"


# ── Customs & Import Tracking ──
class CustomsImportTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomsImportTracking
        fields = "__all__"


# ── Humanitarian Kit ──
class HumanitarianKitSerializer(serializers.ModelSerializer):
    bom_id = serializers.IntegerField(source="bom.id", read_only=True)

    class Meta:
        model = HumanitarianKit
        fields = "__all__"


# ── Disposal Record ──
class DisposalRecordSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_id = serializers.IntegerField(source="product.id", read_only=True)

    class Meta:
        model = DisposalRecord
        fields = "__all__"


# ── Vehicle Dispatch ──
class VehicleDispatchCargoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleDispatchCargo
        fields = ["id", "description", "weight"]


class VehicleDispatchCargoWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleDispatchCargo
        fields = ["description", "weight"]


class VehicleDispatchReadSerializer(serializers.ModelSerializer):
    cargo = VehicleDispatchCargoSerializer(many=True, read_only=True)

    class Meta:
        model = VehicleDispatch
        fields = "__all__"


class VehicleDispatchWriteSerializer(serializers.ModelSerializer):
    cargo = VehicleDispatchCargoWriteSerializer(many=True, required=False)

    class Meta:
        model = VehicleDispatch
        fields = "__all__"

    def create(self, validated_data):
        cargo_data = validated_data.pop("cargo", [])
        dispatch = VehicleDispatch.objects.create(**validated_data)
        for c in cargo_data:
            VehicleDispatchCargo.objects.create(dispatch=dispatch, **c)
        return dispatch

    def update(self, instance, validated_data):
        cargo_data = validated_data.pop("cargo", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if cargo_data is not None:
            instance.cargo.all().delete()
            for c in cargo_data:
                VehicleDispatchCargo.objects.create(dispatch=instance, **c)
        return instance


# ── Beneficiary Distribution List ──
class BeneficiaryDistributionItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)

    class Meta:
        model = BeneficiaryDistributionItem
        fields = ["id", "product_id", "product", "qty", "unit"]
        extra_kwargs = {"product": {"write_only": True, "required": False}}


class BeneficiaryDistributionItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BeneficiaryDistributionItem
        fields = ["product", "qty", "unit"]


class BeneficiaryDistributionListReadSerializer(serializers.ModelSerializer):
    items_per_beneficiary = BeneficiaryDistributionItemSerializer(
        many=True, read_only=True
    )

    class Meta:
        model = BeneficiaryDistributionList
        fields = "__all__"


class BeneficiaryDistributionListWriteSerializer(serializers.ModelSerializer):
    items_per_beneficiary = BeneficiaryDistributionItemWriteSerializer(
        many=True, required=False
    )

    class Meta:
        model = BeneficiaryDistributionList
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items_per_beneficiary", [])
        dist = BeneficiaryDistributionList.objects.create(**validated_data)
        for item_data in items_data:
            BeneficiaryDistributionItem.objects.create(
                distribution_list=dist, **item_data
            )
        return dist

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items_per_beneficiary", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items_per_beneficiary.all().delete()
            for item_data in items_data:
                BeneficiaryDistributionItem.objects.create(
                    distribution_list=instance, **item_data
                )
        return instance


# ── Waybill Management ──
class WaybillItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaybillItem
        fields = ["id", "description", "qty", "weight"]


class WaybillItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaybillItem
        fields = ["description", "qty", "weight"]


class WaybillReadSerializer(serializers.ModelSerializer):
    items = WaybillItemSerializer(many=True, read_only=True)

    class Meta:
        model = Waybill
        fields = "__all__"


class WaybillWriteSerializer(serializers.ModelSerializer):
    items = WaybillItemWriteSerializer(many=True, required=False)

    class Meta:
        model = Waybill
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        waybill = Waybill.objects.create(**validated_data)
        for item_data in items_data:
            WaybillItem.objects.create(waybill=waybill, **item_data)
        return waybill

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                WaybillItem.objects.create(waybill=instance, **item_data)
        return instance


# ── Field Warehouse ──
class FieldWarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldWarehouse
        fields = "__all__"
