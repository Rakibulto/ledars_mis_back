import uuid
from datetime import date

from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from rest_framework import serializers

from inventory.models import ScrapRecord, ReturnRecord, StockMove
from inventory.services.scrap_workflow import get_active_scrap_workflow


def _generate_scrap_reference():
    """Auto-generate a unique scrap reference like SCR-20260516-A3F9C2."""
    today = date.today()
    suffix = uuid.uuid4().hex[:6].upper()
    return f"SCR-{today.strftime('%Y%m%d')}-{suffix}"


def _movement_timestamp(document_date):
    timestamp = timezone.localtime()

    if not document_date:
        return timestamp

    return timestamp.replace(
        year=document_date.year,
        month=document_date.month,
        day=document_date.day,
    )


def _build_return_stock_move(return_record):
    if not return_record.product or not return_record.quantity:
        return None

    warehouse_name = getattr(return_record.warehouse,
                             "name", None) or "Returns warehouse"
    origin_reference = return_record.original_reference or "Return reference pending"
    uom_name = getattr(
        getattr(return_record.product, "uom", None), "name", None)

    if return_record.return_type == "supplier":
        source_location = warehouse_name
        destination_location = origin_reference
    else:
        source_location = origin_reference
        destination_location = warehouse_name

    return StockMove(
        date=_movement_timestamp(return_record.date),
        reference=return_record.reference,
        product=return_record.product,
        source_location=source_location,
        destination_location=destination_location,
        quantity=abs(return_record.quantity),
        uom=uom_name,
        move_type="Return",
        done_by=return_record.created_by,
    )


def _build_scrap_stock_move(scrap_record):
    if not scrap_record.product or not scrap_record.quantity:
        return None

    warehouse_name = getattr(scrap_record.warehouse,
                             "name", None) or "Warehouse pending"
    disposal_label = scrap_record.disposal_method or "Scrap holding area"
    uom_name = getattr(
        getattr(scrap_record.product, "uom", None), "name", None)
    movement_date = scrap_record.disposal_date or scrap_record.date

    return StockMove(
        date=_movement_timestamp(movement_date),
        reference=scrap_record.reference,
        product=scrap_record.product,
        source_location=warehouse_name,
        destination_location=disposal_label,
        quantity=abs(scrap_record.quantity),
        uom=uom_name,
        move_type="Scrap",
        done_by=scrap_record.scrapped_by,
    )


def _sync_return_stock_moves(return_record):
    StockMove.objects.filter(
        reference=return_record.reference, move_type="Return").delete()

    stock_move = _build_return_stock_move(return_record)

    if stock_move:
        StockMove.objects.create(
            date=stock_move.date,
            reference=stock_move.reference,
            product=stock_move.product,
            source_location=stock_move.source_location,
            destination_location=stock_move.destination_location,
            quantity=stock_move.quantity,
            uom=stock_move.uom,
            move_type=stock_move.move_type,
            done_by=stock_move.done_by,
        )


def _sync_scrap_stock_moves(scrap_record):
    StockMove.objects.filter(
        reference=scrap_record.reference, move_type="Scrap").delete()

    stock_move = _build_scrap_stock_move(scrap_record)

    if stock_move:
        StockMove.objects.create(
            date=stock_move.date,
            reference=stock_move.reference,
            product=stock_move.product,
            source_location=stock_move.source_location,
            destination_location=stock_move.destination_location,
            quantity=stock_move.quantity,
            uom=stock_move.uom,
            move_type=stock_move.move_type,
            done_by=stock_move.done_by,
        )


