from rest_framework import serializers
from ..models.treasury_models import TreasuryProcessing, PaymentRecord, PaymentTimeline


class TreasuryProcessingSerializer(serializers.ModelSerializer):
    prf_number = serializers.CharField(
        source="payment_requisition.prf_number", read_only=True
    )
    supplier_name = serializers.CharField(
        source="payment_requisition.supplier.name", read_only=True
    )
    reviewed_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TreasuryProcessing
        fields = [
            "id",
            "processing_number",
            "payment_requisition",
            "prf_number",
            "supplier_name",
            "budget_verified",
            "budget_remarks",
            "finance_remarks",
            "approved_amount",
            "payment_method",
            "payment_scheduled_date",
            "status",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_date",
            "approved_by",
            "approved_by_name",
            "approved_date",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "processing_number",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.employee_name
        return None

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.employee_name
        return None


class PaymentRecordSerializer(serializers.ModelSerializer):
    processing_number = serializers.CharField(
        source="treasury_processing.processing_number", read_only=True
    )
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    processed_by_name = serializers.CharField(
        source="processed_by.username", read_only=True
    )

    class Meta:
        model = PaymentRecord
        fields = [
            "id",
            "treasury_processing",
            "processing_number",
            "supplier",
            "supplier_name",
            "payment_date",
            "amount",
            "payment_method",
            "reference_number",
            "bank_name",
            "account_number",
            "cheque_number",
            "status",
            "remarks",
            "processed_by",
            "processed_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["processed_by", "created_at", "updated_at"]


class PaymentTimelineSerializer(serializers.ModelSerializer):
    prf_number = serializers.CharField(
        source="payment_requisition.prf_number", read_only=True
    )
    performed_by_name = serializers.CharField(
        source="performed_by.username", read_only=True
    )

    class Meta:
        model = PaymentTimeline
        fields = [
            "id",
            "payment_requisition",
            "prf_number",
            "stage",
            "timestamp",
            "remarks",
            "performed_by",
            "performed_by_name",
        ]
        read_only_fields = ["timestamp"]
