from rest_framework import serializers
from accounting.models import (
    PaymentTerm,
    FiscalPosition,
    FiscalPositionTaxMapping,
    FiscalPositionAccountMapping,
    Incoterm,
    ReconciliationModel,
    BankStatement,
    BankStatementLine,
    Check,
    BankTransfer,
    DeferredRevenue,
    DeferredExpense,
)


class PaymentTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTerm
        fields = "__all__"
        read_only_fields = ("code",)


class FiscalPositionTaxMappingSerializer(serializers.ModelSerializer):
    source_tax_name = serializers.CharField(
        source="source_tax.name", read_only=True, default=""
    )
    destination_tax_name = serializers.CharField(
        source="destination_tax.name", read_only=True, default=""
    )

    class Meta:
        model = FiscalPositionTaxMapping
        fields = [
            "id",
            "source_tax",
            "destination_tax",
            "source_tax_name",
            "destination_tax_name",
        ]


class FiscalPositionAccountMappingSerializer(serializers.ModelSerializer):
    source_account_name = serializers.CharField(
        source="source_account.name", read_only=True, default=""
    )
    destination_account_name = serializers.CharField(
        source="destination_account.name", read_only=True, default=""
    )

    class Meta:
        model = FiscalPositionAccountMapping
        fields = [
            "id",
            "source_account",
            "destination_account",
            "source_account_name",
            "destination_account_name",
        ]


class FiscalPositionSerializer(serializers.ModelSerializer):
    tax_mappings = FiscalPositionTaxMappingSerializer(many=True, required=False)
    account_mappings = FiscalPositionAccountMappingSerializer(many=True, required=False)

    class Meta:
        model = FiscalPosition
        fields = "__all__"

    def create(self, validated_data):
        tax_mappings = validated_data.pop("tax_mappings", [])
        account_mappings = validated_data.pop("account_mappings", [])
        instance = FiscalPosition.objects.create(**validated_data)
        for mapping in tax_mappings:
            # mapping should contain source_tax and destination_tax ids
            FiscalPositionTaxMapping.objects.create(fiscal_position=instance, **mapping)
        for mapping in account_mappings:
            # mapping should contain source_account and destination_account ids
            FiscalPositionAccountMapping.objects.create(fiscal_position=instance, **mapping)
        return instance

    def update(self, instance, validated_data):
        tax_mappings = validated_data.pop("tax_mappings", [])
        account_mappings = validated_data.pop("account_mappings", [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tax_mappings:
            instance.tax_mappings.all().delete()
            for mapping in tax_mappings:
                FiscalPositionTaxMapping.objects.create(fiscal_position=instance, **mapping)
        if account_mappings:
            instance.account_mappings.all().delete()
            for mapping in account_mappings:
                FiscalPositionAccountMapping.objects.create(fiscal_position=instance, **mapping)
        return instance


class IncotermSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incoterm
        fields = "__all__"


class ReconciliationModelSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(
        source="get_model_type_display", read_only=True
    )
    journal_name = serializers.CharField(
        source="match_journal.name", read_only=True, default=""
    )
    account_name = serializers.CharField(
        source="account.name", read_only=True, default=""
    )

    class Meta:
        model = ReconciliationModel
        fields = "__all__"


class BankStatementLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankStatementLine
        fields = "__all__"
        extra_kwargs = {"statement": {"required": False}}


class BankStatementSerializer(serializers.ModelSerializer):
    bank_account_name = serializers.CharField(
        source="bank_account.name", read_only=True
    )
    lines = BankStatementLineSerializer(many=True, read_only=True)
    lines_data = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False, default=list
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    duplicate_count = serializers.SerializerMethodField()
    unmatched_count = serializers.SerializerMethodField()

    class Meta:
        model = BankStatement
        fields = "__all__"

    def get_duplicate_count(self, obj):
        return obj.lines.filter(line_status="duplicate").count()

    def get_unmatched_count(self, obj):
        resolved = {"matched", "writeoff", "counterpart_created"}
        return obj.lines.exclude(line_status__in=resolved).count()

    def create(self, validated_data):
        lines_data = validated_data.pop("lines_data", [])
        statement = super().create(validated_data)
        for line in lines_data:
            line.pop("statement", None)
            amt = float(line.get("amount", 0) or 0)
            line.setdefault("line_type", "credit" if amt >= 0 else "debit")
            line.setdefault("line_status", "unmatched")
            BankStatementLine.objects.create(statement=statement, **line)
        return statement


class CheckSerializer(serializers.ModelSerializer):
    bank_account_name = serializers.CharField(
        source="bank_account.name", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    direction_display = serializers.CharField(
        source="get_direction_display", read_only=True
    )

    class Meta:
        model = Check
        fields = "__all__"


class BankTransferSerializer(serializers.ModelSerializer):
    from_account_name = serializers.CharField(
        source="from_account.name", read_only=True
    )
    to_account_name = serializers.CharField(
        source="to_account.name", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    journal_entry_reference = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = BankTransfer
        fields = "__all__"

    def get_journal_entry_reference(self, obj):
        if obj.journal_entry:
            return f"JE-{obj.journal_entry.id}"
        return ""


class DeferredRevenueSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    customer_name = serializers.CharField(
        source="customer.name", read_only=True, default=""
    )
    monthly_recognition = serializers.SerializerMethodField()

    class Meta:
        model = DeferredRevenue
        fields = "__all__"

    def get_monthly_recognition(self, obj):
        try:
            periods = int(obj.periods) if obj.periods else 0
            if periods > 0:
                return round(float(obj.total_amount) / periods, 2)
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        return 0


class DeferredExpenseSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    vendor_name = serializers.CharField(
        source="vendor.name", read_only=True, default=""
    )
    monthly_recognition = serializers.SerializerMethodField()

    class Meta:
        model = DeferredExpense
        fields = "__all__"

    def get_monthly_recognition(self, obj):
        try:
            periods = int(obj.periods) if obj.periods else 0
            if periods > 0:
                return round(float(obj.total_amount) / periods, 2)
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        return 0

