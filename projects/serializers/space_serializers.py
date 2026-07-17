from rest_framework import serializers
from projects.models import Space, SpaceMember


class SpaceMemberSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = SpaceMember
        fields = "__all__"

    def get_user_name(self, obj):
        return obj.user.username or obj.user.email if obj.user else None

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None


class SpaceSerializer(serializers.ModelSerializer):
    space_members = SpaceMemberSerializer(many=True, read_only=True)
    lists_count = serializers.IntegerField(read_only=True)
    tasks_count = serializers.IntegerField(read_only=True)
    workspace_name = serializers.CharField(source="workspace.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Space
        fields = "__all__"
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None


class SpaceListSerializer(serializers.ModelSerializer):
    lists_count = serializers.IntegerField(read_only=True)
    tasks_count = serializers.IntegerField(read_only=True)
    workspace_name = serializers.CharField(source="workspace.name", read_only=True)

    class Meta:
        model = Space
        fields = [
            "id",
            "workspace",
            "workspace_name",
            "name",
            "description",
            "color",
            "icon",
            "is_private",
            "lists_count",
            "tasks_count",
            "created_at",
        ]
