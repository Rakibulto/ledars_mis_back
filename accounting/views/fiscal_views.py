from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction

from accounting.models import FiscalYear, FiscalPeriod
from accounting.serializers.fiscal_serializers import (
    FiscalYearListSerializer,
    FiscalYearDetailSerializer,
    FiscalPeriodSerializer,
)


class FiscalYearViewSet(viewsets.ModelViewSet):
    queryset = FiscalYear.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "is_active"]
    search_fields = ["name", "code"]

    def get_serializer_class(self):
        if self.action == "list":
            return FiscalYearListSerializer
        return FiscalYearDetailSerializer

    @action(detail=True, methods=["post"])
    def generate_periods(self, request, pk=None):
        """Auto-generate any missing monthly periods for a fiscal year."""
        fiscal_year = self.get_object()

        from dateutil.relativedelta import relativedelta

        period_specs = []
        current = fiscal_year.start_date
        number = 1
        while current < fiscal_year.end_date:
            next_month = current + relativedelta(months=1)
            if next_month > fiscal_year.end_date:
                next_month = fiscal_year.end_date
            period_end = (
                next_month - relativedelta(days=1)
                if next_month != fiscal_year.end_date
                else fiscal_year.end_date
            )
            period_specs.append(
                {
                    "name": current.strftime("%B %Y"),
                    "number": number,
                    "start_date": current,
                    "end_date": period_end,
                }
            )
            current = next_month
            number += 1

        existing_numbers = set(
            fiscal_year.periods.values_list("number", flat=True)
        )
        missing_periods = [
            FiscalPeriod(fiscal_year=fiscal_year, **spec)
            for spec in period_specs
            if spec["number"] not in existing_numbers
        ]

        if missing_periods:
            with transaction.atomic():
                FiscalPeriod.objects.bulk_create(missing_periods)

        created_count = len(missing_periods)
        total_count = len(period_specs)
        if created_count:
            detail = f"{created_count} periods generated."
        else:
            detail = "Fiscal periods are already generated."

        return Response(
            {
                "detail": detail,
                "created_count": created_count,
                "period_count": total_count,
            }
        )

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """Close a fiscal year."""
        fiscal_year = self.get_object()
        fiscal_year.status = "closed"
        fiscal_year.save(update_fields=["status"])
        fiscal_year.periods.update(status="closed")
        return Response({"detail": "Fiscal year closed."})

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        """Reopen a closed fiscal year."""
        fiscal_year = self.get_object()
        fiscal_year.status = "open"
        fiscal_year.save(update_fields=["status"])
        return Response({"detail": "Fiscal year reopened."})


class FiscalPeriodViewSet(viewsets.ModelViewSet):
    queryset = FiscalPeriod.objects.select_related("fiscal_year").all()
    serializer_class = FiscalPeriodSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["fiscal_year", "status"]
