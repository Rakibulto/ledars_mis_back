from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from paginations import Pagination
from inventory.models import ReorderRule, KittingBOM
from inventory.serializers import ReorderRuleSerializer, KittingBOMSerializer


class ReorderRuleViewSet(ModelViewSet):
    queryset = ReorderRule.objects.select_related("product", "warehouse").order_by("-id")
    serializer_class = ReorderRuleSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_fields = ["is_active", "trigger", "product", "warehouse"]
    search_fields = ["product__name", "product__code", "warehouse__name", "trigger"]
    ordering_fields = [
        "id",
        "product__name",
        "warehouse__name",
        "min_qty",
        "max_qty",
        "reorder_qty",
        "lead_time_days",
        "trigger",
        "is_active",
    ]
    ordering = ["-id"]


class ReplenishmentViewSet(ReorderRuleViewSet):
    pass


class KittingBOMViewSet(ModelViewSet):
    queryset = (
        KittingBOM.objects.select_related("product")
        .prefetch_related("components__component")
        .order_by("-id")
    )
    serializer_class = KittingBOMSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_fields = ["is_active", "product"]
    search_fields = ["name", "code", "product__name", "product__code", "description"]
    ordering_fields = ["id", "name", "code", "product__name", "total_cost", "assembly_time_minutes", "created_at"]
    ordering = ["-id"]
