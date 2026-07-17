from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from paginations import Pagination
from inventory.filters import (
    QCTemplateFilter,
    QualityAlertFilter,
    QualityCheckFilter,
    QualityTeamFilter,
)
from inventory.models import (
    QualityCheck,
    QualityAlert,
    QualityControlPoint,
    QualityTeam,
    QCTemplate,
)
from inventory.serializers import (
    QualityCheckSerializer,
    QualityAlertSerializer,
    QualityControlPointSerializer,
    QualityTeamSerializer,
    QCTemplateSerializer,
)


class QualityCheckViewSet(ModelViewSet):
    queryset = QualityCheck.objects.select_related(
        "product", "warehouse", "team", "grn_line", "grn_line__grn",
        "office_location", "created_by",
    ).all()
    serializer_class = QualityCheckSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_class = QualityCheckFilter
    search_fields = [
        "reference",
        "check_type",
        "status",
        "result",
        "priority",
        "inspector",
        "notes",
        "findings",
        "corrective_actions",
        "remarks",
        "product__name",
        "product__code",
        "warehouse__name",
        "warehouse__code",
        "team__name",
        "grn_line__grn__grn_number",
        "office_location__name",
        "created_by__username",
    ]
    ordering_fields = [
        "reference",
        "date",
        "check_type",
        "status",
        "result",
        "priority",
        "created_at",
        "product__name",
        "warehouse__name",
        "office_location__name",
    ]
    ordering = ["-date", "-created_at"]

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user)


class QualityAlertViewSet(ModelViewSet):
    queryset = QualityAlert.objects.select_related(
        "product", "reported_by", "office_location", "assigned_to"
    ).all()
    serializer_class = QualityAlertSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_class = QualityAlertFilter
    search_fields = [
        "reference",
        "title",
        "severity",
        "status",
        "description",
        "corrective_action",
        "product__name",
        "product__code",
        "reported_by__username",
        "reported_by__email",
        "office_location__name",
        "assigned_to__username",
    ]
    ordering_fields = [
        "reference",
        "title",
        "severity",
        "status",
        "created_at",
        "product__name",
        "reported_by__username",
        "office_location__name",
        "id",
    ]
    ordering = ["-created_at", "-id"]


class QualityControlPointViewSet(ModelViewSet):
    queryset = QualityControlPoint.objects.select_related(
        "category", "operation_type", "office_location", "product", "assigned_to", "created_by"
    ).order_by("-created_at", "name", "id")
    serializer_class = QualityControlPointSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "reference",
        "name",
        "parameter",
        "standard",
        "inspection_criteria",
        "description",
        "frequency",
        "priority",
        "category__name",
        "operation_type__name",
        "operation_type__code",
        "office_location__name",
        "product__name",
        "product__code",
        "assigned_to__username",
        "created_by__username",
    ]
    ordering_fields = [
        "reference",
        "name",
        "frequency",
        "priority",
        "is_active",
        "is_mandatory",
        "created_at",
        "office_location__name",
        "product__name",
        "assigned_to__username",
        "id",
    ]
    ordering = ["-created_at", "name", "id"]
    filterset_fields = [
        "category", "operation_type", "is_mandatory", "is_active",
        "office_location", "product", "assigned_to", "frequency", "priority",
    ]

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user)


class QualityTeamViewSet(ModelViewSet):
    queryset = QualityTeam.objects.select_related("leader", "category").prefetch_related(
        "members"
    ).all()
    serializer_class = QualityTeamSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_class = QualityTeamFilter
    search_fields = [
        "name",
        "description",
        "leader__username",
        "leader__email",
        "category__name",
    ]
    ordering_fields = ["name", "is_active", "leader__username", "category__name", "id"]
    ordering = ["name", "id"]


class QCTemplateViewSet(ModelViewSet):
    queryset = QCTemplate.objects.select_related("category").all()
    serializer_class = QCTemplateSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_class = QCTemplateFilter
    search_fields = ["name", "category__name"]
    ordering_fields = ["name", "is_active", "category__name", "id"]
    ordering = ["name", "id"]
