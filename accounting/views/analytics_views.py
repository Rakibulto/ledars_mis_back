from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from accounting.models import CostCenter, AnalyticPlan, AnalyticAccount, AnalyticLine, AnalyticTag
from accounting.serializers.analytics_serializers import (
    CostCenterSerializer,
    AnalyticPlanSerializer,
    AnalyticAccountSerializer,
    AnalyticLineSerializer,
    AnalyticTagSerializer,
)


class CostCenterViewSet(viewsets.ModelViewSet):
    queryset = CostCenter.objects.select_related(
        "parent", "department", "project"
    ).all()
    serializer_class = CostCenterSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["is_active", "department", "project"]
    search_fields = ["name", "code"]


class AnalyticPlanViewSet(viewsets.ModelViewSet):
    queryset = AnalyticPlan.objects.select_related("parent_plan").prefetch_related(
        "analytic_accounts"
    ).all()
    serializer_class = AnalyticPlanSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active", "level"]
    search_fields = ["name", "governance_owner"]
    ordering_fields = ["level", "name"]


class AnalyticAccountViewSet(viewsets.ModelViewSet):
    queryset = AnalyticAccount.objects.select_related("project", "currency", "plan").all()
    serializer_class = AnalyticAccountSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["group", "is_active", "plan"]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "balance"]


class AnalyticLineViewSet(viewsets.ModelViewSet):
    queryset = AnalyticLine.objects.select_related(
        "analytic_account", "journal_item", "cost_center", "tag"
    ).all()
    serializer_class = AnalyticLineSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["analytic_account", "cost_center", "date"]
    ordering_fields = ["date", "amount"]


class AnalyticTagViewSet(viewsets.ModelViewSet):
    queryset = AnalyticTag.objects.all()
    serializer_class = AnalyticTagSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["name"]
