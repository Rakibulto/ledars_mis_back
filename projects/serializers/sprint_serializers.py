from rest_framework import serializers
from projects.models import Sprint, SprintTask


class SprintTaskSerializer(serializers.ModelSerializer):
    task_id_display = serializers.CharField(source="task.task_id", read_only=True)
    task_title = serializers.CharField(source="task.title", read_only=True)
    task_status = serializers.CharField(source="task.status.name", read_only=True)
    task_priority = serializers.CharField(source="task.priority", read_only=True)
    task_story_points = serializers.IntegerField(
        source="task.story_points", read_only=True
    )
    task_assignees = serializers.SerializerMethodField()

    class Meta:
        model = SprintTask
        fields = "__all__"

    def get_task_assignees(self, obj):
        return [
            {"id": ta.user.id, "name": ta.user.username or ta.user.email}
            for ta in obj.task.task_assignees.select_related("user").all()
        ]


class SprintSerializer(serializers.ModelSerializer):
    sprint_tasks = SprintTaskSerializer(many=True, read_only=True)
    total_tasks = serializers.IntegerField(read_only=True)
    completed_tasks = serializers.IntegerField(read_only=True)
    total_points = serializers.IntegerField(read_only=True)
    completed_points = serializers.IntegerField(read_only=True)
    space_name = serializers.CharField(source="space.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Sprint
        fields = "__all__"
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None


class SprintListSerializer(serializers.ModelSerializer):
    total_tasks = serializers.IntegerField(read_only=True)
    completed_tasks = serializers.IntegerField(read_only=True)
    total_points = serializers.IntegerField(read_only=True)
    space_name = serializers.CharField(source="space.name", read_only=True)

    class Meta:
        model = Sprint
        fields = [
            "id",
            "name",
            "goal",
            "space",
            "space_name",
            "start_date",
            "end_date",
            "status",
            "velocity",
            "total_tasks",
            "completed_tasks",
            "total_points",
            "created_at",
        ]
