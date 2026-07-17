from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import serializers
from inventory.models import (
    GRN,
    GRNLineItem,
    GIN,
    GINLineItem,
    Product,
    StockTransfer,
    StockTransferLine,
    StockAdjustment,
    StockAdjustmentLine,
    CycleCount,
    CycleCountLine,
    LotSerial,
    StockMove,
)
from inventory.serializers.stock_move_helpers import (
    build_stock_move_document_cache,
    get_stock_move_direction,
    get_stock_move_history_status,
    resolve_stock_move_document,
)
from vendorportal.models import VendorProfile


def _get_vendor_display_name(vendor):
    if not vendor:
        return None

    return (
        getattr(vendor, "name", None)
        or getattr(vendor, "legal_name", None)
        or getattr(vendor, "company_name_bn", None)
        or getattr(vendor, "code", None)
    )


def _movement_timestamp(document_date, *, event_timestamp=None):
    if event_timestamp is not None:
        return timezone.localtime(event_timestamp)

    timestamp = timezone.localtime()

    if not document_date:
        return timestamp

    return timestamp.replace(
        year=document_date.year,
        month=document_date.month,
        day=document_date.day,
    )


def _resolve_request_actor(serializer, *fallback_users):
    request = serializer.context.get("request")
    user = getattr(request, "user", None)

    if getattr(user, "is_authenticated", False):
        return user

    for fallback_user in fallback_users:
        if fallback_user:
            return fallback_user

    return None


def _create_gin_status_log(*, gin, from_status, to_status, actor):
    if not gin.gin_number or not to_status:
        return None

    previous_status = from_status or "Created"

    return StockMove.objects.create(
        date=timezone.localtime(),
        reference=gin.gin_number,
        product=None,
        source_location=previous_status,
        destination_location=to_status,
        quantity=Decimal("0"),
        uom=None,
        move_type="Status Change",
        done_by=actor,
        from_status=previous_status,
        to_status=to_status,
    )


def _build_stock_move(
    *,
    document_date,
    movement_timestamp=None,
    reference,
    product,
    source_location,
    destination_location,
    quantity,
    uom,
    move_type,
    done_by,
):
    if not product or not quantity:
        return None

    return StockMove(
        date=_movement_timestamp(
            document_date, event_timestamp=movement_timestamp),
        reference=reference,
        product=product,
        source_location=source_location,
        destination_location=destination_location,
        quantity=abs(quantity),
        uom=uom,
        move_type=move_type,
        done_by=done_by,
    )


def _build_grn_stock_move(grn, line):
    vendor_name = _get_vendor_display_name(grn.supplier) or "Vendor receipt"
    warehouse_name = getattr(grn.warehouse, "name", None) or "Main inventory"

    return _build_stock_move(
        document_date=grn.receive_date,
        reference=grn.grn_number,
        product=line.product,
        source_location=vendor_name,
        destination_location=warehouse_name,
        quantity=line.accepted_qty,
        uom=line.unit,
        move_type="Receipt",
        done_by=grn.received_by,
    )


def _build_gin_stock_move(gin, line, *, movement_timestamp=None):
    source_label = (
        getattr(gin.office_location, "name", None)
        or getattr(gin.warehouse, "name", None)
        or "Main inventory"
    )
    destination_label = gin.issued_to or gin.department or gin.project or "Issued out"

    return _build_stock_move(
        document_date=gin.issue_date,
        movement_timestamp=movement_timestamp,
        reference=gin.gin_number,
        product=line.product,
        source_location=source_label,
        destination_location=destination_label,
        quantity=line.issued_qty,
        uom=line.unit,
        move_type="Delivery",
        done_by=gin.requested_by or gin.approved_by,
    )


def _build_transfer_stock_move(transfer, line):
    source_label = transfer.from_location or getattr(
        transfer.from_warehouse, "name", None) or "Source pending"
    destination_label = transfer.to_location or getattr(
        transfer.to_warehouse, "name", None) or "Destination pending"

    return _build_stock_move(
        document_date=transfer.transfer_date,
        reference=transfer.transfer_number,
        product=line.product,
        source_location=source_label,
        destination_location=destination_label,
        quantity=line.quantity,
        uom=line.unit,
        move_type="Transfer",
        done_by=transfer.sent_by or transfer.received_by,
    )


def _build_adjustment_stock_move(adjustment, line):
    if not line.difference:
        return None

    warehouse_label = adjustment.location or getattr(
        adjustment.warehouse, "name", None) or "Inventory adjustment"

    if line.difference > 0:
        source_label = "Adjustment increase"
        destination_label = warehouse_label
    else:
        source_label = warehouse_label
        destination_label = "Adjustment decrease"

    return _build_stock_move(
        document_date=adjustment.adjustment_date,
        reference=adjustment.adjustment_number,
        product=line.product,
        source_location=source_label,
        destination_location=destination_label,
        quantity=line.difference,
        uom=line.unit,
        move_type="Adjustment",
        done_by=adjustment.adjusted_by or adjustment.approved_by,
    )


