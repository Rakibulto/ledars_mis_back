from rest_framework import serializers
from accounting.models import TaxGroup, Tax, TaxRule, WithholdingTax


class TaxGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxGroup
        fields = "__all__"


class TaxSerializer(serializers.ModelSerializer):
    tax_group_name = serializers.CharField(
        source="tax_group.name", read_only=True, default=""
    )
    scope_display = serializers.CharField(source="get_scope_display", read_only=True)

    class Meta:
        model = Tax
        fields = "__all__"


class TaxRuleSerializer(serializers.ModelSerializer):
    tax_name = serializers.CharField(source="tax.name", read_only=True)

    class Meta:
        model = TaxRule
        fields = "__all__"


class WithholdingTaxSerializer(serializers.ModelSerializer):
    class Meta:
        model = WithholdingTax
        fields = "__all__"
