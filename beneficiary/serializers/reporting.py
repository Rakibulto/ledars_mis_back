from rest_framework import serializers
from beneficiary.models import (
    DonorReport,
    DuplicateRecord,
    AttendanceTracker,
    HouseholdSurvey,
    EligibilityScreening,
)


class DonorReportSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = DonorReport
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")


class DuplicateRecordSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = DuplicateRecord
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")


class DuplicateRecordSummarySerializer(serializers.Serializer):
    total_detected = serializers.IntegerField()
    pending_review = serializers.IntegerField()
    merged = serializers.IntegerField()


class AttendanceTrackerSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = AttendanceTracker
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")


class HouseholdSurveySerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = HouseholdSurvey
        fields = "__all__"
        read_only_fields = ("reference", "created_by", "created_at")


class EligibilityScreeningSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.name", read_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = EligibilityScreening
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")
