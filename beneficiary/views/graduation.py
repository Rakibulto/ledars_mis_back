from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from inventory.views import CreatedByMixin
from paginations import Pagination
from rest_framework.decorators import action
from beneficiary.models import ExitGraduation, GraduationCriteria, AlumniTracking, ProgressTracking
from beneficiary.serializers import (
    ExitGraduationSerializer,
    GraduationCriteriaSerializer,
    AlumniTrackingSerializer,
    ProgressTrackingSerializer,
)
from beneficiary.services import get_exit_graduation_summary


class ExitGraduationViewSet(CreatedByMixin, ModelViewSet):

    queryset = ExitGraduation.objects.prefetch_related(
        "beneficiary", "program", "created_by"
    ).all()
    serializer_class = ExitGraduationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filterset_fields = ["status", "program"]
    search_fields = ["graduation_code", "beneficiary__beneficiary_code"]
    ordering_fields = ["entry_date", "exit_date", "created_at"]

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        stats = get_exit_graduation_summary()
        return Response(stats)


class GraduationCriteriaViewSet(CreatedByMixin, ModelViewSet):
    queryset = GraduationCriteria.objects.select_related("program", "created_by").all()
    serializer_class = GraduationCriteriaSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status", "program"]
    search_fields = ["criteria", "indicator", "measurement"]
    ordering_fields = ["created_at", "weight"]
    ordering = ["-created_at"]


class AlumniTrackingViewSet(CreatedByMixin, ModelViewSet):
    queryset = AlumniTracking.objects.select_related(
        "beneficiary", "program", "created_by"
    ).all()
    serializer_class = AlumniTrackingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["current_status", "needs_support", "program"]
    search_fields = ["beneficiary__ben_code", "beneficiary__name"]
    ordering_fields = ["graduation_date", "last_contact", "created_at"]
    ordering = ["-created_at"]


class ProgressTrackingViewSet(CreatedByMixin, ModelViewSet):
    queryset = ProgressTracking.objects.select_related(
        "beneficiary", "program", "created_by"
    ).all()
    serializer_class = ProgressTrackingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["program", "current_phase"]
    search_fields = [
        "beneficiary__ben_code",
        "beneficiary__name",
        "current_phase",
        "next_milestone",
    ]
    ordering_fields = ["progress", "enrolled_date", "created_at"]
    ordering = ["-created_at"]
