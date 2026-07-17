from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework import status
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from paginations import Pagination
from ..models.fiscal_year_models import FiscalYear, AccountingPeriod
from ..serializers.fiscal_year_serializers import (
    FiscalYearSerializer,
    FiscalYearListSerializer,
    AccountingPeriodSerializer,
)


class FiscalYearViewSet(ModelViewSet):
    permission_classes = [AllowAny]
    queryset = FiscalYear.objects.prefetch_related("accounting_periods").all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["name", "code"]
    ordering_fields = ["start_date", "created_at", "name"]
    ordering = ["-start_date"]

    def get_serializer_class(self):
        if self.action == "list":
            return FiscalYearListSerializer
        return FiscalYearSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(created_by=user if user.is_authenticated else None)

    @action(detail=True, methods=["patch"], url_path="change-status")
    def change_status(self, request, pk=None):
        fiscal_year = self.get_object()
        new_status = request.data.get("status")
        allowed = [s for s, _ in FiscalYear.STATUS_CHOICES]
        if new_status not in allowed:
            return Response(
                {"status": f"Must be one of: {', '.join(allowed)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Only one active FY at a time
        if new_status == "active":
            FiscalYear.objects.exclude(pk=fiscal_year.pk).filter(status="active").update(status="closed")
        with transaction.atomic():
            fiscal_year.status = new_status
            fiscal_year.save(update_fields=["status"])
        serializer = FiscalYearSerializer(fiscal_year, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="periods")
    def periods(self, request, pk=None):
        fiscal_year = self.get_object()
        periods = fiscal_year.accounting_periods.all()
        serializer = AccountingPeriodSerializer(periods, many=True)
        return Response(serializer.data)


class AccountingPeriodViewSet(ModelViewSet):
    permission_classes = [AllowAny]
    queryset = AccountingPeriod.objects.select_related("fiscal_year", "closed_by").all()
    serializer_class = AccountingPeriodSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["fiscal_year", "status"]
    ordering = ["period_number"]

    def get_queryset(self):
        qs = super().get_queryset()
        fy_id = self.request.query_params.get("fiscal_year")
        if fy_id:
            qs = qs.filter(fiscal_year_id=fy_id)
        return qs

    @action(detail=True, methods=["patch"], url_path="close")
    def close_period(self, request, pk=None):
        period = self.get_object()
        if period.status == "closed":
            return Response({"detail": "Period is already closed."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            user = request.user if request.user.is_authenticated else None
            period.close(user=user)
        serializer = AccountingPeriodSerializer(period)
        return Response(serializer.data)

    @action(detail=True, methods=["patch"], url_path="reopen")
    def reopen_period(self, request, pk=None):
        period = self.get_object()
        if period.status == "open":
            return Response({"detail": "Period is already open."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            period.reopen()
        serializer = AccountingPeriodSerializer(period)
        return Response(serializer.data)
