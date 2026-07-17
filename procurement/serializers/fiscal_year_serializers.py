from rest_framework import serializers
from ..models.fiscal_year_models import FiscalYear, AccountingPeriod


class AccountingPeriodSerializer(serializers.ModelSerializer):
    month = serializers.CharField(source="month_name", read_only=True)
    closed_by_name = serializers.CharField(read_only=True)
    closed_date_display = serializers.SerializerMethodField()

    class Meta:
        model = AccountingPeriod
        fields = [
            "id",
            "period_number",
            "month",
            "start_date",
            "end_date",
            "status",
            "closed_date",
            "closed_date_display",
            "closed_by",
            "closed_by_name",
        ]
        read_only_fields = ["id", "period_number", "start_date", "end_date", "closed_date", "closed_by"]

    def get_closed_date_display(self, obj):
        if obj.closed_date:
            return obj.closed_date.strftime("%Y-%m-%d")
        return ""


class FiscalYearSerializer(serializers.ModelSerializer):
    periods = serializers.IntegerField(read_only=True)
    closed_periods = serializers.IntegerField(read_only=True)
    accounting_periods = AccountingPeriodSerializer(many=True, read_only=True)

    class Meta:
        model = FiscalYear
        fields = [
            "id",
            "code",
            "name",
            "start_date",
            "end_date",
            "status",
            "total_budget",
            "spent",
            "description",
            "periods",
            "closed_periods",
            "accounting_periods",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "periods", "closed_periods", "created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end <= start:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})
        return attrs


class FiscalYearListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list/card view — excludes nested periods."""
    periods = serializers.IntegerField(read_only=True)
    closed_periods = serializers.IntegerField(read_only=True)

    class Meta:
        model = FiscalYear
        fields = [
            "id",
            "code",
            "name",
            "start_date",
            "end_date",
            "status",
            "total_budget",
            "spent",
            "periods",
            "closed_periods",
            "created_at",
        ]
        read_only_fields = fields
