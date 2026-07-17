from rest_framework import serializers
from beneficiary.models import HouseholdProfiling, CoverageArea


class HouseholdProfilingSerializer(serializers.ModelSerializer):

    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = HouseholdProfiling
        fields = "__all__"
        read_only_fields = ["household_code", "created_by", "updated_at", "created_at"]


class CoverageAreaSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = CoverageArea
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")