def _replace_line_items(instance, lines_data, related_name, line_model, foreign_key_name):
    related_manager = getattr(instance, related_name)

    if lines_data is None:
        return list(related_manager.all())

    related_manager.all().delete()

    return [
        line_model.objects.create(**{foreign_key_name: instance}, **line_data)
        for line_data in lines_data
    ]


def _sync_stock_moves(reference, move_type, stock_moves):
    if reference:
        StockMove.objects.filter(
            reference=reference, move_type=move_type).delete()

    if stock_moves:
        StockMove.objects.bulk_create(stock_moves)


def _rebuild_grn_totals_and_stock_moves(grn, lines):
    total = 0
    stock_moves = []

    for line in lines:
        total += (line.accepted_qty or 0) * float(line.unit_price or 0)

        stock_move = _build_grn_stock_move(grn, line)
        if stock_move is not None:
            stock_moves.append(stock_move)

    _sync_stock_moves(grn.grn_number, "Receipt", stock_moves)

    grn.total_value = total
    grn.save(update_fields=["total_value"])


def _apply_grn_verified_stock_update(grn, lines):
    """
    Called exactly once when a GRN transitions to 'Verified'.

    For each line item with a product and accepted_qty > 0:
    - Find or create a LocationStock row at the default office
      (first OfficeManagement where type='office').
    - Increment its quantity by the accepted_qty.

    The post_save signal on LocationStock will automatically recalculate
    Product.on_hand = SUM(all LocationStock rows for that product).

    This function must only be called when the GRN is transitioning FROM
    a non-Verified status TO 'Verified'. Re-saving an already-Verified
    GRN must NOT call this function.
    """
    from procurement.models.office_models import OfficeManagement
    from inventory.models.product import LocationStock

    default_office = OfficeManagement.objects.filter(type="office").first()
    if default_office is None:
        raise serializers.ValidationError(
            {
                "status": (
                    "Cannot verify GRN: no Office location found in Office Management. "
                    "Please create at least one office location first."
                )
            }
        )

    for line in lines:
        if not line.product_id:
            continue

        accepted = Decimal(str(line.accepted_qty or 0))
        if accepted <= Decimal("0"):
            continue

        loc_stock, _ = LocationStock.objects.select_for_update().get_or_create(
            product_id=line.product_id,
            office_location=default_office,
            defaults={"quantity": Decimal("0")},
        )
        loc_stock.quantity += accepted
        loc_stock.save(update_fields=["quantity"])
        # The post_save signal (_sync_product_on_hand) automatically updates
        # Product.on_hand = SUM(LocationStock.quantity) for this product.

        # Update the item's unit_price from the GRN line unit_price.
        # Product.save() automatically preserves the old price in old_unit_price
        # when cost changes (see Product.save() in models/product.py).
        if line.unit_price is not None:
            product = (Product.objects.select_for_update().filter(pk=line.product_id).first())
            if product is not None and product.cost != line.unit_price:
                product.cost = line.unit_price
                product.save(update_fields=["cost", "old_unit_price"])


def _rebuild_gin_totals_and_stock_moves(gin, lines, *, movement_timestamp=None):
    total = 0
    stock_moves = []

    for line in lines:
        total += (line.issued_qty or 0) * float(line.unit_price or 0)

        if gin.status == "Issued":
            stock_move = _build_gin_stock_move(
                gin,
                line,
                movement_timestamp=movement_timestamp,
            )
            if stock_move is not None:
                stock_moves.append(stock_move)

    _sync_stock_moves(gin.gin_number, "Delivery", stock_moves)

    gin.total_value = total
    gin.save(update_fields=["total_value"])


def reconcile_issued_gin_delivery_history(gins=None):
    if gins is None:
        queryset = GIN.objects.filter(status="Issued")
    elif getattr(gins, "model", None) is GIN:
        queryset = gins.filter(status="Issued")
    else:
        gin_ids = [
            gin.id
            for gin in gins
            if getattr(gin, "id", None) and getattr(gin, "status", None) == "Issued"
        ]

        if not gin_ids:
            return 0

        queryset = GIN.objects.filter(id__in=gin_ids, status="Issued")

    queryset = (
        queryset.exclude(gin_number__isnull=True)
        .exclude(gin_number="")
        .select_related("warehouse", "requested_by", "approved_by")
        .prefetch_related("line_items", "line_items__product")
        .distinct()
    )

    gin_numbers = list(queryset.values_list("gin_number", flat=True))

    if not gin_numbers:
        return 0

    existing_delivery_counts = dict(
        StockMove.objects.filter(move_type="Delivery",
                                 reference__in=gin_numbers)
        .values("reference")
        .annotate(total=Count("id"))
        .values_list("reference", "total")
    )
    reconciled = 0

    for gin in queryset:
        expected_stock_moves = []

        for line in gin.line_items.all():
            stock_move = _build_gin_stock_move(gin, line)
            if stock_move is not None:
                expected_stock_moves.append(stock_move)

        if existing_delivery_counts.get(gin.gin_number, 0) == len(expected_stock_moves):
            continue

        _sync_stock_moves(gin.gin_number, "Delivery", expected_stock_moves)
        reconciled += 1

    return reconciled


