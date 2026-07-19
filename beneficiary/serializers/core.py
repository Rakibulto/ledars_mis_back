from rest_framework import serializers
from beneficiary.models import (
    Beneficiary,
    ServiceRH,
    ServiceCategory,
    ServiceDelivery,
    VulnerabilityType,
)


class BeneficiarySerializer(serializers.ModelSerializer):
    total_services_received = serializers.IntegerField(read_only=True)
    total_services_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = Beneficiary
        fields = "__all__"
        read_only_fields = ["ben_code", "created_by", "project_name"]


class SimpleBeneficierySerializer(serializers.ModelSerializer):
    class Meta:
        model = Beneficiary
        fields = ["id", "ben_code", "name"]


class BeneficiarySummarySerializer(serializers.Serializer):
    total_beneficiaries = serializers.IntegerField()
    active = serializers.IntegerField()
    graduated = serializers.IntegerField()
    male = serializers.IntegerField()
    female = serializers.IntegerField()
    Services = serializers.IntegerField()
    total_value = serializers.DecimalField(max_digits=12, decimal_places=2)


class ServiceRHSerializer(serializers.ModelSerializer):

    beneficiary = serializers.PrimaryKeyRelatedField(
        queryset=Beneficiary.objects.all(), allow_null=True, required=False
    )

    beneficiary_info = serializers.SerializerMethodField()
    project_name = serializers.CharField(source="project.name", read_only=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = ServiceRH
        fields = "__all__"
        read_only_fields = ["project_name", "created_by"]

    def get_beneficiary_info(self, obj):
        if obj.beneficiary:
            return {
                "id": obj.beneficiary.id,
                "ben_code": obj.beneficiary.ben_code,
                "name": obj.beneficiary.name,
            }
        return None


class ServiceCategorySerializer(serializers.ModelSerializer):

    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = ServiceCategory
        fields = "__all__"
        read_only_fields = ["created_by"]


class VulnerabilityTypeSerializer(serializers.ModelSerializer):

    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = VulnerabilityType
        fields = "__all__"
        read_only_fields = ["created_by"]


class ServiceDeliverySerializer(serializers.ModelSerializer):

    beneficiary = serializers.PrimaryKeyRelatedField(
        queryset=Beneficiary.objects.all(), allow_null=True, required=False
    )
    beneficiary_info = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = ServiceDelivery
        fields = "__all__"
        read_only_fields = ["created_by"]

    def get_beneficiary_info(self, obj):
        if obj.beneficiary:
            return {
                "id": obj.beneficiary.id,
                "ben_code": obj.beneficiary.ben_code,
                "name": obj.beneficiary.name,
            }
        return None


class ServiceDeliveryStatsSerializer(serializers.Serializer):
    total_services = serializers.IntegerField()
    completed_services = serializers.IntegerField()
    in_progress_services = serializers.IntegerField()
    planned_services = serializers.IntegerField()
    total_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
