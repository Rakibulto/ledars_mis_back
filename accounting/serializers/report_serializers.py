from rest_framework import serializers
from accounting.models import (
    FinancialReportTemplate,
    ReportLine,
    GeneratedReport,
    GeneratedReportData,
)


class ReportLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportLine
        fields = "__all__"


class FinancialReportTemplateSerializer(serializers.ModelSerializer):
    lines = ReportLineSerializer(many=True, read_only=True)

    class Meta:
        model = FinancialReportTemplate
        fields = "__all__"


class GeneratedReportDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedReportData
        fields = "__all__"


class GeneratedReportListSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    report_type = serializers.CharField(source="template.report_type", read_only=True)
    generated_by_name = serializers.CharField(
        source="generated_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = GeneratedReport
        fields = [
            "id",
            "title",
            "template",
            "template_name",
            "report_type",
            "period_from",
            "period_to",
            "status",
            "generated_by_name",
            "generated_at",
        ]


class GeneratedReportDetailSerializer(serializers.ModelSerializer):
    data_rows = GeneratedReportDataSerializer(many=True, read_only=True)
    template_detail = FinancialReportTemplateSerializer(
        source="template", read_only=True
    )

    class Meta:
        model = GeneratedReport
        fields = "__all__"
