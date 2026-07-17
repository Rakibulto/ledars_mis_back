from rest_framework import serializers
from projects.models import CustomField, CustomFieldOption, TaskCustomFieldValue


class CustomFieldOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomFieldOption
        fields = "__all__"


class CustomFieldSerializer(serializers.ModelSerializer):
    options = CustomFieldOptionSerializer(many=True, read_only=True)
    space_name = serializers.CharField(source="space.name", read_only=True)

    class Meta:
        model = CustomField
        fields = "__all__"
        read_only_fields = ["created_by", "created_at"]


class TaskCustomFieldValueSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)
    field_type = serializers.CharField(source="field.field_type", read_only=True)

    class Meta:
        model = TaskCustomFieldValue
        fields = "__all__"
