from rest_framework import serializers
from projects.models import Goal, KeyResult


class KeyResultSerializer(serializers.ModelSerializer):
    progress = serializers.IntegerField(read_only=True)

    class Meta:
        model = KeyResult
        fields = "__all__"


class GoalSerializer(serializers.ModelSerializer):
    key_results = KeyResultSerializer(many=True, read_only=True)
    progress = serializers.IntegerField(read_only=True)
    owner_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        fields = "__all__"
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def get_owner_name(self, obj):
        if obj.owner:
            return obj.owner.username or obj.owner.email
        return None

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None


class GoalListSerializer(serializers.ModelSerializer):
    progress = serializers.IntegerField(read_only=True)
    owner_name = serializers.SerializerMethodField()
    key_results_count = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        fields = [
            "id",
            "name",
            "description",
            "owner",
            "owner_name",
            "goal_type",
            "target_type",
            "target_value",
            "current_value",
            "start_date",
            "end_date",
            "status",
            "progress",
            "key_results_count",
            "created_at",
        ]

    def get_owner_name(self, obj):
        if obj.owner:
            return obj.owner.username or obj.owner.email
        return None

    def get_key_results_count(self, obj):
        return obj.key_results.count()
