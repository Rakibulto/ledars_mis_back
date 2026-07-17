from rest_framework import serializers
from ..models.vendor_models import (
    VendorCategory,
    VendorCategoryMapping,
    VendorEvaluation,
    VendorOnboarding,
    VendorVerification,
    VendorPerformance,
)


class VendorCategorySerializer(serializers.ModelSerializer):
    vendor_count = serializers.IntegerField(
        source="vendor_mappings.count", read_only=True
    )

    class Meta:
        model = VendorCategory
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "vendor_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class VendorCategoryMappingSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = VendorCategoryMapping
        fields = ["id", "supplier", "supplier_name", "category", "category_name"]


class VendorEvaluationSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    evaluated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = VendorEvaluation
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "evaluation_date",
            "quality_rating",
            "delivery_rating",
            "price_rating",
            "compliance_rating",
            "communication_rating",
            "overall_rating",
            "comments",
            "recommendation",
            "evaluated_by",
            "evaluated_by_name",
            "created_at",
        ]
        read_only_fields = ["overall_rating", "created_at"]

    def get_evaluated_by_name(self, obj):
        if obj.evaluated_by:
            return obj.evaluated_by.employee_name
        return None


class VendorOnboardingSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    checklist_progress = serializers.SerializerMethodField()

    class Meta:
        model = VendorOnboarding
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "status",
            "trade_license",
            "tax_certificate",
            "bank_details",
            "nda_signed",
            "reference_verified",
            "compliance_checked",
            "remarks",
            "checklist_progress",
            "initiated_by",
            "completed_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["initiated_by", "created_at", "updated_at"]

    def get_checklist_progress(self, obj):
        checks = [
            obj.trade_license,
            obj.tax_certificate,
            obj.bank_details,
            obj.nda_signed,
            obj.reference_verified,
            obj.compliance_checked,
        ]
        completed = sum(1 for c in checks if c)
        return {"completed": completed, "total": len(checks)}


class VendorVerificationSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    verified_by_name = serializers.SerializerMethodField()

    class Meta:
        model = VendorVerification
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "status",
            "verification_date",
            "documents_verified",
            "financial_check",
            "compliance_check",
            "remarks",
            "verified_by",
            "verified_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_verified_by_name(self, obj):
        if obj.verified_by:
            return obj.verified_by.employee_name
        return None


class VendorPerformanceSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    delivery_rate = serializers.SerializerMethodField()

    class Meta:
        model = VendorPerformance
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "period_month",
            "period_year",
            "total_orders",
            "on_time_deliveries",
            "late_deliveries",
            "rejected_items",
            "total_spent",
            "avg_delivery_days",
            "compliance_score",
            "delivery_rate",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_delivery_rate(self, obj):
        if obj.total_orders == 0:
            return 0
        return round(obj.on_time_deliveries / obj.total_orders * 100, 1)
