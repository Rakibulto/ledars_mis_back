from rest_framework import serializers
from accounting.models.perdium_claim_models import PerdiumClaim
from accounting.models.perdium_models import Perdium


class PerdiumClaimSerializer(serializers.ModelSerializer):
    breakfast_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    lunch_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    dinner_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    accommodation_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    others_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = PerdiumClaim
        fields = "__all__"
        read_only_fields = (
            "breakfast_unit_cost", "lunch_unit_cost", "dinner_unit_cost",
            "accommodation_unit_cost", "others_unit_cost",
            "created_by", "status",
        )

    def _apply_rate(self, validated_data, instance=None):
        grade = validated_data.get("grade") or getattr(instance, "grade", None)
        area_type = validated_data.get("area_type") or getattr(instance, "area_type", None)
        if not grade or not area_type:
            return validated_data

        try:
            rate = Perdium.objects.get(grade=grade, area_type=area_type, is_active=True)
        except Perdium.DoesNotExist:
            raise serializers.ValidationError(
                f"No active perdium rate configured for grade '{grade}' / "
                f"area '{area_type}'. Add it under Perdium Rates first."
            )

        validated_data["breakfast_unit_cost"] = rate.breakfast
        validated_data["lunch_unit_cost"] = rate.lunch
        validated_data["dinner_unit_cost"] = rate.dinner
        validated_data["accommodation_unit_cost"] = rate.accommodation
        validated_data["others_unit_cost"] = rate.others_expenses
        return validated_data

    def create(self, validated_data):
        validated_data = self._apply_rate(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._apply_rate(validated_data, instance)
        return super().update(instance, validated_data)