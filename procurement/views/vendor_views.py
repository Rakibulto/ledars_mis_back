from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from paginations import Pagination
from inventory.views import CreatedByMixin
from ..models.vendor_models import (
    VendorCategory,
    VendorCategoryMapping,
    VendorEvaluation,
    VendorOnboarding,
    VendorVerification,
    VendorPerformance,
)
from ..serializers.vendor_serializers import (
    VendorCategorySerializer,
    VendorCategoryMappingSerializer,
    VendorEvaluationSerializer,
    VendorOnboardingSerializer,
    VendorVerificationSerializer,
    VendorPerformanceSerializer,
)


class VendorCategoryViewSet(viewsets.ModelViewSet):
    queryset = VendorCategory.objects.all()
    serializer_class = VendorCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ["name"]
    filterset_fields = ["is_active"]


class VendorCategoryMappingViewSet(viewsets.ModelViewSet):
    queryset = VendorCategoryMapping.objects.select_related(
        "supplier", "category"
    ).all()
    serializer_class = VendorCategoryMappingSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["supplier", "category"]


class VendorEvaluationViewSet(viewsets.ModelViewSet):
    queryset = VendorEvaluation.objects.select_related("supplier", "evaluated_by").all()
    serializer_class = VendorEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["supplier__name"]
    ordering_fields = ["evaluation_date", "overall_rating"]
    ordering = ["-evaluation_date"]
    filterset_fields = ["supplier"]


class VendorOnboardingViewSet(viewsets.ModelViewSet):
    queryset = VendorOnboarding.objects.select_related("supplier").all()
    serializer_class = VendorOnboardingSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ["supplier__name"]
    filterset_fields = ["status"]

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(initiated_by=self.request.user)


class VendorVerificationViewSet(viewsets.ModelViewSet):
    queryset = VendorVerification.objects.select_related(
        "supplier", "verified_by"
    ).all()
    serializer_class = VendorVerificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "supplier"]


class VendorPerformanceViewSet(viewsets.ModelViewSet):
    queryset = VendorPerformance.objects.select_related("supplier").all()
    serializer_class = VendorPerformanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["period_year", "period_month", "total_spent"]
    ordering = ["-period_year", "-period_month"]
    filterset_fields = ["supplier", "period_year"]

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        from django.db.models import Avg, Sum

        supplier_id = request.query_params.get("supplier")
        qs = VendorPerformance.objects.all()
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        agg = qs.aggregate(
            total_orders=Sum("total_orders"),
            total_on_time=Sum("on_time_deliveries"),
            total_late=Sum("late_deliveries"),
            total_rejected=Sum("rejected_items"),
            total_spent=Sum("total_spent"),
            avg_compliance=Avg("compliance_score"),
        )
        return Response(agg)
