from rest_framework import serializers
from beneficiary.models import Beneficiary, Referral, ReferralNetworkPartner


class ReferralSerializer(serializers.ModelSerializer):

    beneficiary_info = serializers.SerializerMethodField()
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = Referral
        fields = "__all__"
        read_only_fields = ["referral_code", "created_by", "created_at"]

    def get_beneficiary_info(self, obj):
        if obj.beneficiary:
            return {
                "id": obj.beneficiary.id,
                "ben_code": obj.beneficiary.ben_code,
                "name": obj.beneficiary.name,
            }
        return None


class ReferralNetworkPartnerSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = ReferralNetworkPartner
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")
