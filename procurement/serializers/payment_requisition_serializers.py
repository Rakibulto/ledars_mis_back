from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from vendorportal.models.models import VendorProfile
from ..models.payment_requisition_models import (
    PaymentRequisition,
    PaymentRequisitionItem,
)


class PaymentRequisitionItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)

    class Meta:
        model = PaymentRequisitionItem
        fields = [
            "id",
            "payment_requisition",
            "description",
            "item",
            "item_name",
            "quantity",
            "unit_price",
            "amount",
        ]
        read_only_fields = ["id", "amount"]


class PaymentRequisitionItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payment requisition items without payment_requisition field."""

    class Meta:
        model = PaymentRequisitionItem
        fields = [
            "description",
            "item",
            "quantity",
            "unit_price",
        ]


class PaymentRequisitionSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    wo_number = serializers.CharField(source="work_order.wo_number", read_only=True)
    grn_number = serializers.CharField(source="grn.grn_number", read_only=True)
    grn_numbers = serializers.SerializerMethodField()
    budget_code_name = serializers.CharField(source="budget_code.name", read_only=True)
    account_code_name = serializers.CharField(
        source="account_code.name", read_only=True
    )
    project_name = serializers.CharField(source="project.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    approver_name = serializers.SerializerMethodField()
    prf_items = PaymentRequisitionItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(source="prf_items.count", read_only=True)

    # Alias fields for frontend compatibility
    pr_number = serializers.CharField(source="prf_number", read_only=True)
    vendor_name = serializers.CharField(source="supplier.name", read_only=True)
    amount = serializers.DecimalField(
        source="total_amount", read_only=True, max_digits=15, decimal_places=2
    )
    work_order_number = serializers.CharField(
        source="work_order.wo_number", read_only=True
    )

    class Meta:
        model = PaymentRequisition
        fields = [
            "id",
            "prf_number",
            "pr_number",
            "work_order",
            "wo_number",
            "work_order_number",
            "grn",
            "grns",
            "grn_number",
            "grn_numbers",
            "supplier",
            "supplier_name",
            "vendor_name",
            "invoice_number",
            "invoice_date",
            "invoice_amount",
            "budget_code",
            "budget_code_name",
            "account_code",
            "account_code_name",
            "project",
            "project_name",
            "department",
            "department_name",
            "total_amount",
            "amount",
            "tax_amount",
            "net_amount",
            "priority",
            "purpose",
            "remarks",
            "status",
            "attachment",
            "payment_method",
            "finance_remarks",
            "tentative_payment_schedule_date",
            "grn_checkbox",
            "approver",
            "approver_name",
            "approved_date",
            "prf_items",
            "item_count",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "prf_number",
            "net_amount",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_approver_name(self, obj):
        if obj.approver:
            return obj.approver.employee_name
        return None

    def get_grn_numbers(self, obj):
        return [grn.grn_number for grn in obj.grns.all() if grn.grn_number]


class PaymentRequisitionCreateSerializer(serializers.ModelSerializer):
    prf_items = PaymentRequisitionItemCreateSerializer(many=True, required=False)
    # Accept frontend field names
    vendor = serializers.PrimaryKeyRelatedField(
        source="supplier",
        queryset=VendorProfile.objects.all(),
        required=False,
        write_only=True,
    )
    amount = serializers.DecimalField(
        source="total_amount", max_digits=15, decimal_places=2, required=False
    )
 
    class Meta:
        model = PaymentRequisition
        fields = [
            "work_order",
            "grn",
            "grns",
            "supplier",
            "vendor",
            "invoice_number",
            "invoice_date",
            "invoice_amount",
            "budget_code",
            "account_code",
            "project",
            "department",
            "total_amount",
            "amount",
            "tax_amount",
            "priority",
            "purpose",
            "remarks",
            "status",
            "attachment",
            "payment_method",
            "finance_remarks",
            "tentative_payment_schedule_date",
            "grn_checkbox",
            "prf_items",
        ]

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("prf_items", [])
        grns_data = validated_data.pop("grns", [])
        request = self.context.get("request")

        if not validated_data.get("grn") and grns_data:
            validated_data["grn"] = grns_data[0]

        validated_data["created_by"] = request.user if request else None
        if validated_data.get("status") == "Approved" and not validated_data.get("approved_date"):
            validated_data["approved_date"] = timezone.now()
        prf = PaymentRequisition.objects.create(**validated_data)

        if grns_data:
            prf.grns.set(grns_data)

        for item_data in items_data:
            item_data.pop("payment_requisition", None)
            PaymentRequisitionItem.objects.create(payment_requisition=prf, **item_data)
        return prf

    @transaction.atomic
    def update(self, instance, validated_data):
        grns_data = validated_data.pop("grns", None)

        if grns_data is not None and not validated_data.get("grn") and grns_data:
            validated_data["grn"] = grns_data[0]

        if validated_data.get("status") == "Approved" and not instance.approved_date:
            validated_data["approved_date"] = timezone.now()

        instance = super().update(instance, validated_data)

        if grns_data is not None:
            instance.grns.set(grns_data)

        return instance
