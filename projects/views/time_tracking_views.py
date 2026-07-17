from django.db import transaction
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import TimeEntry
from projects.serializers.time_tracking_serializers import TimeEntrySerializer


class TimeEntryViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = TimeEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["description"]
    ordering_fields = ["date", "duration", "created_at"]
    ordering = ["-created_at"]
    filterset_fields = ["task", "user", "is_billable", "is_running"]

    def get_queryset(self):
        qs = TimeEntry.objects.select_related("task", "user").all()

        # Date range filtering
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="start-timer")
    @transaction.atomic
    def start_timer(self, request):
        """Start a new timer on a task."""
        task_id = request.data.get("task_id")
        description = request.data.get("description", "")
        if not task_id:
            return Response(
                {"detail": "task_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Stop any running timers for this user
        TimeEntry.objects.filter(user=request.user, is_running=True).update(
            is_running=False,
            end_time=timezone.now(),
        )
        # Calculate duration for stopped entries
        for entry in TimeEntry.objects.filter(
            user=request.user, duration=0, end_time__isnull=False
        ):
            if entry.start_time and entry.end_time:
                entry.duration = int(
                    (entry.end_time - entry.start_time).total_seconds() / 60
                )
                entry.save(update_fields=["duration"])

        entry = TimeEntry.objects.create(
            task_id=task_id,
            user=request.user,
            description=description,
            start_time=timezone.now(),
            date=timezone.now().date(),
            is_running=True,
        )
        return Response(TimeEntrySerializer(entry).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="stop-timer")
    @transaction.atomic
    def stop_timer(self, request):
        """Stop the currently running timer."""
        entry = TimeEntry.objects.filter(user=request.user, is_running=True).first()
        if not entry:
            return Response(
                {"detail": "No running timer"}, status=status.HTTP_404_NOT_FOUND
            )

        entry.end_time = timezone.now()
        entry.is_running = False
        if entry.start_time:
            entry.duration = int(
                (entry.end_time - entry.start_time).total_seconds() / 60
            )
        entry.save()
        return Response(TimeEntrySerializer(entry).data)

    @action(detail=False, methods=["get"], url_path="my-entries")
    def my_entries(self, request):
        """Get time entries for the current user."""
        entries = self.get_queryset().filter(user=request.user)
        page = self.paginate_queryset(entries)
        if page is not None:
            serializer = TimeEntrySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(TimeEntrySerializer(entries, many=True).data)

    @action(detail=False, methods=["get"], url_path="timesheets")
    def timesheets(self, request):
        """Aggregated timesheet data grouped by user and date."""
        qs = self.get_queryset()
        data = (
            qs.values("user__id", "user__username", "user__email", "date")
            .annotate(
                total_duration=Sum("duration"),
                entries_count=Count("id"),
                total_cost=Sum(F("duration") * F("hourly_rate") / 60.0),
            )
            .order_by("date", "user__id")
        )
        result = [
            {
                "user_id": d["user__id"],
                "user_name": d["user__username"] or d["user__email"],
                "date": d["date"],
                "total_duration": d["total_duration"] or 0,
                "entries_count": d["entries_count"],
                "total_cost": float(d["total_cost"] or 0),
            }
            for d in data
        ]
        return Response(result)

    @action(detail=False, methods=["get"], url_path="reports")
    def reports(self, request):
        """Time tracking summary reports."""
        qs = self.get_queryset()
        total_duration = qs.aggregate(total=Sum("duration"))["total"] or 0
        billable = (
            qs.filter(is_billable=True).aggregate(total=Sum("duration"))["total"] or 0
        )
        non_billable = total_duration - billable

        by_user = list(
            qs.values("user__id", "user__username", "user__email")
            .annotate(total_duration=Sum("duration"), entries_count=Count("id"))
            .order_by("-total_duration")
        )

        return Response(
            {
                "total_duration": total_duration,
                "billable_duration": billable,
                "non_billable_duration": non_billable,
                "by_user": [
                    {
                        "user_id": u["user__id"],
                        "user_name": u["user__username"] or u["user__email"],
                        "total_duration": u["total_duration"],
                        "entries_count": u["entries_count"],
                    }
                    for u in by_user
                ],
            }
        )

    @action(detail=False, methods=["get"], url_path="workload")
    def workload(self, request):
        """Workload analysis per team member."""
        from projects.models import TaskAssignee, Task

        users_data = []
        # Get unique users with time entries or task assignments
        user_ids = set()
        user_ids.update(TimeEntry.objects.values_list("user_id", flat=True).distinct())
        user_ids.update(
            TaskAssignee.objects.values_list("user_id", flat=True).distinct()
        )

        from authentication.models import User

        for uid in user_ids:
            try:
                user = User.objects.get(id=uid)
            except User.DoesNotExist:
                continue

            assigned_tasks = TaskAssignee.objects.filter(user=user).count()
            completed_tasks = TaskAssignee.objects.filter(
                user=user, task__completed_at__isnull=False
            ).count()
            total_hours = (
                TimeEntry.objects.filter(user=user).aggregate(total=Sum("duration"))[
                    "total"
                ]
                or 0
            ) / 60

            # Weekly capacity = 40 hours
            utilization = min(100, int((total_hours / 40) * 100)) if total_hours else 0

            users_data.append(
                {
                    "user_id": user.id,
                    "user_name": user.username or user.email,
                    "assigned_tasks": assigned_tasks,
                    "completed_tasks": completed_tasks,
                    "total_hours": round(total_hours, 1),
                    "utilization": utilization,
                }
            )

        return Response(users_data)
