from .models import Payroll
from rest_framework import serializers

# Serializers for Payroll model.


class PayrollSerializer(serializers.ModelSerializer):
    creator = serializers.StringRelatedField(read_only=True)
    employee = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Payroll
        fields = "__all__"


class LockPayrollSerializer(serializers.Serializer):
    """Serializer for lock/unlock endpoints.

    Accepts month (name or number), year, and boolean `is_lock`.  Month name
    is case-insensitive.
    """

    month = serializers.CharField()
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    is_lock = serializers.BooleanField()

    def validate_month(self, value):
        # allow numeric (int or numeric string) or month name
        # return canonical month name
        if isinstance(value, int):
            if 1 <= value <= 12:
                from payroll.utils import MONTH_NAMES

                return MONTH_NAMES[value]
            raise serializers.ValidationError("Month must be 1-12 or month name")
        if isinstance(value, str):
            try:
                iv = int(value)
                if 1 <= iv <= 12:
                    from payroll.utils import MONTH_NAMES

                    return MONTH_NAMES[iv]
                raise serializers.ValidationError("Month must be 1-12 or name")
            except ValueError:
                from payroll.utils import MONTH_NAMES

                for m in MONTH_NAMES.values():
                    if m.lower() == value.lower():
                        return m
                raise serializers.ValidationError("Unknown month name")
        raise serializers.ValidationError("Invalid month value")


class GeneratePayrollSerializer(serializers.Serializer):
    """Validates the payload for the payroll-generation endpoint.

    Accepts either `month`+`year` (legacy) or `start_date`+`end_date` for an
    arbitrary date range.  The two options are mutually exclusive.
    """

    month = serializers.IntegerField(min_value=1, max_value=12, required=False)
    year = serializers.IntegerField(min_value=2000, max_value=2100, required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    basic_payroll = serializers.BooleanField(default=True)
    festival_bonus = serializers.BooleanField(default=False)
    performance_bonus = serializers.BooleanField(default=False)
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=None,
        help_text="Optional list of employee PKs. When omitted, all active employees are included.",
    )
    async_generation = serializers.BooleanField(
        default=False,
        help_text="When true, payroll is generated in a background thread and a notification is sent on completion.",
    )

    def validate(self, attrs):
        # Two mutually exclusive modes: month/year OR start_date/end_date
        has_month = "month" in attrs or "year" in attrs
        has_range = "start_date" in attrs or "end_date" in attrs

        if has_range:
            # both start_date and end_date are required in range mode
            if not attrs.get("start_date") or not attrs.get("end_date"):
                raise serializers.ValidationError(
                    {
                        "date_range": "Both start_date and end_date are required when specifying a date range."
                    }
                )
            if attrs["start_date"] > attrs["end_date"]:
                raise serializers.ValidationError(
                    {"date_range": "start_date must be on or before end_date."}
                )
            # disallow month/year together with range to avoid ambiguity
            if attrs.get("month") or attrs.get("year"):
                raise serializers.ValidationError(
                    {
                        "non_field_errors": "Provide either month/year or start_date/end_date, not both."
                    }
                )
            return attrs

        # month/year mode: both required
        if has_month:
            if attrs.get("month") is None or attrs.get("year") is None:
                raise serializers.ValidationError(
                    {
                        "month_year": "Both month and year are required when not providing a date range."
                    }
                )
            return attrs

        raise serializers.ValidationError(
            {
                "non_field_errors": "Either month/year or start_date/end_date must be provided."
            }
        )
