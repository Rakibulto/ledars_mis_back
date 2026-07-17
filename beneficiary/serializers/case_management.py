from rest_framework import serializers
from beneficiary.models import Beneficiary, CaseFile, ProtectionCase, ConsentRecord, SafeguardingIncident


class CaseFileSerializer(serializers.ModelSerializer):

    beneficiary = serializers.PrimaryKeyRelatedField(
        queryset=Beneficiary.objects.all(), allow_null=True, required=False
    )
    beneficiary_info = serializers.SerializerMethodField()
    case_worke_name = serializers.ReadOnlyField(source="case_worker.employee_name")
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = CaseFile
        fields = "__all__"
        read_only_fields = ["created_by", "last_update", "created_at"]

    def get_beneficiary_info(self, obj):
        if obj.beneficiary:
            return {
                "id": obj.beneficiary.id,
                "ben_code": obj.beneficiary.ben_code,
                "name": obj.beneficiary.name,
            }
        return None


class ProtectionCaseSerializer(serializers.ModelSerializer):
    beneficiary_name = serializers.CharField(source="beneficiary.name", read_only=True)
    case_worker_name = serializers.ReadOnlyField(source="case_worker.employee_name")
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = ProtectionCase
        fields = "__all__"
        read_only_fields = ("reference", "created_by", "created_at", "last_update")


class ConsentRecordSerializer(serializers.ModelSerializer):
    beneficiary_info = serializers.SerializerMethodField()
    beneficiary_name = serializers.CharField(source="beneficiary.name", read_only=True)
    ben_code = serializers.CharField(source="beneficiary.ben_code", read_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = ConsentRecord
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


class SafeguardingIncidentSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = SafeguardingIncident
        fields = "__all__"
        read_only_fields = ("reference", "created_by", "created_at")
