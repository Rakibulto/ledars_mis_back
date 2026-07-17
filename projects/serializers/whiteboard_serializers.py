from rest_framework import serializers
from projects.models import Whiteboard


class WhiteboardSerializer(serializers.ModelSerializer):
    space_name = serializers.CharField(source="space.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    collaborator_names = serializers.SerializerMethodField()

    class Meta:
        model = Whiteboard
        fields = "__all__"
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None

    def get_collaborator_names(self, obj):
        return [
            {"id": u.id, "name": u.username or u.email} for u in obj.collaborators.all()
        ]
