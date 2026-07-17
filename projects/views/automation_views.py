from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Automation, AutomationAction, AutomationLog
from projects.serializers.automation_serializers import (
    AutomationSerializer,
    AutomationListSerializer,
    AutomationActionSerializer,
    AutomationLogSerializer,
)


class AutomationViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = AutomationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "trigger_type", "is_active", "runs", "created_at"]
    ordering = ["-created_at"]
    filterset_fields = ["space", "trigger_type", "is_active"]

    def get_queryset(self):
        return (
            Automation.objects.select_related("space").prefetch_related("actions").all()
        )

    def get_serializer_class(self):
        if self.action == "list":
            return AutomationListSerializer
        return AutomationSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        automation = serializer.save(created_by=self.request.user)
        # Create actions if provided
        actions_data = self.request.data.get("actions_data", [])
        for idx, act in enumerate(actions_data):
            AutomationAction.objects.create(
                automation=automation,
                action_type=act.get("action_type", "change_status"),
                action_config=act.get("action_config", {}),
                position=idx,
            )

    @action(detail=True, methods=["patch"], url_path="toggle")
    @transaction.atomic
    def toggle(self, request, pk=None):
        """Toggle automation active/inactive."""
        automation = self.get_object()
        automation.is_active = not automation.is_active
        automation.save(update_fields=["is_active"])
        return Response(AutomationSerializer(automation).data)

    @action(detail=True, methods=["get"], url_path="logs")
    def get_logs(self, request, pk=None):
        automation = self.get_object()
        logs = AutomationLog.objects.filter(automation=automation).order_by(
            "-executed_at"
        )[:50]
        return Response(AutomationLogSerializer(logs, many=True).data)


class AutomationActionViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = AutomationActionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["automation"]

    def get_queryset(self):
        return AutomationAction.objects.select_related("automation").all()


class AutomationLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AutomationLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["automation", "status"]

    def get_queryset(self):
        return AutomationLog.objects.select_related("automation", "task").all()
