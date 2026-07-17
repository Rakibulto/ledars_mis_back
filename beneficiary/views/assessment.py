from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from inventory.views import CreatedByMixin
from paginations import Pagination
from rest_framework.decorators import action
from beneficiary.models import VulnerabilityAssessment, ImpactMeasurement, OutcomeIndicator, NeedsAssessment
from beneficiary.serializers import (
    VulnerabilityAssessmentSerializer,
    ImpactMeasurementSerializer,
    OutcomeIndicatorSerializer,
    NeedsAssessmentSerializer,
)
from beneficiary.services import get_vulnerability_summary, get_impact_summary


class VulnerabilityAssessmentViewSet(CreatedByMixin, ModelViewSet):

    queryset = VulnerabilityAssessment.objects.prefetch_related(
        "beneficiary", "created_by"
    ).all()
    serializer_class = VulnerabilityAssessmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filterset_fields = ["risk_level"]
    search_fields = ["assessment_code", "beneficiary__name", "assessor"]
    ordering_fields = ["id", "created_at"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["get"], url_path="summary")
    def vulnerability_summary(self, request):
        stats = get_vulnerability_summary()
        return Response(stats)


class ImpactMeasurementViewSet(CreatedByMixin, ModelViewSet):
    queryset = ImpactMeasurement.objects.all().order_by("created_at")
    serializer_class = ImpactMeasurementSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    @action(detail=False, methods=["get"], url_path="summary")
    def impact_summary(self, request):
        stats = get_impact_summary()
        return Response(stats)


class OutcomeIndicatorViewSet(CreatedByMixin, ModelViewSet):
    queryset = OutcomeIndicator.objects.all().order_by("-created_at")
    serializer_class = OutcomeIndicatorSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination


class NeedsAssessmentViewSet(CreatedByMixin, ModelViewSet):
    queryset = NeedsAssessment.objects.select_related("created_by").order_by("-created_at")
    serializer_class = NeedsAssessmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status"]
    search_fields = ["reference", "location", "assessor"]
    # ordering_fields = ["date", "gap_score", "created_at"]
    # ordering = ["-created_at"]
