from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from django.db import transaction
from paginations import Pagination
from ..models.settings_models import Currency, ExchangeRate
from ..serializers.currency_serializers import (
    CurrencySerializer,
    CurrencyListSerializer,
    ExchangeRateSerializer,
)


class CurrencyFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status")
    is_base = django_filters.BooleanFilter(field_name="is_base")

    class Meta:
        model = Currency
        fields = ["status", "is_base"]


class CurrencyViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for currencies.
    Custom actions:
      PATCH  /currencies/{id}/set-status/  → toggle active/inactive
    """

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CurrencyFilter
    search_fields = ["code", "name", "symbol"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["-is_base", "code"]

    def get_queryset(self):
        return Currency.objects.prefetch_related("exchange_rates").all()

    def get_serializer_class(self):
        if self.action == "list":
            return CurrencyListSerializer
        return CurrencySerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        with transaction.atomic():
            serializer.save()

    def perform_destroy(self, instance):
        with transaction.atomic():
            if instance.is_base:
                from rest_framework.exceptions import ValidationError
                raise ValidationError("Cannot delete the base currency.")
            instance.delete()

    @action(detail=True, methods=["patch"], url_path="set-status")
    def set_status(self, request, pk=None):
        """PATCH /currencies/{id}/set-status/  body: {status: 'active'|'inactive'}"""
        currency = self.get_object()
        new_status = request.data.get("status")
        if new_status not in ("active", "inactive"):
            return Response(
                {"status": "Must be 'active' or 'inactive'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            currency.status = new_status
            currency.save(update_fields=["status"])
        return Response(CurrencySerializer(currency, context={"request": request}).data)

    @action(detail=True, methods=["get"], url_path="rates")
    def rates(self, request, pk=None):
        """GET /currencies/{id}/rates/  → all historical rates for this currency."""
        currency = self.get_object()
        qs = currency.exchange_rates.order_by("-effective_date")
        serializer = ExchangeRateSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


class ExchangeRateFilter(django_filters.FilterSet):
    currency = django_filters.NumberFilter(field_name="currency__id")
    currency_code = django_filters.CharFilter(field_name="currency__code")
    from_date = django_filters.DateFilter(field_name="effective_date", lookup_expr="gte")
    to_date = django_filters.DateFilter(field_name="effective_date", lookup_expr="lte")

    class Meta:
        model = ExchangeRate
        fields = ["currency", "currency_code", "from_date", "to_date"]


class ExchangeRateViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for exchange rate history.
    Bulk-update endpoint:
      POST /exchange-rates/bulk-update/  body: [{currency_id, rate, effective_date}, …]
    """

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    serializer_class = ExchangeRateSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ExchangeRateFilter
    search_fields = ["currency__code", "currency__name", "source"]
    ordering_fields = ["effective_date", "currency__code"]
    ordering = ["-effective_date", "currency__code"]

    def get_queryset(self):
        return ExchangeRate.objects.select_related("currency", "created_by").all()

    def perform_create(self, serializer):
        with transaction.atomic():
            serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        with transaction.atomic():
            serializer.save()

    @action(detail=False, methods=["post"], url_path="bulk-update")
    def bulk_update(self, request):
        """
        POST /exchange-rates/bulk-update/
        body: [{"currency": <id>, "rate": <num>, "effective_date": "YYYY-MM-DD"}, …]
        Creates or updates (upsert by currency + effective_date).
        """
        items = request.data
        if not isinstance(items, list) or len(items) == 0:
            return Response(
                {"detail": "Provide a non-empty list of rate objects."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_records = []
        errors = []

        with transaction.atomic():
            for idx, item in enumerate(items):
                serializer = ExchangeRateSerializer(
                    data=item, context={"request": request}
                )
                if serializer.is_valid():
                    # upsert
                    obj, _ = ExchangeRate.objects.update_or_create(
                        currency_id=item["currency"],
                        effective_date=item["effective_date"],
                        defaults={
                            "rate": item["rate"],
                            "source": item.get("source", "manual"),
                            "notes": item.get("notes", ""),
                            "created_by": request.user,
                        },
                    )
                    created_records.append(ExchangeRateSerializer(obj).data)
                else:
                    errors.append({"index": idx, "errors": serializer.errors})

            if errors:
                raise Exception("Validation errors in bulk update")

        return Response(
            {"updated": len(created_records), "records": created_records},
            status=status.HTTP_200_OK,
        )
