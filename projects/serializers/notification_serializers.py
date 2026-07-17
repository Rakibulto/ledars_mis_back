from rest_framework import serializers
from projects.models import PMNotification


class PMNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PMNotification
        fields = "__all__"
        read_only_fields = ["created_at"]
