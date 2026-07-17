from rest_framework import serializers
from projects.models import StatusGroup, Status


class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        fields = "__all__"
        read_only_fields = ["created_by", "created_at"]


class StatusGroupSerializer(serializers.ModelSerializer):
    statuses = StatusSerializer(many=True, read_only=True)

    class Meta:
        model = StatusGroup
        fields = "__all__"
        read_only_fields = ["created_by", "created_at"]