def _apply_gin_stock_reduction(gin, lines, *, apply_changes=True):
    """
    Validate and (optionally) deduct issued quantities from LocationStock.

    Stock is deducted *only* from the warehouse / office explicitly set on
    the GIN (gin.office_location).  No fallback to a product-home location
    or any other warehouse is performed.

    When apply_changes=True (status -> Issued) and no location is selected,
    a validation error is raised immediately.
    When apply_changes=False (status -> Approved pre-check), missing location
    is silently skipped; the user can assign it before issuing.
    """
    from inventory.services.transfer import deduct_location_stock
    from inventory.models.product import LocationStock

    location = gin.office_location  # OfficeManagement FK - issuing warehouse

    if location is None:
        # Self-heal: if issue_from text is set, try to resolve the FK from it.
        # This fixes legacy GINs where the form saved the office name as text
        # but did not persist the office_location FK.
        if getattr(gin, "issue_from", None):
            from procurement.models.office_models import OfficeManagement as _OM
            from inventory.models.operations import GIN as _GIN
            _resolved = _OM.objects.filter(
                name__iexact=str(gin.issue_from).strip()
            ).first()
            if _resolved is not None:
                location = _resolved
                _GIN.objects.filter(pk=gin.pk).update(office_location=_resolved)
                gin.office_location = _resolved

    if location is None:
        if apply_changes:
            raise serializers.ValidationError(
                {
                    "office_location": (
                        "An issuing warehouse / office must be selected on the GIN "
                        "before it can be marked as Issued."
                    )
                }
            )
        return  # No location yet; skip stock pre-check during Approval

    issued_quantities = {}

    for line in lines:
        if not line.product_id or not line.issued_qty:
            continue

        issued_quantities[line.product_id] = issued_quantities.get(
            line.product_id, Decimal("0")
        ) + Decimal(str(line.issued_qty))

    if not issued_quantities:
        return

    products = {
        p.id: p
        for p in Product.objects.filter(id__in=issued_quantities)
    }

    # ------------------------------------------------------------------ #
    # Validation pass - check LocationStock at the selected location only. #
    # ------------------------------------------------------------------ #
    insufficient_products = []

    for product_id, issued_qty in issued_quantities.items():
        product = products.get(product_id)
        if product is None:
            continue

        available = (
            LocationStock.objects
            .filter(product_id=product_id, office_location=location)
            .values_list("quantity", flat=True)
            .first()
        ) or Decimal("0")

        if available < issued_qty:
            insufficient_products.append(
                f"{product.name} ({product.code}) has only {available} available"
                f" at '{location.name}'; cannot issue {issued_qty}."
            )

    if insufficient_products:
        raise serializers.ValidationError({"status": insufficient_products})

    if not apply_changes:
        return

    # ------------------------------------------------------------------ #
    # Deduction pass - deduct from LocationStock at the selected location. #
    # ------------------------------------------------------------------ #
    for product_id, issued_qty in issued_quantities.items():
        product = products.get(product_id)
        if product is None:
            continue

        try:
            deduct_location_stock(location, product, issued_qty)
        except ValueError as exc:
            raise serializers.ValidationError({"status": [str(exc)]}) from exc


def _apply_stock_adjustment_product_delta(lines):
    adjustment_differences = {}

    for line in lines:
        if not line.product_id or not line.difference:
            continue

        adjustment_differences[line.product_id] = adjustment_differences.get(
            line.product_id, Decimal("0")
        ) + Decimal(str(line.difference))

    if not adjustment_differences:
        return

    # Determine the office_location for this adjustment (all lines share one adjustment)
    office_location_id = None
    if lines:
        try:
            office_location_id = lines[0].adjustment.office_location_id
        except AttributeError:
            pass

    products = {
        product.id: product
        for product in Product.objects.select_for_update().filter(
            id__in=adjustment_differences
        )
    }
    insufficient_products = []

    for product_id, net_difference in adjustment_differences.items():
        product = products.get(product_id)
        if product is None or net_difference >= 0:
            continue

        required_qty = abs(net_difference)
        if product.on_hand < required_qty:
            insufficient_products.append(
                f"{product.name} ({product.code}) has only {product.on_hand} on hand; cannot reduce {required_qty}."
            )

    if insufficient_products:
        raise serializers.ValidationError({"status": insufficient_products})

    for product_id, net_difference in adjustment_differences.items():
        product = products.get(product_id)
        if product is None:
            continue

        if office_location_id:
            from inventory.models.product import LocationStock  # noqa: PLC0415
            # Update LocationStock; the post_save signal recalculates Product.on_hand automatically
            loc_stock, _ = LocationStock.objects.select_for_update().get_or_create(
                product_id=product_id,
                office_location_id=office_location_id,
                defaults={"quantity": Decimal("0")},
            )
            new_qty = loc_stock.quantity + net_difference
            loc_stock.quantity = max(Decimal("0"), new_qty)
            loc_stock.save(update_fields=["quantity"])
        else:
            # No office_location set: update product.on_hand directly
            product.on_hand += net_difference
            product.save()


def _rebuild_transfer_totals_and_stock_moves(transfer, lines):
    total = 0
    stock_moves = []

    for line in lines:
        total += (line.quantity or 0) * float(line.unit_price or 0)

        stock_move = _build_transfer_stock_move(transfer, line)
        if stock_move is not None:
            stock_moves.append(stock_move)

    _sync_stock_moves(transfer.transfer_number, "Transfer", stock_moves)

    transfer.total_value = total
    transfer.save(update_fields=["total_value"])


