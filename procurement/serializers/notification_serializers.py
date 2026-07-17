from rest_framework import serializers
from ..models.notification_models import ProcurementNotification


class ProcurementNotificationSerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(source="recipient.username", read_only=True)

    class Meta:
        model = ProcurementNotification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "priority",
            "reference_id",
            "reference_type",
            "link",
            "recipient",
            "recipient_name",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = ["created_at"]
