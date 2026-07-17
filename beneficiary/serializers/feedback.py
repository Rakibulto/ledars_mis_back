from rest_framework import serializers
from beneficiary.models import Beneficiary, ComplaintsFeedback, GrievanceRedressal, SatisfactionSurvey


class ComplaintsFeedbackSerializer(serializers.ModelSerializer):
    beneficiary_info = serializers.SerializerMethodField()
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = ComplaintsFeedback
        fields = "__all__"
        read_only_fields = ["created_by", "date", "created_at", "updated_at"]

    def get_beneficiary_info(self, obj):
        if obj.beneficiary:
            return {
                "id": obj.beneficiary.id,
                "ben_code": obj.beneficiary.ben_code,
                "name": obj.beneficiary.name,
            }
        return None


class GrievanceRedressalSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = GrievanceRedressal
        fields = "__all__"
        read_only_fields = ("reference", "created_by", "created_at")


class SatisfactionSurveySerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = SatisfactionSurvey
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")
