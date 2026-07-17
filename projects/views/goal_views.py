from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Goal, KeyResult
from projects.serializers.goal_serializers import (
    GoalSerializer,
    GoalListSerializer,
    KeyResultSerializer,
)


class GoalViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = GoalSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "start_date", "end_date", "status", "created_at"]
    ordering = ["-created_at"]
    filterset_fields = ["goal_type", "status", "owner"]

    def get_queryset(self):
        return (
            Goal.objects.select_related("owner").prefetch_related("key_results").all()
        )

    def get_serializer_class(self):
        if self.action == "list":
            return GoalListSerializer
        return GoalSerializer

    @action(detail=True, methods=["patch"], url_path="update-progress")
    @transaction.atomic
    def update_progress(self, request, pk=None):
        goal = self.get_object()
        current_value = request.data.get("current_value")
        if current_value is not None:
            goal.current_value = current_value
            # Auto-update status
            progress = goal.progress
            if progress >= 100:
                goal.status = "completed"
            elif progress >= 70:
                goal.status = "on_track"
            elif progress >= 40:
                goal.status = "at_risk"
            else:
                goal.status = "behind"
            goal.save()
        return Response(GoalSerializer(goal).data)


class KeyResultViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = KeyResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["goal"]

    def get_queryset(self):
        return KeyResult.objects.select_related("goal").all()

    @action(detail=True, methods=["patch"], url_path="update-progress")
    @transaction.atomic
    def update_progress(self, request, pk=None):
        kr = self.get_object()
        current = request.data.get("current")
        if current is not None:
            kr.current = current
            kr.save()
            # Recalc parent goal current_value as average of key results
            goal = kr.goal
            key_results = goal.key_results.all()
            if key_results.exists():
                avg_progress = (
                    sum(k.progress for k in key_results) / key_results.count()
                )
                goal.current_value = (avg_progress / 100) * float(goal.target_value)
                goal.save()
        return Response(KeyResultSerializer(kr).data)
