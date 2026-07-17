from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from paginations import Pagination
from inventory.models import InventoryValuation, LandedCost
from inventory.serializers import InventoryValuationSerializer, LandedCostSerializer


class InventoryValuationViewSet(ModelViewSet):
    queryset = InventoryValuation.objects.select_related("product", "warehouse").all()
    serializer_class = InventoryValuationSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["product__name", "product__code"]
    filterset_fields = ["method", "warehouse"]


class LandedCostViewSet(ModelViewSet):
    queryset = LandedCost.objects.select_related("grn").all()
    serializer_class = LandedCostSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filterset_fields = ["status"]