def _create_adjustment_status_log(*, adjustment, from_status, to_status, actor):
    if not adjustment.adjustment_number or not to_status:
        return None

    previous_status = from_status or "Created"

    return StockMove.objects.create(
        date=timezone.localtime(),
        reference=adjustment.adjustment_number,
        product=None,
        source_location=previous_status,
        destination_location=to_status,
        quantity=Decimal("0"),
        uom=None,
        move_type="Status Change",
        done_by=actor,
        from_status=previous_status,
        to_status=to_status,
    )


def _rebuild_adjustment_totals_and_stock_moves(adjustment, lines):
    total = 0
    stock_moves = []

    for line in lines:
        total += abs(line.difference or 0) * float(line.unit_price or 0)

        stock_move = _build_adjustment_stock_move(adjustment, line)
        if stock_move is not None:
            stock_moves.append(stock_move)

    _sync_stock_moves(adjustment.adjustment_number, "Adjustment", stock_moves)

    adjustment.total_value = total
    adjustment.save(update_fields=["total_value"])


class GRNLineItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = GRNLineItem
        fields = "__all__"
        read_only_fields = ["id", "grn"]


class GRNReadSerializer(serializers.ModelSerializer):
    line_items = GRNLineItemSerializer(many=True, read_only=True)
    vendor_id = serializers.IntegerField(source="supplier_id", read_only=True)
    vendor_name = serializers.SerializerMethodField()
    supplier_name = serializers.SerializerMethodField()
    po_number_display = serializers.CharField(
        source="po_number.po_number", read_only=True)
    warehouse_name = serializers.CharField(
        source="warehouse.name", read_only=True)
    received_by_name = serializers.CharField(
        source="received_by.username", read_only=True
    )
    item_count = serializers.SerializerMethodField()
    ordered_qty_total = serializers.SerializerMethodField()
    accepted_qty_total = serializers.SerializerMethodField()
    rejected_qty_total = serializers.SerializerMethodField()
    pending_qty_total = serializers.SerializerMethodField()

    class Meta:
        model = GRN
        fields = "__all__"

    def get_vendor_name(self, obj):
        return _get_vendor_display_name(obj.supplier)

    def get_supplier_name(self, obj):
        return self.get_vendor_name(obj)

    def get_item_count(self, obj):
        return obj.line_items.count()

    def get_ordered_qty_total(self, obj):
        return round(sum(float(line.ordered_qty or 0) for line in obj.line_items.all()), 2)

    def get_accepted_qty_total(self, obj):
        return round(sum(float(line.accepted_qty or 0) for line in obj.line_items.all()), 2)

    def get_rejected_qty_total(self, obj):
        return round(sum(float(line.rejected_qty or 0) for line in obj.line_items.all()), 2)

    def get_pending_qty_total(self, obj):
        return round(
            sum(
                max(float(line.ordered_qty or 0) -
                    float(line.received_qty or 0), 0)
                for line in obj.line_items.all()
            ),
            2,
        )


