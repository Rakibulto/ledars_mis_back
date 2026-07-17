from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Milestone, MilestoneTask
from projects.serializers.milestone_serializers import (
    MilestoneSerializer,
    MilestoneTaskSerializer,
)


class MilestoneViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = MilestoneSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "target_date", "status", "created_at"]
    ordering = ["target_date"]
    filterset_fields = ["space", "status"]

    def get_queryset(self):
        return (
            Milestone.objects.select_related("space")
            .prefetch_related("milestone_tasks__task__status__group")
            .all()
        )

    @action(detail=True, methods=["post"], url_path="add-task")
    @transaction.atomic
    def add_task(self, request, pk=None):
        milestone = self.get_object()
        task_id = request.data.get("task_id")
        if not task_id:
            return Response(
                {"detail": "task_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        mt, created = MilestoneTask.objects.get_or_create(
            milestone=milestone, task_id=task_id
        )
        if not created:
            return Response(
                {"detail": "Task already in milestone"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            MilestoneTaskSerializer(mt).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["delete"], url_path="remove-task/(?P<task_id>[^/.]+)")
    @transaction.atomic
    def remove_task(self, request, pk=None, task_id=None):
        milestone = self.get_object()
        deleted, _ = MilestoneTask.objects.filter(
            milestone=milestone, task_id=task_id
        ).delete()
        if not deleted:
            return Response(
                {"detail": "Task not in milestone"}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
