from rest_framework import serializers
from projects.models import Milestone, MilestoneTask


class MilestoneTaskSerializer(serializers.ModelSerializer):
    task_id_display = serializers.CharField(source="task.task_id", read_only=True)
    task_title = serializers.CharField(source="task.title", read_only=True)
    task_status = serializers.CharField(source="task.status.name", read_only=True)

    class Meta:
        model = MilestoneTask
        fields = "__all__"


class MilestoneSerializer(serializers.ModelSerializer):
    milestone_tasks = MilestoneTaskSerializer(many=True, read_only=True)
    tasks_count = serializers.IntegerField(read_only=True)
    completed_tasks_count = serializers.IntegerField(read_only=True)
    progress = serializers.IntegerField(read_only=True)
    space_name = serializers.CharField(source="space.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Milestone
        fields = "__all__"
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None
