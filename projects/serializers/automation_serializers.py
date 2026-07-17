from rest_framework import serializers
from projects.models import Automation, AutomationAction, AutomationLog


class AutomationActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationAction
        fields = "__all__"


class AutomationLogSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(source="task.title", read_only=True)

    class Meta:
        model = AutomationLog
        fields = "__all__"


class AutomationSerializer(serializers.ModelSerializer):
    actions = AutomationActionSerializer(many=True, read_only=True)
    space_name = serializers.CharField(source="space.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Automation
        fields = "__all__"
        read_only_fields = [
            "runs",
            "last_run",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None


class AutomationListSerializer(serializers.ModelSerializer):
    actions_count = serializers.SerializerMethodField()
    space_name = serializers.CharField(source="space.name", read_only=True)

    class Meta:
        model = Automation
        fields = [
            "id",
            "name",
            "description",
            "space",
            "space_name",
            "trigger_type",
            "is_active",
            "runs",
            "last_run",
            "actions_count",
            "created_at",
        ]

    def get_actions_count(self, obj):
        return obj.actions.count()
