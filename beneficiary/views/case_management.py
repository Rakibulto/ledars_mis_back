from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from inventory.views import CreatedByMixin
from paginations import Pagination
from rest_framework.decorators import action
from beneficiary.models import CaseFile, ProtectionCase, ConsentRecord, SafeguardingIncident
from beneficiary.serializers import (
    CaseFileSerializer,
    ProtectionCaseSerializer,
    ConsentRecordSerializer,
    SafeguardingIncidentSerializer,
)
from beneficiary.filters import CaseFileFilter
from beneficiary.services import get_casefile_summary


class CaseFileViewSet(ModelViewSet):

    queryset = CaseFile.objects.select_related("beneficiary", "created_by").all()
    serializer_class = CaseFileSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CaseFileFilter
    search_fields = [
        "beneficiary__id",
        "beneficiary__ben_code",
        "case_type",
        "priority",
        "beneficiary__name",
        "next_follow_up",
        "case_worker__employee_name",
    ]
    ordering_fields = ["opened_date", "priority", "created_at"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"], url_path="summary")
    def case_summarty(self, request):
        stats = get_casefile_summary()
        return Response(stats)


class ProtectionCaseViewSet(CreatedByMixin, ModelViewSet):
    queryset = ProtectionCase.objects.select_related(
        "beneficiary", "case_worker", "created_by"
    ).all()
    serializer_class = ProtectionCaseSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["type", "risk_level", "status"]
    search_fields = ["reference", "beneficiary__name", "case_worker__employee_name"]
    ordering_fields = ["opened_date", "last_update", "created_at"]
    ordering = ["-created_at"]


class ConsentRecordViewSet(CreatedByMixin, ModelViewSet):
    queryset = ConsentRecord.objects.select_related("beneficiary", "created_by").all()
    serializer_class = ConsentRecordSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["consent_type", "granted", "data_sharing"]
    search_fields = ["beneficiary__ben_code", "beneficiary__name", "collected_by"]
    ordering_fields = ["date", "expiry", "created_at"]
    ordering = ["-created_at"]


class SafeguardingIncidentViewSet(CreatedByMixin, ModelViewSet):
    queryset = SafeguardingIncident.objects.select_related("created_by").all()
    serializer_class = SafeguardingIncidentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["severity", "status", "type"]
    search_fields = ["reference", "reporter", "investigation_lead", "location"]
    ordering_fields = ["date", "created_at"]
    ordering = ["-created_at"]
