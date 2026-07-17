from rest_framework import serializers
from projects.models import Workspace, WorkspaceMember


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceMember
        fields = "__all__"

    def get_user_name(self, obj):
        return obj.user.username or obj.user.email if obj.user else None

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None


class WorkspaceSerializer(serializers.ModelSerializer):
    workspace_members = WorkspaceMemberSerializer(many=True, read_only=True)
    members_count = serializers.IntegerField(read_only=True)
    spaces_count = serializers.IntegerField(read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = "__all__"
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None


class WorkspaceListSerializer(serializers.ModelSerializer):
    members_count = serializers.IntegerField(read_only=True)
    spaces_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Workspace
        fields = [
            "id",
            "name",
            "description",
            "color",
            "is_active",
            "members_count",
            "spaces_count",
            "created_at",
        ]
