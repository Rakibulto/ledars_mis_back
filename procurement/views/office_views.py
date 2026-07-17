# views.py

from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from ..models.office_models import OfficeManagement, OfficeStaff, Warehouse
from ..serializers.office_serializers import (
    OfficeManagementSerializer,
    OfficeStaffSerializer,
    WarehouseSerializer,
)
from inventory.views import CreatedByMixin
from vendorportal.views.atomic import AtomicModelViewSetMixin

# ======================================
# Office Management ViewSet
# ======================================


class OfficeManagementViewSet(
    AtomicModelViewSetMixin, CreatedByMixin, viewsets.ModelViewSet
):
    queryset = OfficeManagement.objects.all().order_by("-id")
    serializer_class = OfficeManagementSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["type", "status"]
    search_fields = [
        "office_id",
        "name",
        "code",
        "district",
        "division",
    ]
    ordering_fields = [
        "id",
        "name",
        "created_at",
        "updated_at",
    ]


# ======================================
# Office Staff ViewSet
# ======================================


class OfficeStaffViewSet(viewsets.ModelViewSet):
    queryset = OfficeStaff.objects.all().order_by("-id")
    serializer_class = OfficeStaffSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["office"]
    search_fields = [
        "office__name",
        "user__name",
        "user__email",
    ]
    ordering_fields = [
        "id",
        "created_at",
    ]


# ======================================
# Warehouse ViewSet
# ======================================


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all().order_by("-id")
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "warehouse_id",
        "name",
        "office__name",
        "address",
    ]
    ordering_fields = [
        "id",
        "name",
    ]
