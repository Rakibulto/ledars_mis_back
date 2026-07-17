from rest_framework import serializers
from django.db import transaction
from inventory.models import Item
from ..models.grn_models import GoodsReceiptNote, GRNItem, GRNVerification


def _extract_item_name_from_remarks(remarks):
    text = (remarks or "").strip()
    if not text.lower().startswith("item:"):
        return ""
    first_segment = text.split("|", 1)[0]
    return first_segment.split(":", 1)[1].strip() if ":" in first_segment else ""


class GRNItemSerializer(serializers.ModelSerializer):
    item = serializers.SerializerMethodField()
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.SerializerMethodField()
    unit = serializers.CharField(source="item.unit", read_only=True)
    total_value = serializers.SerializerMethodField()

    class Meta:
        model = GRNItem
        fields = [
            "id",
            "grn",
            "item",
            "item_code",
            "item_name",
            "unit",
            "ordered_quantity",
            "received_quantity",
            "accepted_quantity",
            "rejected_quantity",
            "unit_price",
            "total_value",
            "batch_number",
            "expiry_date",
            "condition",
            "remarks",
        ]
        read_only_fields = ["id"]

    def get_total_value(self, obj):
        return obj.received_quantity * obj.unit_price

    def get_item(self, obj):
        if obj.item_id:
            return obj.item_id
        item_name = _extract_item_name_from_remarks(obj.remarks)
        if not item_name:
            return None
        matched = Item.objects.filter(name__iexact=item_name).order_by("id").first()
        return matched.id if matched else None

    def get_item_name(self, obj):
        if obj.item and obj.item.item_name:
            return obj.item.item_name
        return _extract_item_name_from_remarks(obj.remarks) or None


class GRNItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating GRN items without grn field."""

    class Meta:
        model = GRNItem
        fields = [
            "item",
            "ordered_quantity",
            "received_quantity",
            "accepted_quantity",
            "rejected_quantity",
            "unit_price",
            "batch_number",
            "expiry_date",
            "condition",
            "remarks",
        ]


class GoodsReceiptNoteSerializer(serializers.ModelSerializer):
    supplier_name = serializers.SerializerMethodField()
    wo_number = serializers.CharField(source="work_order.wo_number", read_only=True)
    po_number = serializers.CharField(source="purchase_order.po_number", read_only=True)
    dp_number = serializers.CharField(source="direct_purchase.dp_number", read_only=True)
    received_by_name = serializers.SerializerMethodField()
    created_by_username = serializers.SerializerMethodField()
    grn_items = GRNItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(source="grn_items.count", read_only=True)
    vendor_info = serializers.SerializerMethodField()
    receive_location_info = serializers.SerializerMethodField()

    # Alias fields for frontend compatibility
    received_date = serializers.DateField(source="receipt_date", read_only=True)
    work_order_number = serializers.CharField(
        source="work_order.wo_number", read_only=True
    )

    class Meta:
        model = GoodsReceiptNote
        fields = [
            "id",
            "grn_number",
            "work_order",
            "wo_number",
            "work_order_number",
            "purchase_order",
            "po_number",
            "direct_purchase",
            "dp_number",
            "supplier",
            "supplier_name",
            "direct_vendor_name",
            "direct_vendor_email",
            "direct_vendor_phone",
            "direct_vendor_address",
            "vendor_info",
            "receipt_date",
            "received_date",
            "delivery_note_number",
            "invoice_number",
            "invoice_amount",
            "total_received_value",
            "remarks",
            "status",
            "received_by",
            "received_by_name",
            "receive_location",
            "receive_location_info",
            "created_by_username",
            "grn_items",
            "item_count",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "grn_number",
            "total_received_value",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_supplier_name(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return obj.direct_vendor_name or None

    def get_vendor_info(self, obj):
        """Return structured vendor data from VendorProfile or direct evaluation fields."""
        if obj.supplier:
            vp = obj.supplier
            return {
                "id": vp.id,
                "name": vp.name,
                "email": getattr(vp, "email", None),
                "phone": getattr(vp, "phone", None),
                "address": getattr(vp, "address", None),
                "is_direct_evaluation": False,
            }
        if obj.direct_vendor_name:
            return {
                "id": None,
                "name": obj.direct_vendor_name,
                "email": obj.direct_vendor_email,
                "phone": obj.direct_vendor_phone,
                "address": obj.direct_vendor_address,
                "is_direct_evaluation": True,
            }
        return None

    def get_receive_location_info(self, obj):
        if obj.receive_location:
            return {
                "id": obj.receive_location.id,
                "name": obj.receive_location.name,
                "code": obj.receive_location.code,
                "address": obj.receive_location.address,
            }
        return None

    def get_received_by_name(self, obj):
        if obj.received_by:
            return obj.received_by.employee_name
        return self.get_created_by_username(obj)

    def get_created_by_username(self, obj):
        if not obj.created_by:
            return None
        return (
            getattr(obj.created_by, "username", None)
            or getattr(obj.created_by, "employee_name", None)
            or getattr(obj.created_by, "email", None)
        )


class GRNCreateSerializer(serializers.ModelSerializer):
    grn_items = GRNItemCreateSerializer(many=True)
    # Accept frontend field name
    received_date = serializers.DateField(
        source="receipt_date", required=False, allow_null=True
    )
    # Direct evaluation vendor fields — accepted when supplier FK is null
    direct_vendor_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True
    )
    direct_vendor_email = serializers.EmailField(
        required=False, allow_blank=True, allow_null=True
    )
    direct_vendor_phone = serializers.CharField(
        max_length=50, required=False, allow_blank=True, allow_null=True
    )
    direct_vendor_address = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    class Meta:
        model = GoodsReceiptNote
        fields = [
            "work_order",
            "purchase_order",
            "direct_purchase",
            "supplier",
            "direct_vendor_name",
            "direct_vendor_email",
            "direct_vendor_phone",
            "direct_vendor_address",
            "receipt_date",
            "received_date",
            "delivery_note_number",
            "invoice_number",
            "invoice_amount",
            "remarks",
            "received_by",
            "receive_location",
            "grn_items",
        ]

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("grn_items", [])
        request = self.context.get("request")
        validated_data["created_by"] = request.user if request else None
        grn = GoodsReceiptNote.objects.create(**validated_data)
        for item_data in items_data:
            item_data.pop("grn", None)
            if not item_data.get("item"):
                item_name = _extract_item_name_from_remarks(item_data.get("remarks"))
                if item_name:
                    item_data["item"] = (
                        Item.objects.filter(name__iexact=item_name).order_by("id").first()
                    )
            GRNItem.objects.create(grn=grn, **item_data)
        grn.calculate_total_received()
        return grn


class GRNVerificationSerializer(serializers.ModelSerializer):
    grn_number = serializers.CharField(source="grn.grn_number", read_only=True)
    verified_by_name = serializers.SerializerMethodField()

    class Meta:
        model = GRNVerification
        fields = [
            "id",
            "grn",
            "grn_number",
            "grn_item",
            "inspection_date",
            "status",
            "findings",
            "verified_by",
            "verified_by_name",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_verified_by_name(self, obj):
        if obj.verified_by:
            return obj.verified_by.employee_name
        return None
