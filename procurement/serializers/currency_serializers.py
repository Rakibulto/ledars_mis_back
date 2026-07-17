from rest_framework import serializers
from django.db import transaction
from ..models.settings_models import Currency, ExchangeRate


class ExchangeRateSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    currency_name = serializers.CharField(source="currency.name", read_only=True)
    inverse_rate = serializers.DecimalField(
        max_digits=18, decimal_places=6, read_only=True
    )
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ExchangeRate
        fields = [
            "id",
            "currency",
            "currency_code",
            "currency_name",
            "rate",
            "inverse_rate",
            "effective_date",
            "source",
            "notes",
            "created_by",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "created_by"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return getattr(obj.created_by, "get_full_name", lambda: str(obj.created_by))()
        return None

    def create(self, validated_data):
        request = self.context.get("request")
        with transaction.atomic():
            if request and hasattr(request, "user") and request.user.is_authenticated:
                validated_data["created_by"] = request.user
            return super().create(validated_data)


class CurrencySerializer(serializers.ModelSerializer):
    """Full serializer — includes latest rate snapshot for display."""

    latest_rate = serializers.SerializerMethodField()
    last_updated = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Currency
        fields = [
            "id",
            "code",
            "name",
            "symbol",
            "is_base",
            "status",
            "notes",
            "latest_rate",
            "last_updated",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "created_by"]

    def get_latest_rate(self, obj):
        rate = obj.latest_rate
        return float(rate.rate) if rate else None

    def get_last_updated(self, obj):
        rate = obj.latest_rate
        return str(rate.effective_date) if rate else None

    def get_created_by_name(self, obj):
        if obj.created_by:
            return getattr(obj.created_by, "get_full_name", lambda: str(obj.created_by))()
        return None

    def validate(self, attrs):
        # Ensure only one base currency
        if attrs.get("is_base"):
            qs = Currency.objects.filter(is_base=True)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"is_base": "Only one base currency is allowed."}
                )
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        with transaction.atomic():
            if request and hasattr(request, "user") and request.user.is_authenticated:
                validated_data["created_by"] = request.user
            return super().create(validated_data)


class CurrencyListSerializer(serializers.ModelSerializer):
    """Lightweight list serializer (no heavy queries)."""

    latest_rate = serializers.SerializerMethodField()
    last_updated = serializers.SerializerMethodField()

    class Meta:
        model = Currency
        fields = [
            "id",
            "code",
            "name",
            "symbol",
            "is_base",
            "status",
            "latest_rate",
            "last_updated",
        ]

    def get_latest_rate(self, obj):
        rate = obj.latest_rate
        return float(rate.rate) if rate else None

    def get_last_updated(self, obj):
        rate = obj.latest_rate
        return str(rate.effective_date) if rate else None
