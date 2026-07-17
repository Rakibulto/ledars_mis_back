from rest_framework import serializers
from projects.models import List


class ListSerializer(serializers.ModelSerializer):
    tasks_count = serializers.IntegerField(read_only=True)
    space_name = serializers.CharField(source="space.name", read_only=True)

    class Meta:
        model = List
        fields = "__all__"
        read_only_fields = ["created_by", "created_at", "updated_at"]
