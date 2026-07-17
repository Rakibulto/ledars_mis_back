from django.db import transaction
from django.db.models import Q, Count, Case, When, IntegerField
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import (
    Task,
    TaskAssignee,
    TaskWatcher,
    TaskDependency,
    Subtask,
    Checklist,
    ChecklistItem,
    TaskAttachment,
    TaskComment,
    TaskActivityLog,
    TaskTag,
    Tag,
)
from projects.serializers.task_serializers import (
    TaskListSerializer,
    TaskDetailSerializer,
    TaskAssigneeSerializer,
    TaskWatcherSerializer,
    TaskDependencySerializer,
    SubtaskSerializer,
    ChecklistSerializer,
    ChecklistItemSerializer,
    TaskAttachmentSerializer,
    TaskCommentSerializer,
    TaskActivityLogSerializer,
)


class TaskViewSet(CreatedByMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "description", "task_id"]
    ordering_fields = [
        "title",
        "priority",
        "due_date",
        "status",
        "story_points",
        "position",
        "created_at",
    ]
    ordering = ["position", "-created_at"]
    filterset_fields = ["list", "status", "priority", "is_recurring", "parent"]

    def get_queryset(self):
        qs = (
            Task.objects.select_related(
                "list",
                "list__space",
                "status",
                "status__group",
                "parent",
                "created_by",
                "updated_by",
            )
            .prefetch_related(
                "task_assignees__user",
                "task_watchers__user",
                "task_tags__tag",
                "checklists__items",
                "comments",
                "attachments",
                "activity_logs",
                "children",
                "dependencies_from__depends_on",
            )
            .all()
        )

        # Filter by space
        space_id = self.request.query_params.get("space")
        if space_id:
            qs = qs.filter(list__space_id=space_id)

        # Filter by assignee
        assignee_id = self.request.query_params.get("assignee")
        if assignee_id:
            qs = qs.filter(task_assignees__user_id=assignee_id)

        # Filter by tag
        tag_id = self.request.query_params.get("tag")
        if tag_id:
            qs = qs.filter(task_tags__tag_id=tag_id)

        # Filter by due date range
        due_from = self.request.query_params.get("due_from")
        due_to = self.request.query_params.get("due_to")
        if due_from:
            qs = qs.filter(due_date__gte=due_from)
        if due_to:
            qs = qs.filter(due_date__lte=due_to)

        # Filter overdue
        overdue = self.request.query_params.get("overdue")
        if overdue == "true":
            qs = qs.filter(due_date__lt=timezone.now(), completed_at__isnull=True)

        # Filter by group_by=status for board view
        group_by = self.request.query_params.get("group_by")
        if group_by == "status":
            qs = qs.order_by("status__position", "position")
        elif group_by == "priority":
            priority_order = Case(
                When(priority="urgent", then=0),
                When(priority="high", then=1),
                When(priority="normal", then=2),
                When(priority="low", then=3),
                When(priority="none", then=4),
                output_field=IntegerField(),
            )
            qs = qs.annotate(priority_order=priority_order).order_by(
                "priority_order", "position"
            )

        return qs.distinct()

    def get_serializer_class(self):
        if self.action == "list":
            return TaskListSerializer
        return TaskDetailSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        # Trigger automations
        from projects.services.automation_engine import trigger_automation

        task = serializer.instance
        trigger_automation("task_created", task, self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        old_status = serializer.instance.status
        old_priority = serializer.instance.priority
        serializer.save(updated_by=self.request.user)
        task = serializer.instance

        # Trigger status change automation
        if old_status != task.status:
            from projects.services.automation_engine import trigger_automation

            trigger_automation(
                "status_changed",
                task,
                self.request.user,
                {
                    "old_status": old_status.id if old_status else None,
                    "new_status": task.status.id if task.status else None,
                },
            )
            # Auto-set completed_at
            if task.status and task.status.group and task.status.group.name == "done":
                task.completed_at = timezone.now()
                task.save(update_fields=["completed_at"])
            elif task.completed_at:
                task.completed_at = None
                task.save(update_fields=["completed_at"])

        # Trigger priority change automation
        if old_priority != task.priority:
            from projects.services.automation_engine import trigger_automation

            trigger_automation(
                "priority_changed",
                task,
                self.request.user,
                {
                    "old_priority": old_priority,
                    "new_priority": task.priority,
                },
            )

    # -- Board position update (drag & drop) --
    @action(detail=True, methods=["patch"], url_path="move")
    @transaction.atomic
    def move(self, request, pk=None):
        """Move task to a new list/status/position (board drag-drop)."""
        task = self.get_object()
        new_list_id = request.data.get("list_id")
        new_status_id = request.data.get("status_id")
        new_position = request.data.get("position")

        if new_list_id is not None:
            old_list = task.list_id
            task.list_id = new_list_id
            if old_list != int(new_list_id):
                TaskActivityLog.objects.create(
                    task=task,
                    user=request.user,
                    action="moved",
                    field="list",
                    old_value=str(old_list),
                    new_value=str(new_list_id),
                )
                from projects.services.automation_engine import trigger_automation

                trigger_automation(
                    "moved_to_list", task, request.user, {"list_id": new_list_id}
                )

        if new_status_id is not None:
            old_status = task.status_id
            task.status_id = new_status_id
            if old_status != int(new_status_id):
                TaskActivityLog.objects.create(
                    task=task,
                    user=request.user,
                    action="status_changed",
                    field="status",
                    old_value=str(old_status),
                    new_value=str(new_status_id),
                )
                from projects.services.automation_engine import trigger_automation

                trigger_automation(
                    "status_changed",
                    task,
                    request.user,
                    {
                        "old_status": old_status,
                        "new_status": new_status_id,
                    },
                )

        if new_position is not None:
            task.position = new_position

        task.save()
        return Response(TaskListSerializer(task).data)

    # -- Bulk operations --
    @action(detail=False, methods=["post"], url_path="bulk-update")
    @transaction.atomic
    def bulk_update(self, request):
        """Bulk update tasks (mark done, set priority, delete)."""
        task_ids = request.data.get("task_ids", [])
        action_type = request.data.get("action")

        if not task_ids or not action_type:
            return Response(
                {"detail": "task_ids and action are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tasks = Task.objects.filter(id__in=task_ids)

        if action_type == "delete":
            count = tasks.count()
            tasks.delete()
            return Response({"deleted": count})

        elif action_type == "set_status":
            status_id = request.data.get("status_id")
            tasks.update(status_id=status_id, updated_by=request.user)

        elif action_type == "set_priority":
            priority = request.data.get("priority")
            tasks.update(priority=priority, updated_by=request.user)

        elif action_type == "mark_done":
            from projects.models import Status

            done_status = Status.objects.filter(group__name="done").first()
            if done_status:
                tasks.update(
                    status=done_status,
                    completed_at=timezone.now(),
                    updated_by=request.user,
                )

        return Response({"updated": tasks.count()})

    # -- Quick add (board column) --
    @action(detail=False, methods=["post"], url_path="quick-add")
    @transaction.atomic
    def quick_add(self, request):
        """Quick-add task from board column."""
        title = request.data.get("title")
        list_id = request.data.get("list_id")
        status_id = request.data.get("status_id")

        if not title or not list_id:
            return Response(
                {"detail": "title and list_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task = Task.objects.create(
            title=title,
            list_id=list_id,
            status_id=status_id,
            created_by=request.user,
        )
        TaskActivityLog.objects.create(task=task, user=request.user, action="created")

        from projects.services.automation_engine import trigger_automation

        trigger_automation("task_created", task, request.user)

        return Response(TaskListSerializer(task).data, status=status.HTTP_201_CREATED)

    # -- My tasks --
    @action(detail=False, methods=["get"], url_path="my-tasks")
    def my_tasks(self, request):
        """Get tasks assigned to the current user."""
        tasks = self.get_queryset().filter(task_assignees__user=request.user).distinct()
        page = self.paginate_queryset(tasks)
        if page is not None:
            serializer = TaskListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(TaskListSerializer(tasks, many=True).data)

    # -- Stats --
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        qs = self.get_queryset()
        total = qs.count()
        by_priority = {
            p: qs.filter(priority=p).count()
            for p in ["urgent", "high", "normal", "low", "none"]
        }
        overdue = qs.filter(
            due_date__lt=timezone.now(), completed_at__isnull=True
        ).count()
        completed = qs.filter(completed_at__isnull=False).count()
        return Response(
            {
                "total": total,
                "completed": completed,
                "overdue": overdue,
                "by_priority": by_priority,
            }
        )


# --- Sub-resource ViewSets ---


class TaskAssigneeViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = TaskAssigneeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["task"]

    def get_queryset(self):
        return TaskAssignee.objects.select_related("user", "task").all()

    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save()
        TaskActivityLog.objects.create(
            task=obj.task,
            user=self.request.user,
            action="assigned",
            new_value=obj.user.username or obj.user.email,
        )
        from projects.services.automation_engine import trigger_automation

        trigger_automation(
            "task_assigned", obj.task, self.request.user, {"assignee_id": obj.user.id}
        )


class TaskWatcherViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = TaskWatcherSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["task"]

    def get_queryset(self):
        return TaskWatcher.objects.select_related("user", "task").all()


class TaskDependencyViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = TaskDependencySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["task"]

    def get_queryset(self):
        return TaskDependency.objects.select_related("task", "depends_on").all()

    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save()
        TaskActivityLog.objects.create(
            task=obj.task,
            user=self.request.user,
            action="dependency_added",
            new_value=obj.depends_on.task_id,
        )


class SubtaskViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = SubtaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["task"]

    def get_queryset(self):
        return Subtask.objects.select_related("task", "assignee").all()


class ChecklistViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = ChecklistSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["task"]

    def get_queryset(self):
        return Checklist.objects.select_related("task").prefetch_related("items").all()


class ChecklistItemViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = ChecklistItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["checklist"]

    def get_queryset(self):
        return ChecklistItem.objects.select_related("checklist", "assignee").all()

    @action(detail=True, methods=["patch"], url_path="toggle")
    @transaction.atomic
    def toggle(self, request, pk=None):
        item = self.get_object()
        item.is_done = not item.is_done
        item.save(update_fields=["is_done"])
        return Response(ChecklistItemSerializer(item).data)


class TaskAttachmentViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = TaskAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["task"]

    def get_queryset(self):
        return TaskAttachment.objects.select_related("task", "uploaded_by").all()

    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save(uploaded_by=self.request.user)
        TaskActivityLog.objects.create(
            task=obj.task,
            user=self.request.user,
            action="attachment_added",
            new_value=obj.file_name,
        )


class TaskCommentViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = TaskCommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["task"]

    def get_queryset(self):
        return (
            TaskComment.objects.select_related("user", "task")
            .prefetch_related("replies")
            .all()
        )

    @transaction.atomic
    def perform_create(self, serializer):
        comment = serializer.save(user=self.request.user)
        TaskActivityLog.objects.create(
            task=comment.task,
            user=self.request.user,
            action="comment_added",
        )
        from projects.services.automation_engine import trigger_automation

        trigger_automation("comment_added", comment.task, self.request.user)


class TaskActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TaskActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["task", "action"]

    def get_queryset(self):
        return TaskActivityLog.objects.select_related("user", "task").all()
