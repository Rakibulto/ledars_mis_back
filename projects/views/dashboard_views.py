from django.db import models
from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Dashboard, DashboardWidget, Task, Sprint, TimeEntry, Project


class DashboardViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        return Dashboard.objects.prefetch_related("widgets").all()

    def get_serializer_class(self):
        from projects.serializers.dashboard_serializers import DashboardSerializer

        return DashboardSerializer


class DashboardWidgetViewSet(CreatedByMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["dashboard"]

    def get_queryset(self):
        return DashboardWidget.objects.select_related("dashboard").all()

    def get_serializer_class(self):
        from projects.serializers.dashboard_serializers import DashboardWidgetSerializer

        return DashboardWidgetSerializer


class PMDashboardStatsView(viewsets.ViewSet):
    """ClickUp-style project management dashboard stats."""

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):
        now = timezone.now()
        today = now.date()

        tasks = Task.objects.all()
        total_tasks = tasks.count()
        completed_tasks = tasks.filter(completed_at__isnull=False).count()
        overdue_tasks = tasks.filter(
            due_date__lt=today, completed_at__isnull=True
        ).count()
        in_progress_tasks = tasks.filter(
            status__group__label__in=["active", "in_progress"]
        ).count()

        # Tasks by priority
        by_priority = list(
            tasks.values("priority").annotate(count=Count("id")).order_by("priority")
        )

        # Tasks by status group
        by_status = list(
            tasks.values(
                status_group=F("status__group__label"),
                status_name=F("status__name"),
                status_color=F("status__color"),
            )
            .annotate(count=Count("id"))
            .order_by("status__group__position")
        )

        # Recent activity
        recent_tasks = list(
            tasks.order_by("-created_at")[:10].values(
                "id",
                "task_id",
                "title",
                "priority",
                "created_at",
                status_name=F("status__name"),
                status_color=F("status__color"),
            )
        )

        # Sprint stats
        active_sprint = Sprint.objects.filter(status="active").first()
        sprint_data = None
        if active_sprint:
            sprint_tasks = active_sprint.tasks.all()
            sprint_data = {
                "id": active_sprint.id,
                "name": active_sprint.name,
                "start_date": active_sprint.start_date,
                "end_date": active_sprint.end_date,
                "total_tasks": sprint_tasks.count(),
                "completed_tasks": sprint_tasks.filter(
                    completed_at__isnull=False
                ).count(),
                "total_points": sprint_tasks.aggregate(total=Sum("story_points"))[
                    "total"
                ]
                or 0,
                "completed_points": sprint_tasks.filter(
                    completed_at__isnull=False
                ).aggregate(total=Sum("story_points"))["total"]
                or 0,
            }

        # Projects summary
        projects = Project.objects.all()
        projects_data = {
            "total": projects.count(),
            "active": projects.filter(status="Active").count(),
            "completed": projects.filter(status="Completed").count(),
        }

        # Time tracking (this week)
        week_start = today - timezone.timedelta(days=today.weekday())
        weekly_hours = (
            TimeEntry.objects.filter(date__gte=week_start, date__lte=today).aggregate(
                total=Sum("duration")
            )["total"]
            or 0
        )

        return Response(
            {
                "tasks": {
                    "total": total_tasks,
                    "completed": completed_tasks,
                    "in_progress": in_progress_tasks,
                    "overdue": overdue_tasks,
                    "completion_rate": (
                        round(completed_tasks / total_tasks * 100, 1)
                        if total_tasks
                        else 0
                    ),
                },
                "by_priority": by_priority,
                "by_status": by_status,
                "recent_tasks": recent_tasks,
                "active_sprint": sprint_data,
                "projects": projects_data,
                "weekly_hours": round(weekly_hours / 60, 1) if weekly_hours else 0,
            }
        )

    @action(detail=False, methods=["get"], url_path="workload")
    def workload(self, request):
        from authentication.models import User

        users = User.objects.all()
        workload_data = []
        for user in users:
            assigned_tasks = Task.objects.filter(
                task_assignees__user=user, completed_at__isnull=True
            )
            completed = Task.objects.filter(
                task_assignees__user=user, completed_at__isnull=False
            ).count()
            workload_data.append(
                {
                    "user_id": user.id,
                    "user_name": user.username or user.email,
                    "assigned": assigned_tasks.count(),
                    "completed": completed,
                    "overdue": assigned_tasks.filter(
                        due_date__lt=timezone.now().date()
                    ).count(),
                    "by_priority": list(
                        assigned_tasks.values("priority").annotate(count=Count("id"))
                    ),
                }
            )

        return Response(workload_data)
