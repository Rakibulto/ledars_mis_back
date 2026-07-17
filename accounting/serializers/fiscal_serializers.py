from rest_framework import serializers
from accounting.models import FiscalYear, FiscalPeriod


class FiscalPeriodSerializer(serializers.ModelSerializer):
    fiscal_year_name = serializers.CharField(source="fiscal_year.name", read_only=True)

    class Meta:
        model = FiscalPeriod
        fields = "__all__"


class FiscalYearListSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True)
    period_count = serializers.SerializerMethodField()

    class Meta:
        model = FiscalYear
        fields = [
            "id",
            "name",
            "code",
            "start_date",
            "end_date",
            "status",
            "is_active",
            "period_count",
            "created_at",
        ]

    def get_period_count(self, obj):
        return obj.periods.count()


class FiscalYearDetailSerializer(serializers.ModelSerializer):
    periods = FiscalPeriodSerializer(many=True, read_only=True)

    class Meta:
        model = FiscalYear
        fields = "__all__"
        read_only_fields = ['code']
