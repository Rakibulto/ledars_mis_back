from rest_framework import serializers
from beneficiary.models import VulnerabilityAssessment, ImpactMeasurement, OutcomeIndicator, NeedsAssessment


class VulnerabilityAssessmentSerializer(serializers.ModelSerializer):

    beneficiary_name = serializers.CharField(source="beneficiary.name", read_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = VulnerabilityAssessment
        fields = "__all__"
        read_only_fields = ["assessment_code", "created_by", "created_at"]


class ImpactMeasurementSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")
    class Meta:
        model = ImpactMeasurement
        fields = "__all__"
        read_only_fields= ['id', 'created_by', 'created_at']


class OutcomeIndicatorSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")
    class Meta:
        model = OutcomeIndicator
        fields = "__all__"
        read_only_fields= ['id', 'created_by', 'created_at']


class NeedsAssessmentSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = NeedsAssessment
        fields = "__all__"
        read_only_fields = ("reference", "created_by", "created_at")
