from rest_framework import serializers
from .models import Donor, DonorLedger


class DonorSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Donor
        fields = "__all__"
        read_only_fields = (
            "id",
            "donor_code",
            "created_at",
            "updated_at",
            "created_by",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.photo:
            request = self.context.get("request")
            photo_url = instance.photo.url
            if request is not None:
                photo_url = request.build_absolute_uri(photo_url)
            data["photo"] = photo_url
        return data


class DonorLedgerSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    donor_name = serializers.CharField(source="donor.name", read_only=True)

    related_project_name = serializers.CharField(
        source="related_project.title",
        read_only=True,
    )

    class Meta:
        model = DonorLedger
        fields = "__all__"
        read_only_fields = (
            "id",
            "ledger_code",
            "created_at",
            "updated_at",
            "created_by",
            "donor_name",
            "related_project_name",
        )