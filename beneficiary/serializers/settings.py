from rest_framework import serializers
from beneficiary.models import BeneficiarySetting


class BeneficiarySettingSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = BeneficiarySetting
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")
