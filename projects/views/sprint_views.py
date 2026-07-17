from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Sprint, SprintTask, Task
from projects.serializers.sprint_serializers import (
    SprintSerializer,
    SprintListSerializer,
    SprintTaskSerializer,
)


class SprintViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = SprintSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "goal"]
    ordering_fields = ["name", "start_date", "end_date", "status", "created_at"]
    ordering = ["-created_at"]
    filterset_fields = ["space", "status"]

    def get_queryset(self):
        return (
            Sprint.objects.select_related("space")
            .prefetch_related(
                "sprint_tasks__task__status__group",
                "sprint_tasks__task__task_assignees__user",
            )
            .all()
        )

    def get_serializer_class(self):
        if self.action == "list":
            return SprintListSerializer
        return SprintSerializer

    @action(detail=True, methods=["patch"], url_path="start")
    @transaction.atomic
    def start_sprint(self, request, pk=None):
        """Start a sprint — only one active sprint per space."""
        sprint = self.get_object()
        # Deactivate any currently active sprint in same space
        Sprint.objects.filter(space=sprint.space, status="active").update(
            status="completed"
        )
        sprint.status = "active"
        if not sprint.start_date:
            sprint.start_date = timezone.now().date()
        sprint.save()
        return Response(SprintSerializer(sprint).data)

    @action(detail=True, methods=["patch"], url_path="complete")
    @transaction.atomic
    def complete_sprint(self, request, pk=None):
        sprint = self.get_object()
        sprint.status = "completed"
        if not sprint.end_date:
            sprint.end_date = timezone.now().date()
        # Calculate velocity
        completed_points = sum(
            st.task.story_points
            for st in sprint.sprint_tasks.select_related("task").filter(
                task__status__group__name="done"
            )
        )
        sprint.velocity = completed_points
        sprint.save()
        return Response(SprintSerializer(sprint).data)

    @action(detail=True, methods=["post"], url_path="add-task")
    @transaction.atomic
    def add_task(self, request, pk=None):
        sprint = self.get_object()
        task_id = request.data.get("task_id")
        if not task_id:
            return Response(
                {"detail": "task_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        st, created = SprintTask.objects.get_or_create(sprint=sprint, task_id=task_id)
        if not created:
            return Response(
                {"detail": "Task already in sprint"}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(SprintTaskSerializer(st).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path="remove-task/(?P<task_id>[^/.]+)")
    @transaction.atomic
    def remove_task(self, request, pk=None, task_id=None):
        sprint = self.get_object()
        deleted, _ = SprintTask.objects.filter(sprint=sprint, task_id=task_id).delete()
        if not deleted:
            return Response(
                {"detail": "Task not in sprint"}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="burndown")
    def burndown(self, request, pk=None):
        """Get burndown chart data for a sprint."""
        sprint = self.get_object()
        if not sprint.start_date or not sprint.end_date:
            return Response(
                {"detail": "Sprint needs start and end dates"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_points = sum(
            st.task.story_points
            for st in sprint.sprint_tasks.select_related("task").all()
        )

        from datetime import timedelta

        data = []
        current = sprint.start_date
        while current <= sprint.end_date:
            completed = sum(
                st.task.story_points
                for st in sprint.sprint_tasks.select_related("task").filter(
                    task__completed_at__date__lte=current
                )
            )
            data.append(
                {
                    "date": current.isoformat(),
                    "ideal": max(
                        0,
                        total_points
                        - (
                            total_points
                            * (current - sprint.start_date).days
                            / max((sprint.end_date - sprint.start_date).days, 1)
                        ),
                    ),
                    "actual": total_points - completed,
                }
            )
            current += timedelta(days=1)

        return Response({"total_points": total_points, "burndown": data})

    @action(detail=True, methods=["patch"], url_path="retrospective")
    @transaction.atomic
    def retrospective(self, request, pk=None):
        sprint = self.get_object()
        sprint.went_well = request.data.get("went_well", sprint.went_well)
        sprint.to_improve = request.data.get("to_improve", sprint.to_improve)
        sprint.action_items = request.data.get("action_items", sprint.action_items)
        sprint.save()
        return Response(SprintSerializer(sprint).data)


class SprintTaskViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = SprintTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["sprint"]

    def get_queryset(self):
        return (
            SprintTask.objects.select_related(
                "sprint", "task", "task__status", "task__status__group"
            )
            .prefetch_related("task__task_assignees__user")
            .all()
        )
