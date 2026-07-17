from django.db import transaction
from rest_framework import serializers
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
)


class TaskAssigneeSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = TaskAssignee
        fields = "__all__"

    def get_user_name(self, obj):
        return obj.user.username or obj.user.email if obj.user else None

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None


class TaskWatcherSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskWatcher
        fields = "__all__"

    def get_user_name(self, obj):
        return obj.user.username or obj.user.email if obj.user else None


class TaskDependencySerializer(serializers.ModelSerializer):
    depends_on_title = serializers.CharField(source="depends_on.title", read_only=True)
    depends_on_task_id = serializers.CharField(
        source="depends_on.task_id", read_only=True
    )

    class Meta:
        model = TaskDependency
        fields = "__all__"


class SubtaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.SerializerMethodField()

    class Meta:
        model = Subtask
        fields = "__all__"

    def get_assignee_name(self, obj):
        if obj.assignee:
            return obj.assignee.username or obj.assignee.email
        return None


class ChecklistItemSerializer(serializers.ModelSerializer):
    assignee_name = serializers.SerializerMethodField()

    class Meta:
        model = ChecklistItem
        fields = "__all__"

    def get_assignee_name(self, obj):
        if obj.assignee:
            return obj.assignee.username or obj.assignee.email
        return None


class ChecklistSerializer(serializers.ModelSerializer):
    items = ChecklistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Checklist
        fields = "__all__"


class TaskAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskAttachment
        fields = "__all__"
        read_only_fields = ["uploaded_by", "uploaded_at"]

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.username or obj.uploaded_by.email
        return None


class TaskCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = TaskComment
        fields = "__all__"
        read_only_fields = ["user", "created_at", "updated_at"]

    def get_user_name(self, obj):
        if obj.user:
            return obj.user.username or obj.user.email
        return None

    def get_replies(self, obj):
        if obj.parent is None:
            replies = obj.replies.all()
            return TaskCommentSerializer(replies, many=True).data
        return []


class TaskActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskActivityLog
        fields = "__all__"

    def get_user_name(self, obj):
        if obj.user:
            return obj.user.username or obj.user.email
        return None


class TaskTagInlineSerializer(serializers.ModelSerializer):
    tag_name = serializers.CharField(source="tag.name", read_only=True)
    tag_color = serializers.CharField(source="tag.color", read_only=True)

    class Meta:
        model = TaskTag
        fields = ["id", "tag", "tag_name", "tag_color"]


class TaskListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list/board views."""

    assignees = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    status_name = serializers.CharField(source="status.name", read_only=True)
    status_color = serializers.CharField(source="status.color", read_only=True)
    list_name = serializers.CharField(source="list.name", read_only=True)
    subtask_count = serializers.IntegerField(read_only=True)
    subtask_done = serializers.IntegerField(read_only=True)
    checklist_count = serializers.IntegerField(read_only=True)
    checklist_done = serializers.IntegerField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    attachment_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "task_id",
            "title",
            "description",
            "list",
            "list_name",
            "status",
            "status_name",
            "status_color",
            "priority",
            "assignees",
            "tags",
            "start_date",
            "due_date",
            "completed_at",
            "time_estimate",
            "story_points",
            "position",
            "parent",
            "is_recurring",
            "subtask_count",
            "subtask_done",
            "checklist_count",
            "checklist_done",
            "comment_count",
            "attachment_count",
            "created_at",
            "updated_at",
        ]

    def get_assignees(self, obj):
        return [
            {
                "id": ta.user.id,
                "name": ta.user.username or ta.user.email,
                "email": ta.user.email,
            }
            for ta in obj.task_assignees.select_related("user").all()
        ]

    def get_tags(self, obj):
        return [
            {"id": tt.tag.id, "name": tt.tag.name, "color": tt.tag.color}
            for tt in obj.task_tags.select_related("tag").all()
        ]


class TaskDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer with nested relations."""

    assignees = serializers.SerializerMethodField()
    watchers = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    dependencies = TaskDependencySerializer(
        source="dependencies_from", many=True, read_only=True
    )
    checklists = ChecklistSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    activity_logs = TaskActivityLogSerializer(many=True, read_only=True)
    attachments = TaskAttachmentSerializer(many=True, read_only=True)
    subtasks = SubtaskSerializer(many=True, read_only=True)

    status_name = serializers.CharField(source="status.name", read_only=True)
    status_color = serializers.CharField(source="status.color", read_only=True)
    list_name = serializers.CharField(source="list.name", read_only=True)
    space_name = serializers.CharField(source="list.space.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    subtask_count = serializers.IntegerField(read_only=True)
    subtask_done = serializers.IntegerField(read_only=True)
    checklist_count = serializers.IntegerField(read_only=True)
    checklist_done = serializers.IntegerField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    attachment_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Task
        fields = "__all__"
        read_only_fields = [
            "task_id",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None

    def get_assignees(self, obj):
        return [
            {
                "id": ta.user.id,
                "name": ta.user.username or ta.user.email,
                "email": ta.user.email,
            }
            for ta in obj.task_assignees.select_related("user").all()
        ]

    def get_watchers(self, obj):
        return [
            {
                "id": tw.user.id,
                "name": tw.user.username or tw.user.email,
                "email": tw.user.email,
            }
            for tw in obj.task_watchers.select_related("user").all()
        ]

    def get_tags(self, obj):
        return [
            {"id": tt.tag.id, "name": tt.tag.name, "color": tt.tag.color}
            for tt in obj.task_tags.select_related("tag").all()
        ]

    def get_comments(self, obj):
        top_level = obj.comments.filter(parent__isnull=True)
        return TaskCommentSerializer(top_level, many=True).data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        assignee_ids = request.data.get("assignee_ids", []) if request else []
        watcher_ids = request.data.get("watcher_ids", []) if request else []
        tag_ids = request.data.get("tag_ids", []) if request else []
        dependency_data = request.data.get("dependencies", []) if request else []
        subtask_data = request.data.get("subtasks_data", []) if request else []
        checklist_data = request.data.get("checklists_data", []) if request else []

        task = Task.objects.create(**validated_data)

        # Assignees
        for uid in assignee_ids:
            TaskAssignee.objects.create(task=task, user_id=uid)

        # Watchers
        for uid in watcher_ids:
            TaskWatcher.objects.create(task=task, user_id=uid)

        # Tags
        from projects.models import TaskTag

        for tid in tag_ids:
            TaskTag.objects.create(task=task, tag_id=tid)

        # Dependencies
        for dep in dependency_data:
            TaskDependency.objects.create(
                task=task,
                depends_on_id=dep.get("depends_on"),
                dependency_type=dep.get("dependency_type", "blocking"),
            )

        # Subtasks
        for idx, st in enumerate(subtask_data):
            Subtask.objects.create(task=task, title=st.get("title", ""), position=idx)

        # Checklists
        for cl_data in checklist_data:
            cl = Checklist.objects.create(
                task=task, name=cl_data.get("name", "Checklist")
            )
            for idx, item in enumerate(cl_data.get("items", [])):
                ChecklistItem.objects.create(
                    checklist=cl, text=item.get("text", ""), position=idx
                )

        # Activity log
        if request and request.user.is_authenticated:
            TaskActivityLog.objects.create(
                task=task, user=request.user, action="created"
            )

        return task

    @transaction.atomic
    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None

        # Track changes for activity log
        tracked_fields = ["title", "priority", "status", "due_date", "description"]
        changes = []
        for field in tracked_fields:
            if field in validated_data:
                old_val = getattr(instance, field)
                new_val = validated_data[field]
                if old_val != new_val:
                    old_display = (
                        str(old_val.name) if hasattr(old_val, "name") else str(old_val)
                    )
                    new_display = (
                        str(new_val.name) if hasattr(new_val, "name") else str(new_val)
                    )
                    changes.append((field, old_display, new_display))

        instance = super().update(instance, validated_data)

        # Assignees
        assignee_ids = request.data.get("assignee_ids") if request else None
        if assignee_ids is not None:
            instance.task_assignees.all().delete()
            for uid in assignee_ids:
                TaskAssignee.objects.create(task=instance, user_id=uid)

        # Watchers
        watcher_ids = request.data.get("watcher_ids") if request else None
        if watcher_ids is not None:
            instance.task_watchers.all().delete()
            for uid in watcher_ids:
                TaskWatcher.objects.create(task=instance, user_id=uid)

        # Tags
        tag_ids = request.data.get("tag_ids") if request else None
        if tag_ids is not None:
            instance.task_tags.all().delete()
            from projects.models import TaskTag

            for tid in tag_ids:
                TaskTag.objects.create(task=instance, tag_id=tid)

        # Log changes
        if user:
            for field, old_val, new_val in changes:
                action = (
                    f"{field}_changed"
                    if f"{field}_changed" in dict(TaskActivityLog.ACTION_CHOICES)
                    else "status_changed"
                )
                TaskActivityLog.objects.create(
                    task=instance,
                    user=user,
                    action=action,
                    field=field,
                    old_value=old_val,
                    new_value=new_val,
                )

        return instance
