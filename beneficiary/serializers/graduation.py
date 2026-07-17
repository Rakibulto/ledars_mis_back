from rest_framework import serializers
from beneficiary.models import ExitGraduation, GraduationCriteria, AlumniTracking, ProgressTracking


class ExitGraduationSerializer(serializers.ModelSerializer):

    beneficiary_info = serializers.SerializerMethodField()
    program_info = serializers.SerializerMethodField()
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = ExitGraduation
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")

    def get_beneficiary_info(self, obj):
        if obj.beneficiary:
            return {
                "id": obj.beneficiary.id,
                "name": str(obj.beneficiary),
                "code": getattr(obj.beneficiary, "beneficiary_code", None),
            }
        return None

    def get_program_info(self, obj):
        if obj.program:
            return {"id": obj.program.id, "name": str(obj.program)}
        return None


class GraduationCriteriaSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.name", read_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = GraduationCriteria
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")


class AlumniTrackingSerializer(serializers.ModelSerializer):
    beneficiary_info = serializers.SerializerMethodField()
    ben_code = serializers.CharField(source="beneficiary.ben_code", read_only=True)
    program_name = serializers.CharField(source="program.name", read_only=True)
    name = serializers.CharField(source="beneficiary.name", read_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = AlumniTracking
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


class ProgressTrackingSerializer(serializers.ModelSerializer):
    beneficiary_info = serializers.SerializerMethodField()
    beneficiary_name = serializers.CharField(source="beneficiary.name", read_only=True)
    ben_code = serializers.CharField(source="beneficiary.ben_code", read_only=True)
    program_name = serializers.CharField(source="program.name", read_only=True)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = ProgressTracking
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
