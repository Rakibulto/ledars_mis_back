from rest_framework import generics, filters

from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from inventory.views import CreatedByMixin
from paginations import Pagination
from rest_framework.decorators import action
from django.db.models import Count, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from beneficiary.models import (
    Beneficiary,
    ServiceRH,
    ServiceCategory,
    ServiceDelivery,
    VulnerabilityType,
)
from beneficiary.serializers import (
    BeneficiarySerializer,
    BeneficiarySummarySerializer,
    ServiceRHSerializer,
    ServiceCategorySerializer,
    ServiceDeliverySerializer,
    ServiceDeliveryStatsSerializer,
    VulnerabilityTypeSerializer,
)
from ..serializers.core import SimpleBeneficierySerializer

from beneficiary.filters import (
    BeneficiaryFilter,
    ServiceRHFilter,
    ServiceCategoryFilter,
    ServiceDeliveryFilter,
    VulnerabilityTypeFilter,
)
from beneficiary.services import get_beneficiary_summary, get_service_delivery_stats


class BeneficiaryViewSet(CreatedByMixin, ModelViewSet):
    queryset = Beneficiary.objects.annotate(
        total_services_received=Count("services_received"),
        total_services_value=Coalesce(
            Sum("services_received__value"),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    ).select_related("created_by", "project")
    serializer_class = BeneficiarySerializer

    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = BeneficiaryFilter
    search_fields = ["ben_code", "name", "email", "project__name"]
    ordering_fields = ["created_at", "total_services_received", "total_services_value"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        stats = get_beneficiary_summary()
        serializer = BeneficiarySummarySerializer(stats)
        return Response(serializer.data)
    

class SimpleBeneficieryViews(generics.ListAPIView):
    queryset = Beneficiary.objects.all()
    serializer_class = SimpleBeneficierySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]


    search_fields = ["name", "ben_code"]
    ordering_fields = ["created_at", "name"]
    ordering = ["-created_at"]

    # ✅ Filters
    filterset_fields = [
        "name",     
        "ben_code",      
    ]

class ServiceRHViewSet(CreatedByMixin, ModelViewSet):
    queryset = ServiceRH.objects.select_related(
        "beneficiary", "created_by", "project"
    ).all()
    serializer_class = ServiceRHSerializer

    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ServiceRHFilter
    search_fields = ["beneficiary", "name", "status", "project__name"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


class ServiceCategoryViewSet(CreatedByMixin, ModelViewSet):
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer

    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ServiceCategoryFilter
    search_fields = ["name", "description", "status", "created_by"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


class VulnerabilityTypeViewSet(CreatedByMixin, ModelViewSet):
    queryset = VulnerabilityType.objects.all()
    serializer_class = VulnerabilityTypeSerializer

    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = VulnerabilityTypeFilter
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


class ServiceDeliveryViewSet(CreatedByMixin, ModelViewSet):
    queryset = ServiceDelivery.objects.select_related("beneficiary", "category").all()
    serializer_class = ServiceDeliverySerializer

    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ServiceDeliveryFilter
    search_fields = [
        "beneficiary__ben_code",
        "beneficiary__name",
        "service_type",
        "category__name",
        "location",
        "status",
        "provider",
    ]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        stats = get_service_delivery_stats()
        serializer = ServiceDeliveryStatsSerializer(stats)
        return Response(serializer.data)
