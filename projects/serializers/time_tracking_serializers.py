from rest_framework import serializers
from projects.models import TimeEntry


class TimeEntrySerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    task_title = serializers.CharField(source="task.title", read_only=True)
    task_id_display = serializers.CharField(source="task.task_id", read_only=True)
    cost = serializers.FloatField(read_only=True)

    class Meta:
        model = TimeEntry
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def get_user_name(self, obj):
        if obj.user:
            return obj.user.username or obj.user.email
        return None


class TimesheetSerializer(serializers.Serializer):
    """Aggregated timesheet data per user per day."""

    user_id = serializers.IntegerField()
    user_name = serializers.CharField()
    date = serializers.DateField()
    total_duration = serializers.IntegerField()
    total_cost = serializers.FloatField()
    entries_count = serializers.IntegerField()
