from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from accounting.models import TaxGroup, Tax, TaxRule, WithholdingTax
from accounting.serializers.tax_serializers import (
    TaxGroupSerializer,
    TaxSerializer,
    TaxRuleSerializer,
    WithholdingTaxSerializer,
)


class TaxGroupViewSet(viewsets.ModelViewSet):
    queryset = TaxGroup.objects.all()
    serializer_class = TaxGroupSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class TaxViewSet(viewsets.ModelViewSet):
    queryset = Tax.objects.select_related(
        "tax_group", "account", "refund_account"
    ).all()
    serializer_class = TaxSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["tax_group", "tax_type", "scope", "is_active"]
    search_fields = ["name"]


class TaxRuleViewSet(viewsets.ModelViewSet):
    queryset = TaxRule.objects.select_related("tax").all()
    serializer_class = TaxRuleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["tax", "is_active"]


class WithholdingTaxViewSet(viewsets.ModelViewSet):
    queryset = WithholdingTax.objects.select_related("account").all()
    serializer_class = WithholdingTaxSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name"]
