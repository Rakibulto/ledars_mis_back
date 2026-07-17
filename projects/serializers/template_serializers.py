from rest_framework import serializers
from projects.models import Template


class TemplateSerializer(serializers.ModelSerializer):
    space_name = serializers.CharField(source="space.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Template
        fields = "__all__"
        read_only_fields = ["usage_count", "created_by", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None
