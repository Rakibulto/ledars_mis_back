from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from inventory.views import CreatedByMixin
from paginations import Pagination
from rest_framework.decorators import action
from beneficiary.models import ComplaintsFeedback, GrievanceRedressal, SatisfactionSurvey
from beneficiary.serializers import (
    ComplaintsFeedbackSerializer,
    GrievanceRedressalSerializer,
    SatisfactionSurveySerializer,
)
from beneficiary.filters import ComplaintsFeedbackFilter
from beneficiary.services import get_complaints_feedback_summary


class ComplaintsFeedbackViewSet(CreatedByMixin, ModelViewSet):
    queryset = ComplaintsFeedback.objects.select_related(
        "beneficiary", "created_by"
    ).all()
    serializer_class = ComplaintsFeedbackSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ComplaintsFeedbackFilter
    search_fields = [
        "subject",
        "message",
        "beneficiary__ben_code",
        "beneficiary__name",
        "status",
        "priority",
    ]
    ordering_fields = ["created_at", "date"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        data = get_complaints_feedback_summary()
        return Response(data)


class GrievanceRedressalViewSet(CreatedByMixin, ModelViewSet):
    queryset = GrievanceRedressal.objects.select_related("created_by").all()
    serializer_class = GrievanceRedressalSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status", "type"]
    search_fields = ["reference", "complainant", "assigned_to", "description"]
    ordering_fields = ["date", "days_to_resolve", "created_at"]
    ordering = ["-created_at"]


class SatisfactionSurveyViewSet(CreatedByMixin, ModelViewSet):
    queryset = SatisfactionSurvey.objects.select_related("project", "created_by").order_by("-created_at")
    serializer_class = SatisfactionSurveySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status", "project"]
    search_fields = ["survey_name", "period"]
    ordering_fields = ["avg_satisfaction", "response_rate", "created_at"]
    ordering = ["-created_at"]
