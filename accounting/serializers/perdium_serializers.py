from rest_framework import serializers
from accounting.models.perdium_models import Perdium


class PerdiumSerializer(serializers.ModelSerializer):
    area_type_display = serializers.CharField(source="get_area_type_display", read_only=True)
    grade_display = serializers.CharField(source="get_grade_display", read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = Perdium
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")