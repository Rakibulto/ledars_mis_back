from rest_framework import serializers
from projects.models import Doc


class DocSerializer(serializers.ModelSerializer):
    pages_count = serializers.IntegerField(read_only=True)
    space_name = serializers.CharField(source="space.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    shared_with_users = serializers.SerializerMethodField()

    class Meta:
        model = Doc
        fields = "__all__"
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None

    def get_shared_with_users(self, obj):
        return [
            {"id": u.id, "name": u.username or u.email, "email": u.email}
            for u in obj.shared_with.all()
        ]
