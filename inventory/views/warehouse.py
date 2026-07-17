from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from paginations import Pagination
from inventory.models import (
    Warehouse,
    StorageLocation,
    PutawayRule,
    RemovalStrategy,
    OperationType,
    Route,
    ShippingMethod,
)
from inventory.serializers import (
    WarehouseSerializer,
    StorageLocationSerializer,
    PutawayRuleSerializer,
    RemovalStrategySerializer,
    OperationTypeSerializer,
    RouteSerializer,
    ShippingMethodSerializer,
)


class WarehouseViewSet(ModelViewSet):
    queryset = Warehouse.objects.all().order_by("-created_at")
    serializer_class = WarehouseSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ["name", "code", "address", "manager", "phone"]
    ordering_fields = [
        "name",
        "code",
        "warehouse_type",
        "capacity_sqft",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]
    filterset_fields = ["warehouse_type", "is_active"]


class StorageLocationViewSet(ModelViewSet):
    queryset = StorageLocation.objects.select_related("office").order_by(
        "office__name", "name"
    )
    serializer_class = StorageLocationSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "name",
        "barcode",
        "location_type",
        "office__name",
        "office__code",
    ]
    ordering_fields = [
        "name",
        "location_type",
        "barcode",
        "is_active",
        "is_scrap",
        "is_return",
        "office__name",
    ]
    ordering = ["office__name", "name"]
    filterset_fields = [
        "office",
        "location_type",
        "is_active",
        "is_scrap",
        "is_return",
    ]


class PutawayRuleViewSet(ModelViewSet):
    queryset = PutawayRule.objects.select_related(
        "product", "category", "warehouse", "location"
    ).order_by("sequence", "id")
    serializer_class = PutawayRuleSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "product__name",
        "product__code",
        "category__name",
        "warehouse__name",
        "warehouse__code",
        "location__name",
        "location__barcode",
    ]
    ordering_fields = [
        "sequence",
        "is_active",
        "product__name",
        "category__name",
        "warehouse__name",
        "location__name",
        "id",
    ]
    ordering = ["sequence", "id"]
    filterset_fields = ["warehouse", "location", "product", "category", "is_active"]

    def get_queryset(self):
        queryset = super().get_queryset()
        target_type = (
            str(self.request.query_params.get("target_type") or "").strip().lower()
        )

        if target_type == "product":
            queryset = queryset.filter(product__isnull=False)
        elif target_type == "category":
            queryset = queryset.filter(product__isnull=True, category__isnull=False)

        return queryset


class RemovalStrategyViewSet(ModelViewSet):
    queryset = RemovalStrategy.objects.select_related("warehouse").order_by(
        "name", "id"
    )
    serializer_class = RemovalStrategySerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ["name", "strategy", "warehouse__name", "warehouse__code"]
    ordering_fields = ["name", "strategy", "warehouse__name", "is_active", "id"]
    ordering = ["name", "id"]
    filterset_fields = ["warehouse", "strategy", "is_active"]


class OperationTypeViewSet(ModelViewSet):
    queryset = OperationType.objects.select_related(
        "warehouse", "default_source", "default_destination"
    ).order_by("name", "id")
    serializer_class = OperationTypeSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "name",
        "code",
        "operation_type",
        "warehouse__name",
        "warehouse__code",
        "default_source__name",
        "default_destination__name",
    ]
    ordering_fields = [
        "name",
        "code",
        "operation_type",
        "warehouse__name",
        "is_active",
        "id",
    ]
    ordering = ["name", "id"]
    filterset_fields = ["warehouse", "operation_type", "is_active"]


class RouteViewSet(ModelViewSet):
    queryset = Route.objects.order_by("name", "id")
    serializer_class = RouteSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "is_active", "id"]
    ordering = ["name", "id"]
    filterset_fields = ["is_active"]

    def get_queryset(self):
        queryset = super().get_queryset()
        has_steps = (
            str(self.request.query_params.get("has_steps") or "").strip().lower()
        )

        if has_steps == "true":
            queryset = queryset.exclude(steps=[])
        elif has_steps == "false":
            queryset = queryset.filter(steps=[])

        return queryset


class ShippingMethodViewSet(ModelViewSet):
    queryset = ShippingMethod.objects.all()
    serializer_class = ShippingMethodSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
