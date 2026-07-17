from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from paginations import Pagination
from inventory.models import (
    DonorFundedInventory,
    FieldDistribution,
    LossDamageClaim,
    EmergencyReserve,
    CommodityTracking,
    PipelineTracking,
    CustomsImportTracking,
    HumanitarianKit,
    DisposalRecord,
    VehicleDispatch,
    BeneficiaryDistributionList,
    Waybill,
    FieldWarehouse,
)
from inventory.serializers import (
    DonorFundedInventorySerializer,
    FieldDistributionSerializer,
    LossDamageClaimReadSerializer,
    LossDamageClaimWriteSerializer,
    EmergencyReserveReadSerializer,
    EmergencyReserveWriteSerializer,
    CommodityTrackingSerializer,
    PipelineTrackingSerializer,
    CustomsImportTrackingSerializer,
    HumanitarianKitSerializer,
    DisposalRecordSerializer,
    VehicleDispatchReadSerializer,
    VehicleDispatchWriteSerializer,
    BeneficiaryDistributionListReadSerializer,
    BeneficiaryDistributionListWriteSerializer,
    WaybillReadSerializer,
    WaybillWriteSerializer,
    FieldWarehouseSerializer,
)


class DonorFundedInventoryViewSet(ModelViewSet):
    queryset = DonorFundedInventory.objects.select_related("product", "warehouse").all()
    serializer_class = DonorFundedInventorySerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter]
    search_fields = ["project_name", "donor", "grant_reference"]


class FieldDistributionViewSet(ModelViewSet):
    queryset = FieldDistribution.objects.select_related(
        "product", "distributed_by"
    ).all()
    serializer_class = FieldDistributionSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filterset_fields = ["status"]


class LossDamageClaimViewSet(ModelViewSet):
    queryset = LossDamageClaim.objects.prefetch_related("items__product").all()
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["reference", "shipment_ref", "carrier"]
    filterset_fields = ["status", "type"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return LossDamageClaimWriteSerializer
        return LossDamageClaimReadSerializer


class EmergencyReserveViewSet(ModelViewSet):
    queryset = EmergencyReserve.objects.select_related("warehouse").prefetch_related(
        "items__product"
    ).all()
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter]
    search_fields = ["warehouse__name", "authorization_level"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return EmergencyReserveWriteSerializer
        return EmergencyReserveReadSerializer


class CommodityTrackingViewSet(ModelViewSet):
    queryset = CommodityTracking.objects.all()
    serializer_class = CommodityTrackingSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["commodity", "donor", "grant"]
    filterset_fields = ["compliance_status"]


class PipelineTrackingViewSet(ModelViewSet):
    queryset = PipelineTracking.objects.all()
    serializer_class = PipelineTrackingSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["reference", "shipment", "carrier"]
    filterset_fields = ["status"]


class CustomsImportTrackingViewSet(ModelViewSet):
    queryset = CustomsImportTracking.objects.all()
    serializer_class = CustomsImportTrackingSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["reference", "shipment", "port"]
    filterset_fields = ["customs_status"]


class HumanitarianKitViewSet(ModelViewSet):
    queryset = HumanitarianKit.objects.select_related("bom").all()
    serializer_class = HumanitarianKitSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter]
    search_fields = ["name", "code", "target_group"]


class DisposalRecordViewSet(ModelViewSet):
    queryset = DisposalRecord.objects.select_related("product").all()
    serializer_class = DisposalRecordSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["reference", "reason", "method"]
    filterset_fields = ["reason"]


class VehicleDispatchViewSet(ModelViewSet):
    queryset = VehicleDispatch.objects.prefetch_related("cargo").all()
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["reference", "vehicle", "driver", "route"]
    filterset_fields = ["status"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return VehicleDispatchWriteSerializer
        return VehicleDispatchReadSerializer


class BeneficiaryDistributionListViewSet(ModelViewSet):
    queryset = BeneficiaryDistributionList.objects.prefetch_related(
        "items_per_beneficiary__product"
    ).all()
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["name", "project", "location"]
    filterset_fields = ["status"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return BeneficiaryDistributionListWriteSerializer
        return BeneficiaryDistributionListReadSerializer


class WaybillViewSet(ModelViewSet):
    queryset = Waybill.objects.prefetch_related("items").all()
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["reference", "origin", "destination", "vehicle", "driver"]
    filterset_fields = ["status"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return WaybillWriteSerializer
        return WaybillReadSerializer


class FieldWarehouseViewSet(ModelViewSet):
    queryset = FieldWarehouse.objects.all()
    serializer_class = FieldWarehouseSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["name", "location", "manager"]
    filterset_fields = ["type", "condition"]