class GRNWriteSerializer(serializers.ModelSerializer):
    line_items = GRNLineItemSerializer(many=True, required=False)
    vendor = serializers.PrimaryKeyRelatedField(
        source="supplier",
        queryset=VendorProfile.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = GRN
        fields = "__all__"
        read_only_fields = ["grn_number",
                            "total_value", "created_at", "updated_at"]

    def create(self, validated_data):
        lines_data = validated_data.pop("line_items", [])
        with transaction.atomic():
            grn = GRN.objects.create(**validated_data)
            lines = _replace_line_items(
                grn, lines_data, "line_items", GRNLineItem, "grn")
            _rebuild_grn_totals_and_stock_moves(grn, lines)

        return grn

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("line_items", None)

        # Capture the previous status before overwriting the instance fields.
        # This is the only safe place to read it — after setattr() it's gone.
        previous_status = instance.status
        new_status = validated_data.get("status", instance.status)

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.save()

            lines = _replace_line_items(
                instance, lines_data, "line_items", GRNLineItem, "grn"
            )
            _rebuild_grn_totals_and_stock_moves(instance, lines)

            # ── Stock update on first-time Verified transition ───────────────
            # Run only when the status changes FROM any non-Verified state
            # TO 'Verified'. Re-saving an already-Verified GRN is a no-op.
            if new_status == "Verified" and previous_status != "Verified":
                _apply_grn_verified_stock_update(instance, lines)

        return instance


class GINLineItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    item_current_quantity = serializers.SerializerMethodField()

    class Meta:
        model = GINLineItem
        fields = "__all__"
        read_only_fields = ["id", "gin"]

    def get_item_current_quantity(self, obj):
        if not obj.product_id:
            return None

        # GINReadSerializer.to_representation injects a per-GIN LocationStock map
        # so we return the exact quantity available at the issuing location.
        ls_map = self.context.get("gin_location_stock_map")
        if ls_map is not None:
            # Returns 0 (not None) so the frontend chip shows "Out of stock"
            # rather than hiding the column entirely.
            return round(float(ls_map.get(obj.product_id, 0)), 2)

        # Fallback: GIN has no office_location — show global on_hand.
        return round(float(obj.product.on_hand or 0), 2)


class GINReadSerializer(serializers.ModelSerializer):
    line_items = GINLineItemSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(
        source="warehouse.name", read_only=True)
    office_location_name = serializers.CharField(
        source="office_location.name", read_only=True)
    office_location_type = serializers.CharField(
        source="office_location.type", read_only=True)
    requested_by_name = serializers.CharField(
        source="requested_by.username", read_only=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True
    )
    issued_by_name = serializers.CharField(
        source="issued_by.username", read_only=True
    )
    item_count = serializers.SerializerMethodField()
    issued_qty_total = serializers.SerializerMethodField()
    status_log = serializers.SerializerMethodField()
    issue_from_location_id = serializers.SerializerMethodField()
    project_id = serializers.SerializerMethodField()

    class Meta:
        model = GIN
        fields = "__all__"

    def get_item_count(self, obj):
        return obj.line_items.count()

    def get_issue_from_location_id(self, obj):
        """FK id of the office location goods were issued FROM."""
        return obj.office_location_id

    def get_project_id(self, obj):
        """Return the FK id of the linked ProjectManagementProject, or None."""
        return obj.project_fk_id

    def get_issued_qty_total(self, obj):
        return round(sum(float(line.issued_qty or 0) for line in obj.line_items.all()), 2)

    def _get_status_log_cache(self):
        cache = self.context.get("_gin_status_log_cache")

        if cache is not None:
            return cache

        root_instance = getattr(getattr(self, "root", None), "instance", None)

        if root_instance is None:
            self.context["_gin_status_log_cache"] = {}
            return self.context["_gin_status_log_cache"]

        if isinstance(root_instance, GIN):
            gin_numbers = [
                root_instance.gin_number] if root_instance.gin_number else []
        else:
            gin_numbers = [
                instance.gin_number
                for instance in root_instance
                if getattr(instance, "gin_number", None)
            ]

        status_moves = (
            StockMove.objects.select_related("done_by")
            .filter(reference__in=gin_numbers, move_type="Status Change")
            .order_by("date", "id")
        )

        cache = {}

        for move in status_moves:
            cache.setdefault(move.reference, []).append(
                {
                    "gin_code": move.reference,
                    "name": getattr(move.done_by, "username", None) or "System",
                    "email": getattr(move.done_by, "email", None),
                    "status_from": "_"
                    if move.from_status in {None, "", "Created"}
                    else move.from_status,
                    "status_to": move.to_status or move.destination_location,
                }
            )

        self.context["_gin_status_log_cache"] = cache
        return cache

    def get_status_log(self, obj):
        return self._get_status_log_cache().get(obj.gin_number, [])

    def to_representation(self, instance):
        from inventory.models.product import LocationStock

        # Pre-build a {product_id: quantity} map for this GIN's office_location.
        # Injecting it into context lets the nested GINLineItemSerializer return
        # location-specific stock in a single extra query (no N+1).
        gin_location = instance.office_location  # already select_related by viewset

        if gin_location:
            ls_map = dict(
                LocationStock.objects
                .filter(office_location=gin_location)
                .values_list("product_id", "quantity")
            )
        else:
            ls_map = None  # No location set; line items fall back to product.on_hand

        self.context["gin_location_stock_map"] = ls_map
        result = super().to_representation(instance)
        self.context.pop("gin_location_stock_map", None)
        # If project is blank, expose issued_to as the project value
        if not result.get("project"):
            result["project"] = instance.issued_to or None
        return result


class GINWriteSerializer(serializers.ModelSerializer):
    line_items = GINLineItemSerializer(many=True, required=False)

    class Meta:
        model = GIN
        fields = "__all__"
        read_only_fields = ["gin_number",
                            "total_value", "created_at", "updated_at"]

    def _validate_workflow_status_transition(self, previous_status, new_status):
        if new_status == previous_status:
            return

        from inventory.services.gin_workflow import get_active_gin_workflow

        if not get_active_gin_workflow():
            return

        if previous_status == "Pending Approval" and new_status == "Approved":
            raise serializers.ValidationError(
                {
                    "status": (
                        "Workflow approval is required. "
                        "Use POST /api/gin/{id}/approve/."
                    )
                }
            )

        if previous_status == "Approved" and new_status == "Issued":
            raise serializers.ValidationError(
                {
                    "status": (
                        "Workflow issue is required. "
                        "Use POST /api/gin/{id}/issue/."
                    )
                }
            )

    def create(self, validated_data):
        lines_data = validated_data.pop("line_items", [])
        with transaction.atomic():
            gin = GIN.objects.create(**validated_data)
            lines = _replace_line_items(
                gin, lines_data, "line_items", GINLineItem, "gin")

            if gin.status == "Approved":
                _apply_gin_stock_reduction(gin, lines, apply_changes=False)
            elif gin.status == "Issued":
                _apply_gin_stock_reduction(gin, lines)

            status_log = _create_gin_status_log(
                gin=gin,
                from_status=None,
                to_status=gin.status,
                actor=_resolve_request_actor(
                    self,
                    gin.requested_by,
                    gin.approved_by,
                ),
            )
            _rebuild_gin_totals_and_stock_moves(
                gin,
                lines,
                movement_timestamp=status_log.date if gin.status == "Issued" and status_log else None,
            )

        return gin

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("line_items", None)
        previous_status = instance.status
        new_status = validated_data.get("status", previous_status)
        self._validate_workflow_status_transition(previous_status, new_status)

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.save()

            lines = _replace_line_items(
                instance, lines_data, "line_items", GINLineItem, "gin"
            )

            if instance.status == "Approved":
                _apply_gin_stock_reduction(instance, lines, apply_changes=False)

            if previous_status != "Issued" and instance.status == "Issued":
                _apply_gin_stock_reduction(instance, lines)

            status_log = None
            if previous_status != instance.status:
                status_log = _create_gin_status_log(
                    gin=instance,
                    from_status=previous_status,
                    to_status=instance.status,
                    actor=_resolve_request_actor(
                        self,
                        instance.approved_by,
                        instance.requested_by,
                    ),
                )

            _rebuild_gin_totals_and_stock_moves(
                instance,
                lines,
                movement_timestamp=(
                    status_log.date
                    if instance.status == "Issued" and status_log is not None
                    else None
                ),
            )

        return instance


class StockTransferLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = StockTransferLine
        fields = "__all__"
        read_only_fields = ["id", "transfer"]


class StockTransferReadSerializer(serializers.ModelSerializer):
    lines = StockTransferLineSerializer(many=True, read_only=True)
    from_warehouse_name = serializers.CharField(
        source="from_warehouse.name", read_only=True
    )
    to_warehouse_name = serializers.CharField(
        source="to_warehouse.name", read_only=True
    )
    sent_by_name = serializers.CharField(
        source="sent_by.username", read_only=True)
    received_by_name = serializers.CharField(
        source="received_by.username", read_only=True
    )
    item_count = serializers.SerializerMethodField()
    quantity_total = serializers.SerializerMethodField()

    class Meta:
        model = StockTransfer
        fields = "__all__"

    def get_item_count(self, obj):
        return obj.lines.count()

    def get_quantity_total(self, obj):
        return round(sum(float(line.quantity or 0) for line in obj.lines.all()), 2)


class StockTransferWriteSerializer(serializers.ModelSerializer):
    lines = StockTransferLineSerializer(many=True, required=False)

    class Meta:
        model = StockTransfer
        fields = "__all__"
        read_only_fields = [
            "transfer_number",
            "total_value",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        with transaction.atomic():
            transfer = StockTransfer.objects.create(**validated_data)
            lines = _replace_line_items(
                transfer, lines_data, "lines", StockTransferLine, "transfer"
            )
            _rebuild_transfer_totals_and_stock_moves(transfer, lines)

        return transfer

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.save()

            lines = _replace_line_items(
                instance, lines_data, "lines", StockTransferLine, "transfer"
            )
            _rebuild_transfer_totals_and_stock_moves(instance, lines)

        return instance


class StockAdjustmentLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = StockAdjustmentLine
        fields = "__all__"
        read_only_fields = ["id", "adjustment"]


class StockAdjustmentReadSerializer(serializers.ModelSerializer):
    lines = StockAdjustmentLineSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(
        source="warehouse.name", read_only=True)
    office_location_name = serializers.CharField(
        source="office_location.name", read_only=True)
    office_location_type = serializers.CharField(
        source="office_location.type", read_only=True)
    adjusted_by_name = serializers.CharField(
        source="adjusted_by.username", read_only=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True
    )
    item_count = serializers.SerializerMethodField()
    difference_total = serializers.SerializerMethodField()
    status_log = serializers.SerializerMethodField()

    class Meta:
        model = StockAdjustment
        fields = "__all__"

    def get_item_count(self, obj):
        return obj.lines.count()

    def get_difference_total(self, obj):
        return round(sum(float(line.difference or 0) for line in obj.lines.all()), 2)

    def _get_status_log_cache(self):
        cache = self.context.get("_adjustment_status_log_cache")

        if cache is not None:
            return cache

        root_instance = getattr(getattr(self, "root", None), "instance", None)

        if root_instance is None:
            self.context["_adjustment_status_log_cache"] = {}
            return self.context["_adjustment_status_log_cache"]

        if isinstance(root_instance, StockAdjustment):
            references = (
                [root_instance.adjustment_number] if root_instance.adjustment_number else []
            )
        else:
            references = [
                instance.adjustment_number
                for instance in root_instance
                if getattr(instance, "adjustment_number", None)
            ]

        status_moves = (
            StockMove.objects.select_related("done_by")
            .filter(reference__in=references, move_type="Status Change")
            .order_by("date", "id")
        )

        cache = {}

        for move in status_moves:
            cache.setdefault(move.reference, []).append(
                {
                    "adjustment_code": move.reference,
                    "name": getattr(move.done_by, "username", None) or "System",
                    "email": getattr(move.done_by, "email", None),
                    "status_from": "_"
                    if move.from_status in {None, "", "Created"}
                    else move.from_status,
                    "status_to": move.to_status or move.destination_location,
                }
            )

        self.context["_adjustment_status_log_cache"] = cache
        return cache

    def get_status_log(self, obj):
        return self._get_status_log_cache().get(obj.adjustment_number, [])


class StockAdjustmentWriteSerializer(serializers.ModelSerializer):
    lines = StockAdjustmentLineSerializer(many=True, required=False)

    class Meta:
        model = StockAdjustment
        fields = "__all__"
        read_only_fields = [
            "adjustment_number",
            "total_value",
            "created_at",
            "updated_at",
        ]

    def _validate_workflow_status_transition(self, previous_status, new_status):
        if new_status == previous_status:
            return

        from inventory.services.adjustment_workflow import get_active_stock_adjustment_workflow

        if not get_active_stock_adjustment_workflow():
            return

        if previous_status == "Pending Approval" and new_status == "Approved":
            raise serializers.ValidationError(
                {
                    "status": (
                        "Workflow approval is required. "
                        "Use POST /api/stock-adjustments/{id}/approve/."
                    )
                }
            )

    def validate(self, data):
        adjustment_type = data.get("adjustment_type") or (
            self.instance.adjustment_type if self.instance else None
        )
        lines = data.get("lines", [])

        STOCK_IN_TYPES = {"stock_in", "return"}
        STOCK_OUT_TYPES = {"stock_out"}

        errors = []
        for i, line in enumerate(lines):
            system_qty = float(line.get("system_qty", 0))
            counted_qty = float(line.get("counted_qty", 0))
            item_name = line.get("item_name") or f"Line {i + 1}"

            if adjustment_type in STOCK_IN_TYPES:
                if counted_qty <= system_qty:
                    errors.append(
                        f"{item_name}: counted quantity ({counted_qty}) must be greater than "
                        f"system quantity ({system_qty}) for adjustment type '{adjustment_type}'."
                    )
            elif adjustment_type in STOCK_OUT_TYPES:
                if counted_qty >= system_qty:
                    errors.append(
                        f"{item_name}: counted quantity ({counted_qty}) must be less than "
                        f"system quantity ({system_qty}) for adjustment type '{adjustment_type}'."
                    )
            # correction: no restriction

        if errors:
            raise serializers.ValidationError({"lines": errors})

        if self.instance:
            previous_status = self.instance.status
            new_status = data.get("status", previous_status)
            self._validate_workflow_status_transition(previous_status, new_status)

        return data

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        with transaction.atomic():
            adj = StockAdjustment.objects.create(**validated_data)
            lines = _replace_line_items(
                adj, lines_data, "lines", StockAdjustmentLine, "adjustment"
            )
            if adj.status == "Approved":
                _apply_stock_adjustment_product_delta(lines)
            _rebuild_adjustment_totals_and_stock_moves(adj, lines)

        return adj

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)
        previous_status = instance.status
        new_status = validated_data.get("status", previous_status)
        self._validate_workflow_status_transition(previous_status, new_status)

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.save()

            lines = _replace_line_items(
                instance, lines_data, "lines", StockAdjustmentLine, "adjustment"
            )

            if previous_status != "Approved" and instance.status == "Approved":
                _apply_stock_adjustment_product_delta(lines)

            _rebuild_adjustment_totals_and_stock_moves(instance, lines)

        return instance


class CycleCountLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = CycleCountLine
        fields = "__all__"
        read_only_fields = ["id", "cycle_count", "variance"]


class CycleCountReadSerializer(serializers.ModelSerializer):
    lines = CycleCountLineSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(
        source="warehouse.name", read_only=True)
    owner_name = serializers.CharField(source="owner.username", read_only=True)
    reviewer_name = serializers.CharField(
        source="reviewer.username", read_only=True)
    item_count = serializers.SerializerMethodField()
    counted_items = serializers.SerializerMethodField()
    variance_count = serializers.SerializerMethodField()
    variance_total = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()

    class Meta:
        model = CycleCount
        fields = "__all__"

    def get_item_count(self, obj):
        return obj.lines.count()

    def get_counted_items(self, obj):
        return obj.lines.exclude(counted_qty__isnull=True).count()

    def get_variance_count(self, obj):
        return obj.lines.exclude(variance__isnull=True).exclude(variance=0).count()

    def get_variance_total(self, obj):
        return round(sum(float(line.variance or 0) for line in obj.lines.all()), 2)

    def get_progress_percent(self, obj):
        item_count = self.get_item_count(obj)

        if not item_count:
            return 0

        return round((self.get_counted_items(obj) / item_count) * 100, 2)


class CycleCountWriteSerializer(serializers.ModelSerializer):
    lines = CycleCountLineSerializer(many=True, required=False)

    class Meta:
        model = CycleCount
        fields = "__all__"
        read_only_fields = ["count_number", "created_at", "updated_at"]

    def validate_lines(self, value):
        if value is not None and not value:
            raise serializers.ValidationError(
                "At least one cycle count line is required."
            )

        return value

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        with transaction.atomic():
            cycle_count = CycleCount.objects.create(**validated_data)
            _replace_line_items(
                cycle_count, lines_data, "lines", CycleCountLine, "cycle_count"
            )

        return cycle_count

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.save()

            _replace_line_items(
                instance, lines_data, "lines", CycleCountLine, "cycle_count"
            )

        return instance


class LotSerialSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    warehouse_name = serializers.CharField(
        source="warehouse.name", read_only=True)

    class Meta:
        model = LotSerial
        fields = "__all__"


class StockMoveDocumentMixin:
    def _get_stock_move_document_cache(self):
        cache = self.context.get("_stock_move_document_cache")

        if cache is not None:
            return cache

        root_instance = getattr(getattr(self, "root", None), "instance", None)

        if root_instance is None:
            root_instance = getattr(self, "instance", None)

        cache = build_stock_move_document_cache(root_instance)
        self.context["_stock_move_document_cache"] = cache
        return cache

    def _get_stock_move_document(self, obj):
        return resolve_stock_move_document(obj, self._get_stock_move_document_cache())


class StockMoveSerializer(StockMoveDocumentMixin, serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    done_by_name = serializers.CharField(
        source="done_by.username", read_only=True)
    done_by_email = serializers.CharField(
        source="done_by.email", read_only=True)
    direction = serializers.SerializerMethodField()
    history_status = serializers.SerializerMethodField()
    document_type = serializers.SerializerMethodField()
    document_id = serializers.SerializerMethodField()

    class Meta:
        model = StockMove
        fields = "__all__"

    def get_direction(self, obj):
        return get_stock_move_direction(obj)

    def get_history_status(self, obj):
        return get_stock_move_history_status(obj)

    def get_document_type(self, obj):
        document = self._get_stock_move_document(obj)
        return document.get("type") if document else None

    def get_document_id(self, obj):
        document = self._get_stock_move_document(obj)
        return document.get("id") if document else None


# ─────────────────────────────────────────────────────────────
#  INTERNAL TRANSFER  serializers
# ─────────────────────────────────────────────────────────────
from inventory.models import InternalTransfer, InternalTransferLine  # noqa: E402


class InternalTransferLineSerializer(serializers.ModelSerializer):
    # Read-only convenience fields
    product_on_hand = serializers.DecimalField(
        source="product.on_hand", read_only=True, max_digits=12, decimal_places=2
    )
    product_unit = serializers.CharField(source="product.uom.name", read_only=True)

    class Meta:
        model = InternalTransferLine
        fields = "__all__"
        read_only_fields = ["id", "transfer"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Runtime fallback: if unit_price is 0 but the linked product has a cost,
        # return the product's current cost so the API never shows 0 for a priced item.
        if not data.get("unit_price") or float(data["unit_price"]) == 0:
            product = instance.product
            if product and product.cost:
                data["unit_price"] = str(product.cost)
        return data


class InternalTransferReadSerializer(serializers.ModelSerializer):
    lines = InternalTransferLineSerializer(many=True, read_only=True)
    from_office_name = serializers.CharField(
        source="from_office.name", read_only=True
    )
    from_office_type = serializers.CharField(
        source="from_office.type", read_only=True
    )
    to_office_name = serializers.CharField(
        source="to_office.name", read_only=True
    )
    to_office_type = serializers.CharField(
        source="to_office.type", read_only=True
    )
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )
    item_count = serializers.SerializerMethodField()
    quantity_total = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()
    status_log = serializers.SerializerMethodField()

    class Meta:
        model = InternalTransfer
        fields = "__all__"

    def get_item_count(self, obj):
        return obj.lines.count()

    def get_quantity_total(self, obj):
        return round(sum(float(line.quantity or 0) for line in obj.lines.all()), 2)

    def get_total_value(self, obj):
        total = sum(
            (line.quantity or 0) * (line.unit_price or 0)
            for line in obj.lines.all()
        )
        if isinstance(total, Decimal):
            total = total.quantize(Decimal("0.01"))
        return float(total)

    def get_status_log(self, obj):
        """Return approval status history from status_log JSONField."""
        log = getattr(obj, 'status_log', None)
        if log and isinstance(log, list):
            return log
        return []


class InternalTransferWriteSerializer(serializers.ModelSerializer):
    lines = InternalTransferLineSerializer(many=True, required=False)

    class Meta:
        model = InternalTransfer
        fields = "__all__"
        read_only_fields = ["transfer_number", "stock_deducted", "stock_received", "created_at", "updated_at"]

    def _save_lines(self, transfer, lines_data):
        if lines_data is None:
            return list(transfer.lines.all())
        transfer.lines.all().delete()
        saved = []
        for item in lines_data:
            item.pop("id", None)
            item.pop("transfer", None)
            # Populate snapshot fields from the linked product
            product = item.get("product")
            if product and hasattr(product, "name"):
                item.setdefault("product_name", product.name)
                item.setdefault("product_code", product.code)
                item.setdefault("unit", product.uom.name if product.uom else "")
                # Auto-fill unit_price from the product's cost if not explicitly provided
                item.setdefault("unit_price", product.cost if product.cost else 0)
            saved.append(InternalTransferLine.objects.create(transfer=transfer, **item))
        return saved

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        with transaction.atomic():
            transfer = InternalTransfer.objects.create(**validated_data)
            self._save_lines(transfer, lines_data)
        return transfer

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            self._save_lines(instance, lines_data)
        return instance
