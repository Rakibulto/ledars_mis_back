from rest_framework import serializers
from beneficiary.models import (
    Beneficiary,
    TargetingCriteria,
    DistributionPlan,
    ServiceCalendarEvent,
    CaseWorkerAssignment,
    FollowUpSchedule,
)


class TargetingCriteriaSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.name", read_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = TargetingCriteria
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")


class DistributionPlanSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = DistributionPlan
        fields = "__all__"
        read_only_fields = ("reference", "created_by", "created_at")


class ServiceCalendarEventSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = ServiceCalendarEvent
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")


class CaseWorkerAssignmentSerializer(serializers.ModelSerializer):
    case_worker_name = serializers.ReadOnlyField(source="case_worker.employee_name")
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = CaseWorkerAssignment
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")


class FollowUpScheduleSerializer(serializers.ModelSerializer):
    beneficiary_info = serializers.SerializerMethodField()
    beneficiary_name = serializers.CharField(source="beneficiary.name", read_only=True)
    ben_code = serializers.CharField(source="beneficiary.ben_code", read_only=True)
    case_worker_name = serializers.ReadOnlyField(source="case_worker.employee_name")
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = FollowUpSchedule
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")

    def get_beneficiary_info(self, obj):
        if obj.beneficiary:
            return {
                "id": obj.beneficiary.id,
                "ben_code": obj.beneficiary.ben_code,
                "name": obj.beneficiary.name,
            }
        return None
 