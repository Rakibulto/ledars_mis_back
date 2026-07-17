from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from inventory.views import CreatedByMixin
from paginations import Pagination
from beneficiary.models import (
    TargetingCriteria,
    DistributionPlan,
    ServiceCalendarEvent,
    CaseWorkerAssignment,
    FollowUpSchedule,
)
from beneficiary.serializers import (
    TargetingCriteriaSerializer,
    DistributionPlanSerializer,
    ServiceCalendarEventSerializer,
    CaseWorkerAssignmentSerializer,
    FollowUpScheduleSerializer,
)


class TargetingCriteriaViewSet(CreatedByMixin, ModelViewSet):
    queryset = TargetingCriteria.objects.select_related("program", "created_by").all()
    serializer_class = TargetingCriteriaSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status", "type", "program"]
    search_fields = ["criterion", "measurement"]
    ordering_fields = ["weight", "created_at"]
    ordering = ["-created_at"]


class DistributionPlanViewSet(CreatedByMixin, ModelViewSet):
    queryset = DistributionPlan.objects.select_related("project", "created_by").all()
    serializer_class = DistributionPlanSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status", "project"]
    search_fields = ["reference", "name", "location", "coordinator"]
    ordering_fields = ["date", "created_at"]
    ordering = ["-created_at"]


class ServiceCalendarEventViewSet(CreatedByMixin, ModelViewSet):
    queryset = ServiceCalendarEvent.objects.select_related("created_by").all()
    serializer_class = ServiceCalendarEventSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status", "type"]
    search_fields = ["title", "location"]
    ordering_fields = ["date", "created_at"]
    ordering = ["-date"]


class CaseWorkerAssignmentViewSet(CreatedByMixin, ModelViewSet):
    queryset = CaseWorkerAssignment.objects.select_related(
        "case_worker", "created_by"
    ).all()
    serializer_class = CaseWorkerAssignmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["specialization"]
    search_fields = ["case_worker__employee_name", "area", "designation"]
    ordering_fields = ["active_cases", "created_at"]
    ordering = ["-created_at"]


class FollowUpScheduleViewSet(CreatedByMixin, ModelViewSet):
    queryset = FollowUpSchedule.objects.select_related(
        "beneficiary", "case_worker", "created_by"
    ).all()
    serializer_class = FollowUpScheduleSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status", "priority", "type"]
    search_fields = [
        "beneficiary__ben_code",
        "beneficiary__name",
        "case_worker__employee_name",
        "purpose",
    ]
    ordering_fields = ["follow_up_date", "created_at"]
    ordering = ["follow_up_date"]
