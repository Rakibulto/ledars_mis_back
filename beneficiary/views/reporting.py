from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from inventory.views import CreatedByMixin
from paginations import Pagination
from beneficiary.models import (
    DonorReport,
    DuplicateRecord,
    AttendanceTracker,
    HouseholdSurvey,
    EligibilityScreening,
)
from beneficiary.serializers import (
    DonorReportSerializer,
    DuplicateRecordSerializer,
    DuplicateRecordSummarySerializer,
    AttendanceTrackerSerializer,
    HouseholdSurveySerializer,
    EligibilityScreeningSerializer,
)
from beneficiary.services import get_duplicate_record_summary


class DonorReportViewSet(CreatedByMixin, ModelViewSet):
    queryset = DonorReport.objects.select_related("project", "created_by").all()
    serializer_class = DonorReportSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status", "project"]
    search_fields = ["donor", "period"]
    ordering_fields = ["due_date", "achievement", "created_at"]
    ordering = ["-created_at"]


class DuplicateRecordViewSet(CreatedByMixin, ModelViewSet):
    queryset = DuplicateRecord.objects.select_related("created_by").all()
    serializer_class = DuplicateRecordSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status", "auto_detected"]
    search_fields = ["record_a", "record_b", "name_a", "name_b"]
    ordering_fields = ["similarity_score", "detected_date", "created_at"]
    ordering = ["-similarity_score"]

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        stats = get_duplicate_record_summary()
        serializer = DuplicateRecordSummarySerializer(stats)
        return Response(serializer.data)


class AttendanceTrackerViewSet(CreatedByMixin, ModelViewSet):
    queryset = AttendanceTracker.objects.select_related("project", "created_by").all()
    serializer_class = AttendanceTrackerSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["project"]
    search_fields = ["activity", "location", "facilitator"]
    ordering_fields = ["date", "attendance_rate", "created_at"]
    ordering = ["-date"]


class HouseholdSurveyViewSet(CreatedByMixin, ModelViewSet):
    queryset = HouseholdSurvey.objects.select_related("project", "created_by").order_by("-created_at")
    serializer_class = HouseholdSurveySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status", "project"]
    search_fields = ["reference", "survey_name"]
    ordering_fields = ["start_date", "completion_rate", "created_at"]
    ordering = ["-created_at"]


class EligibilityScreeningViewSet(CreatedByMixin, ModelViewSet):
    queryset = EligibilityScreening.objects.select_related(
        "program", "created_by"
    ).order_by("-created_at")
    serializer_class = EligibilityScreeningSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status", "eligible", "program"]
    search_fields = ["applicant", "nid", "screener"]
    ordering_fields = ["screening_date", "score", "created_at"]
    ordering = ["-created_at"]
