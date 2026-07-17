from django.db import transaction
from rest_framework import serializers
from projects.models import Form, FormField, FormSubmission


class FormFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormField
        fields = "__all__"


class FormSubmissionSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FormSubmission
        fields = "__all__"
        read_only_fields = ["submitted_at"]

    def get_submitted_by_name(self, obj):
        if obj.submitted_by:
            return obj.submitted_by.username or obj.submitted_by.email
        return None


class FormSerializer(serializers.ModelSerializer):
    fields_list = FormFieldSerializer(source="fields", many=True, read_only=True)
    submissions_count = serializers.IntegerField(read_only=True)
    space_name = serializers.CharField(source="space.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Form
        fields = "__all__"
        read_only_fields = [
            "submissions_count",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        fields_data = request.data.get("fields_data", []) if request else []

        form = Form.objects.create(**validated_data)

        for idx, field in enumerate(fields_data):
            FormField.objects.create(
                form=form,
                label=field.get("label", ""),
                field_type=field.get("field_type", "text"),
                required=field.get("required", False),
                options=field.get("options", []),
                placeholder=field.get("placeholder", ""),
                position=idx,
            )

        return form