def _apply_scrap_stock_deduction(scrap_record):
    """Reduce LocationStock (and via signal Product.on_hand) by the scrap quantity."""
    from inventory.models import Product  # local import to avoid circular
    from inventory.models.product import LocationStock

    if not scrap_record.product_id or not scrap_record.quantity:
        return

    deduct = Decimal(str(scrap_record.quantity))

    with transaction.atomic():
        product = Product.objects.select_for_update().get(pk=scrap_record.product_id)

        if product.on_hand < deduct:
            raise serializers.ValidationError(
                {"quantity": (
                    f"{product.name} ({product.code}) only has {product.on_hand} on hand; "
                    f"cannot scrap {deduct}."
                )}
            )

        office_location_id = scrap_record.office_location_id

        if office_location_id:
            # Deduct from the specific location; signal recalculates Product.on_hand
            loc_stock, _ = LocationStock.objects.select_for_update().get_or_create(
                product_id=scrap_record.product_id,
                office_location_id=office_location_id,
                defaults={"quantity": Decimal("0")},
            )
            new_qty = loc_stock.quantity - deduct
            loc_stock.quantity = max(Decimal("0"), new_qty)
            loc_stock.save(update_fields=["quantity"])
        else:
            # No location set: deduct directly from product.on_hand
            product.on_hand -= deduct
            product.save(update_fields=["on_hand"])


class ScrapRecordSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    uom_name = serializers.CharField(source="product.uom.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    office_location_name = serializers.CharField(
        source="office_location.name", read_only=True
    )
    office_location_type = serializers.CharField(
        source="office_location.type", read_only=True
    )
    scrapped_by_name = serializers.CharField(
        source="scrapped_by.username", read_only=True)
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True)

    class Meta:
        model = ScrapRecord
        fields = "__all__"
        extra_kwargs = {
            "reference": {"required": False, "allow_blank": True},
            "reason": {"required": False, "allow_blank": True, "allow_null": True},
        }
        read_only_fields = [
            "approval_level",
            "approval_log",
            "approved_by",
        ]

    def validate(self, data):
        from inventory.models import Product  # local import to avoid circular

        product = data.get("product") or (self.instance.product if self.instance else None)
        quantity = data.get("quantity") if "quantity" in data else (
            self.instance.quantity if self.instance else None
        )

        if product and quantity is not None:
            try:
                p = Product.objects.get(pk=product.pk)
            except Product.DoesNotExist:
                raise serializers.ValidationError({"product": "Selected product does not exist."})

            qty = Decimal(str(quantity))
            if qty <= 0:
                raise serializers.ValidationError(
                    {"quantity": "Scrap quantity must be greater than zero."}
                )
            if qty > p.on_hand:
                raise serializers.ValidationError(
                    {"quantity": (
                        f"{p.name} ({p.code}) only has {p.on_hand} units on hand; "
                        f"scrap quantity ({qty}) cannot exceed available stock."
                    )}
                )

        return data

    def create(self, validated_data):
        # Always create with "Pending Approval" status
        validated_data["status"] = "Pending Approval"
        # Auto-generate reference if not supplied
        if not validated_data.get("reference"):
            validated_data["reference"] = _generate_scrap_reference()
        with transaction.atomic():
            instance = super().create(validated_data)
            _sync_scrap_stock_moves(instance)
            return instance

    def update(self, instance, validated_data):
        # Block direct status change to approved if workflow is active
        new_status = validated_data.get("status", instance.status)
        if (
            new_status == "approved"
            and instance.status != "approved"
            and get_active_scrap_workflow() is not None
        ):
            raise serializers.ValidationError(
                {
                    "status": (
                        "Workflow approval is required. "
                        "Use POST /api/scrap-records/{id}/approve/."
                    )
                }
            )

        from_status = instance.status
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            _sync_scrap_stock_moves(instance)
            if from_status != "approved" and instance.status == "approved":
                _apply_scrap_stock_deduction(instance)
            return instance


class ScrapRecordReadSerializer(ScrapRecordSerializer):
    class Meta:
        model = ScrapRecord
        fields = "__all__"


class ReturnRecordSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    warehouse_name = serializers.CharField(
        source="warehouse.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True)

    class Meta:
        model = ReturnRecord
        fields = "__all__"

    def create(self, validated_data):
        with transaction.atomic():
            instance = super().create(validated_data)
            _sync_return_stock_moves(instance)
            return instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            _sync_return_stock_moves(instance)
            return instance


class ReturnRecordReadSerializer(ReturnRecordSerializer):
    return_type_label = serializers.CharField(
        source="get_return_type_display", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(
        source="warehouse.name", read_only=True)

    class Meta:
        model = ReturnRecord
        fields = "__all__"
