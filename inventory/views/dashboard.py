from collections import OrderedDict
from decimal import Decimal

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Q, Sum
from django.utils import timezone
from datetime import timedelta
from paginations import Pagination
from inventory.models import (
    Product,
    Item,
    Category,
    Warehouse,
    InventoryValuation,
    GRN,
    GRNLineItem,
    GIN,
    GINLineItem,
    StockTransfer,
    StockAdjustment,
    StockMove,
    QualityCheck,
    QualityAlert,
    LotSerial,
    LocationStock,
    ScrapRecord,
    ReturnRecord,
)
from inventory.serializers import (
    ItemSummarySerializer,
    DashboardKPISerializer,
    InventoryDashboardOverviewSerializer,
    InventoryLogListSerializer,
    InventoryLogAnalyticsSerializer,
    InventoryLogHistorySerializer,
)
from inventory.serializers.operations import reconcile_issued_gin_delivery_history
from inventory.services import item_summary
from procurement.models.grn_models import (
    GoodsReceiptNote as ProcurementGRN,
    GRNItem as ProcurementGRNItem,
)


def _parse_bool_query_param(value):
    if value is None:
        return None

    normalized = str(value).strip().lower()

    if normalized in {"true", "1", "yes"}:
        return True

    if normalized in {"false", "0", "no"}:
        return False

    return None


def _filter_inventory_log_products(request):
    queryset = Product.objects.select_related(
        "category", "subcategory", "uom", "supplier"
    ).all()

    search = request.query_params.get("search", "").strip()
    category_id = request.query_params.get("category")
    subcategory_id = request.query_params.get("subcategory")
    supplier_id = request.query_params.get("supplier")
    stock_status = request.query_params.get("stock_status")
    status = request.query_params.get("status")
    is_active = _parse_bool_query_param(request.query_params.get("is_active"))

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(code__icontains=search)
            | Q(category__name__icontains=search)
            | Q(subcategory__name__icontains=search)
            | Q(supplier__name__icontains=search)
            | Q(office_location__name__icontains=search)
        )

    if category_id:
        queryset = queryset.filter(category_id=category_id)

    if subcategory_id:
        queryset = queryset.filter(subcategory_id=subcategory_id)

    if supplier_id:
        queryset = queryset.filter(supplier_id=supplier_id)

    if stock_status:
        queryset = queryset.filter(stock_status=stock_status)

    if status:
        queryset = queryset.filter(status=status)

    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)

    return queryset


def _inventory_value_expression():
    return ExpressionWrapper(
        F("cost") * F("on_hand"),
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )


def _build_status_totals(queryset):
    return {
        row["status"]: row["total"]
        for row in queryset.values("status").annotate(total=Count("id"))
    }


def _get_vendor_display_name(vendor):
    if not vendor:
        return None

    return (
        getattr(vendor, "name", None)
        or getattr(vendor, "legal_name", None)
        or getattr(vendor, "company_name_bn", None)
        or getattr(vendor, "code", None)
    )


def _get_procurement_grn_event_timestamp(grn):
    event_timestamp = getattr(grn, "updated_at", None) or getattr(
        grn, "created_at", None)

    if event_timestamp is None:
        return timezone.localtime()

    return timezone.localtime(event_timestamp)


def _get_procurement_grn_line_quantity(grn_line):
    accepted_quantity = Decimal(
        str(getattr(grn_line, "accepted_quantity", 0) or 0))

    if accepted_quantity > 0:
        return accepted_quantity

    return Decimal(str(getattr(grn_line, "received_quantity", 0) or 0))


def _get_procurement_grn_actor_name(grn):
    received_by = getattr(grn, "received_by", None)

    if received_by is not None:
        return getattr(received_by, "employee_name", None) or str(received_by)

    created_by = getattr(grn, "created_by", None)

    if created_by is not None:
        return getattr(created_by, "username", None) or getattr(created_by, "email", None)

    return None


def _normalize_analytics_period(value):
    normalized = str(value or "").strip().lower()

    if normalized in {"daily", "weekly", "monthly", "yearly", "custom"}:
        return normalized

    return "monthly"


def _parse_date_param(value):
    """Parse a YYYY-MM-DD string into a date, returning None on failure."""
    if not value:
        return None
    try:
        from datetime import date as _date
        parts = str(value).strip().split("-")
        if len(parts) == 3:
            return _date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, TypeError):
        pass
    return None


def _get_analytics_period_window(period, now):
    now = timezone.localtime(now)

    if period == "daily":
        return (
            now.replace(hour=0, minute=0, second=0, microsecond=0),
            "Today",
        )

    if period == "weekly":
        return (
            (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
            "This Week",
        )

    if period == "yearly":
        return (
            now.replace(month=1, day=1, hour=0, minute=0,
                        second=0, microsecond=0),
            "This Year",
        )

    return (
        now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        "This Month",
    )


def _get_stock_move_flow(move_type, source_location="", destination_location=""):
    normalized_move_type = str(move_type or "").strip()
    normalized_source = str(source_location or "").strip().lower()
    normalized_destination = str(destination_location or "").strip().lower()

    if normalized_move_type in {"Receipt", "Return"}:
        return "in"

    if normalized_move_type in {"Delivery", "Scrap"}:
        return "out"

    if normalized_move_type == "Transfer":
        return "internal"

    if normalized_move_type == "Adjustment":
        if normalized_source == "adjustment increase":
            return "in"

        if normalized_destination == "adjustment decrease":
            return "out"

    if normalized_move_type == "Status Change":
        return "status"

    return "other"


def _iter_analytics_period_buckets(period, period_start, period_end):
    if period == "daily":
        cursor = period_start.replace(minute=0, second=0, microsecond=0)
        last_bucket = period_end.replace(minute=0, second=0, microsecond=0)

        while cursor <= last_bucket:
            yield cursor
            cursor += timedelta(hours=1)
        return

    if period in {"weekly", "monthly"}:
        cursor = period_start.replace(
            hour=0, minute=0, second=0, microsecond=0)
        last_bucket = period_end.replace(
            hour=0, minute=0, second=0, microsecond=0)

        while cursor <= last_bucket:
            yield cursor
            cursor += timedelta(days=1)
        return

    cursor = period_start.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)
    last_bucket = period_end.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)

    while cursor <= last_bucket:
        yield cursor

        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)


def _truncate_analytics_period_bucket(period, value):
    local_value = timezone.localtime(value)

    if period == "daily":
        return local_value.replace(minute=0, second=0, microsecond=0)

    if period in {"weekly", "monthly"}:
        return local_value.replace(hour=0, minute=0, second=0, microsecond=0)

    return local_value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _format_analytics_bucket_label(period, bucket):
    if period == "daily":
        return bucket.strftime("%I %p").lstrip("0")

    if period == "weekly":
        return bucket.strftime("%a")

    if period == "monthly":
        return bucket.strftime("%d %b")

    return bucket.strftime("%b")


def _build_analytics_timeline(period, period_start, period_end):
    zero = Decimal("0")
    timeline = OrderedDict()

    for bucket in _iter_analytics_period_buckets(period, period_start, period_end):
        timeline[bucket] = {
            "bucket_start": bucket,
            "label": _format_analytics_bucket_label(period, bucket),
            "in_count": 0,
            "in_quantity": zero,
            "in_value": zero,
            "out_count": 0,
            "out_quantity": zero,
            "out_value": zero,
            "internal_count": 0,
        }

    return timeline


def _build_top_movement_rows(product_totals):
    return sorted(
        product_totals.values(),
        key=lambda row: (row["value"], row["quantity"], row["move_count"]),
        reverse=True,
    )[:5]


def _filter_inventory_log_history(request):
    queryset = StockMove.objects.select_related("product", "done_by").all()

    search = request.query_params.get("search", "").strip()
    product_id = request.query_params.get("product")
    done_by_id = request.query_params.get("done_by")
    move_type = request.query_params.get("move_type")
    direction = (request.query_params.get("direction") or "").strip().lower()
    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")

    if search:
        queryset = queryset.filter(
            Q(reference__icontains=search)
            | Q(product__name__icontains=search)
            | Q(product__code__icontains=search)
            | Q(source_location__icontains=search)
            | Q(destination_location__icontains=search)
            | Q(done_by__username__icontains=search)
            | Q(done_by__email__icontains=search)
            | Q(from_status__icontains=search)
            | Q(to_status__icontains=search)
        )

    if product_id:
        queryset = queryset.filter(product_id=product_id)

    if done_by_id:
        queryset = queryset.filter(done_by_id=done_by_id)

    if move_type:
        queryset = queryset.filter(move_type=move_type)
    else:
        queryset = queryset.exclude(move_type="Status Change")

    if direction == "in":
        queryset = queryset.filter(
            Q(move_type__in=["Receipt", "Return"])
            | Q(move_type="Adjustment", source_location__iexact="Adjustment Increase")
        )
    elif direction == "out":
        queryset = queryset.filter(
            Q(move_type__in=["Delivery", "Scrap"])
            | Q(move_type="Adjustment", destination_location__iexact="Adjustment Decrease")
        )
    elif direction == "internal":
        queryset = queryset.filter(move_type="Transfer")

    if date_from:
        queryset = queryset.filter(date__date__gte=date_from)

    if date_to:
        queryset = queryset.filter(date__date__lte=date_to)

    return queryset


def _to_decimal(value):
    try:
        return Decimal(str(value or 0))
    except (ArithmeticError, TypeError, ValueError):
        return Decimal("0")


def _normalize_location_label(value):
    return str(value or "").strip().lower()


def _get_warehouse_type_label(warehouse):
    if warehouse is None:
        return None

    display_method = getattr(warehouse, "get_warehouse_type_display", None)

    if callable(display_method):
        return display_method()

    return getattr(warehouse, "warehouse_type", None)


def _resolve_main_office_warehouse(warehouses):
    if not warehouses:
        return None

    def _matches(warehouse, *needles):
        haystacks = {
            _normalize_location_label(getattr(warehouse, "name", "")),
            _normalize_location_label(getattr(warehouse, "code", "")),
        }
        return any(any(needle in haystack for haystack in haystacks) for needle in needles)

    for warehouse in warehouses:
        if _matches(warehouse, "main office"):
            return warehouse

    for warehouse in warehouses:
        if _matches(warehouse, "main"):
            return warehouse

    for warehouse in warehouses:
        if _normalize_location_label(getattr(warehouse, "warehouse_type", "")) == "central":
            return warehouse

    return warehouses[0]


def _build_dashboard_scope(request, warehouses, main_office_warehouse):
    selected_value = str(request.query_params.get("warehouse") or "").strip().lower()

    if selected_value == "main-office":
        warehouse_name = getattr(main_office_warehouse, "name", None) or "Main inventory"
        labels = {label for label in {_normalize_location_label(warehouse_name), "main inventory"} if label}

        return {
            "key": "main-office",
            "label": "Main Office",
            "warehouse_id": getattr(main_office_warehouse, "id", None),
            "warehouse_name": warehouse_name,
            "warehouse_code": getattr(main_office_warehouse, "code", None),
            "warehouse_type": _get_warehouse_type_label(main_office_warehouse),
            "is_main_office": True,
            "scope_type": "main-office",
            "warehouse": main_office_warehouse,
            "labels": labels,
        }

    if selected_value.isdigit():
        selected_id = int(selected_value)
        selected_warehouse = next(
            (warehouse for warehouse in warehouses if warehouse.id == selected_id),
            None,
        )

        if selected_warehouse is not None:
            return {
                "key": f"warehouse:{selected_warehouse.id}",
                "label": selected_warehouse.name,
                "warehouse_id": selected_warehouse.id,
                "warehouse_name": selected_warehouse.name,
                "warehouse_code": selected_warehouse.code,
                "warehouse_type": _get_warehouse_type_label(selected_warehouse),
                "is_main_office": bool(
                    main_office_warehouse and selected_warehouse.id == main_office_warehouse.id
                ),
                "scope_type": "warehouse",
                "warehouse": selected_warehouse,
                "labels": {_normalize_location_label(selected_warehouse.name)},
            }

    return {
        "key": "all",
        "label": "All Warehouses",
        "warehouse_id": None,
        "warehouse_name": None,
        "warehouse_code": None,
        "warehouse_type": None,
        "is_main_office": False,
        "scope_type": "all",
        "warehouse": None,
        "labels": set(),
    }


def _valuation_matches_scope(valuation, scope):
    if scope["scope_type"] == "all":
        return True

    if scope["scope_type"] == "warehouse":
        return valuation.warehouse_id == scope["warehouse_id"]

    if scope["scope_type"] == "main-office":
        if valuation.warehouse_id is None:
            return True

        return valuation.warehouse_id == scope["warehouse_id"]

    return False


def _get_move_scope_direction(move, scope):
    flow = _get_stock_move_flow(
        getattr(move, "move_type", None),
        getattr(move, "source_location", ""),
        getattr(move, "destination_location", ""),
    )

    if flow == "status":
        return None

    if scope["scope_type"] == "all":
        if flow in {"in", "out", "internal"}:
            return flow
        return "other"

    source_label = _normalize_location_label(getattr(move, "source_location", ""))
    destination_label = _normalize_location_label(getattr(move, "destination_location", ""))
    labels = scope["labels"]
    source_match = source_label in labels
    destination_match = destination_label in labels

    if flow == "in":
        return "in" if destination_match else None

    if flow == "out":
        return "out" if source_match else None

    if flow == "internal":
        return "internal" if source_match or destination_match else None

    return "other" if source_match or destination_match else None


def _serialize_move_direction(direction):
    if direction == "in":
        return "In"

    if direction == "out":
        return "Out"

    if direction == "internal":
        return "Internal"

    return "Other"


def _build_dashboard_snapshot(
    scope,
    valuations,
    stock_moves_window,
    recent_moves_pool,
    *,
    active_warehouses_count,
    include_details=True,
):
    product_totals = {}
    total_on_hand_qty = Decimal("0")
    total_stock_value = Decimal("0")

    for valuation in valuations:
        if not _valuation_matches_scope(valuation, scope):
            continue

        product = getattr(valuation, "product", None)

        if product is None:
            continue

        product_id = getattr(product, "id", None)

        if product_id is None:
            continue

        on_hand_qty = _to_decimal(getattr(valuation, "on_hand", 0))
        stock_value = _to_decimal(getattr(valuation, "total_value", 0))
        total_on_hand_qty += on_hand_qty
        total_stock_value += stock_value

        if product_id not in product_totals:
            product_totals[product_id] = {
                "product_id": product_id,
                "product_name": getattr(product, "name", None),
                "product_code": getattr(product, "code", None),
                "on_hand_qty": Decimal("0"),
                "stock_value": Decimal("0"),
                "reorder_level": _to_decimal(getattr(product, "reorder_level", 0)),
                "max_stock": _to_decimal(getattr(product, "max_stock", 0)),
            }

        product_totals[product_id]["on_hand_qty"] += on_hand_qty
        product_totals[product_id]["stock_value"] += stock_value

    healthy_count = 0
    low_stock_count = 0
    out_of_stock_count = 0
    overstock_count = 0

    for row in product_totals.values():
        on_hand_qty = row["on_hand_qty"]
        reorder_level = row["reorder_level"]
        max_stock = row["max_stock"]

        if on_hand_qty <= 0:
            out_of_stock_count += 1
        elif reorder_level > 0 and on_hand_qty <= reorder_level:
            low_stock_count += 1
        elif max_stock > 0 and on_hand_qty > max_stock:
            overstock_count += 1
        else:
            healthy_count += 1

    today = timezone.localdate()
    timeline_start = today - timedelta(days=6)
    timeline = OrderedDict()

    for offset in range(7):
        bucket_day = timeline_start + timedelta(days=offset)
        timeline[bucket_day] = {
            "date": bucket_day.isoformat(),
            "label": bucket_day.strftime("%d %b"),
            "inbound_qty": Decimal("0"),
            "outbound_qty": Decimal("0"),
            "internal_qty": Decimal("0"),
            "movement_count": 0,
        }

    inbound_count = 0
    outbound_count = 0
    internal_count = 0
    inbound_qty = Decimal("0")
    outbound_qty = Decimal("0")
    internal_qty = Decimal("0")
    relevant_move_count = 0

    for move in stock_moves_window:
        direction = _get_move_scope_direction(move, scope)

        if direction is None:
            continue

        relevant_move_count += 1
        quantity = _to_decimal(getattr(move, "quantity", 0))
        move_day = timezone.localtime(getattr(move, "date")).date()

        if direction == "in":
            inbound_count += 1
            inbound_qty += quantity
        elif direction == "out":
            outbound_count += 1
            outbound_qty += quantity
        elif direction == "internal":
            internal_count += 1
            internal_qty += quantity

        bucket = timeline.get(move_day)

        if bucket is None:
            continue

        bucket["movement_count"] += 1

        if direction == "in":
            bucket["inbound_qty"] += quantity
        elif direction == "out":
            bucket["outbound_qty"] += quantity
        elif direction == "internal":
            bucket["internal_qty"] += quantity

    recent_moves = []

    if include_details:
        for move in recent_moves_pool:
            direction = _get_move_scope_direction(move, scope)

            if direction is None:
                continue

            recent_moves.append(
                {
                    "id": move.id,
                    "reference": move.reference,
                    "product_name": getattr(move.product, "name", None),
                    "product_code": getattr(move.product, "code", None),
                    "move_type": move.move_type,
                    "direction": _serialize_move_direction(direction),
                    "quantity": move.quantity,
                    "source_location": move.source_location,
                    "destination_location": move.destination_location,
                    "date": move.date,
                }
            )

            if len(recent_moves) >= 6:
                break

    summary = {
        "warehouse_count": active_warehouses_count
        if scope["scope_type"] == "all"
        else (1 if scope["warehouse_id"] or product_totals else 0),
        "sku_count": len(product_totals),
        "on_hand_qty": total_on_hand_qty,
        "stock_value": total_stock_value,
        "healthy_items": healthy_count,
        "low_stock_items": low_stock_count,
        "out_of_stock_items": out_of_stock_count,
        "overstock_items": overstock_count,
        "inbound_count_30d": inbound_count,
        "inbound_qty_30d": inbound_qty,
        "outbound_count_30d": outbound_count,
        "outbound_qty_30d": outbound_qty,
        "internal_count_30d": internal_count,
        "internal_qty_30d": internal_qty,
        "movement_count_30d": relevant_move_count,
    }

    stock_status_breakdown = [
        {"label": "Healthy", "count": healthy_count},
        {"label": "Low Stock", "count": low_stock_count},
        {"label": "Out of Stock", "count": out_of_stock_count},
        {"label": "Overstock", "count": overstock_count},
    ]

    movement_mix = [
        {"label": "Stock In", "count": inbound_count, "quantity": inbound_qty},
        {"label": "Stock Out", "count": outbound_count, "quantity": outbound_qty},
        {"label": "Internal", "count": internal_count, "quantity": internal_qty},
    ]

    top_products = []

    if include_details:
        top_products = sorted(
            product_totals.values(),
            key=lambda row: (row["stock_value"], row["on_hand_qty"], row["product_name"] or ""),
            reverse=True,
        )[:6]

        top_products = [
            {
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "product_code": row["product_code"],
                "on_hand_qty": row["on_hand_qty"],
                "stock_value": row["stock_value"],
            }
            for row in top_products
        ]

    return {
        "summary": summary,
        "stock_status_breakdown": stock_status_breakdown,
        "movement_mix": movement_mix,
        "movement_timeline": list(timeline.values()) if include_details else [],
        "top_products": top_products,
        "recent_moves": recent_moves,
    }


def _build_warehouse_options(warehouses, valuations, stock_moves_window, main_office_warehouse):
    options = []

    for warehouse in warehouses:
        scope = {
            "key": f"warehouse:{warehouse.id}",
            "label": warehouse.name,
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "warehouse_code": warehouse.code,
            "warehouse_type": _get_warehouse_type_label(warehouse),
            "is_main_office": bool(main_office_warehouse and warehouse.id == main_office_warehouse.id),
            "scope_type": "warehouse",
            "warehouse": warehouse,
            "labels": {_normalize_location_label(warehouse.name)},
        }
        snapshot = _build_dashboard_snapshot(
            scope,
            valuations,
            stock_moves_window,
            [],
            active_warehouses_count=1,
            include_details=False,
        )

        options.append(
            {
                "id": warehouse.id,
                "name": warehouse.name,
                "code": warehouse.code,
                "warehouse_type": _get_warehouse_type_label(warehouse),
                "is_main_office": bool(main_office_warehouse and warehouse.id == main_office_warehouse.id),
                **snapshot["summary"],
            }
        )

    return sorted(
        options,
        key=lambda row: (row["stock_value"], row["on_hand_qty"], row["name"]),
        reverse=True,
    )


def _build_operational_overview(scope):
    pending_receipts = GRN.objects.filter(
        status__in=["Draft", "Pending Quality Check", "Pending Approval"]
    )
    open_issues = GIN.objects.filter(status__in=["Draft", "Pending Approval", "Approved"])
    transfers_in_transit = StockTransfer.objects.filter(status="In Transit")
    pending_adjustments = StockAdjustment.objects.filter(status__in=["Draft", "Pending Approval"])

    if scope["scope_type"] == "warehouse":
        pending_receipts = pending_receipts.filter(warehouse_id=scope["warehouse_id"])
        open_issues = open_issues.filter(warehouse_id=scope["warehouse_id"])
        transfers_in_transit = transfers_in_transit.filter(
            Q(from_warehouse_id=scope["warehouse_id"]) | Q(to_warehouse_id=scope["warehouse_id"])
        )
        pending_adjustments = pending_adjustments.filter(warehouse_id=scope["warehouse_id"])
    elif scope["scope_type"] == "main-office":
        warehouse_id = scope["warehouse_id"]
        pending_receipts_filter = Q(warehouse__isnull=True)
        open_issues_filter = Q(warehouse__isnull=True)
        transfer_filter = Q(from_warehouse__isnull=True) | Q(to_warehouse__isnull=True)
        adjustment_filter = Q(warehouse__isnull=True)

        if warehouse_id:
            pending_receipts_filter |= Q(warehouse_id=warehouse_id)
            open_issues_filter |= Q(warehouse_id=warehouse_id)
            transfer_filter |= Q(from_warehouse_id=warehouse_id) | Q(to_warehouse_id=warehouse_id)
            adjustment_filter |= Q(warehouse_id=warehouse_id)

        pending_receipts = pending_receipts.filter(pending_receipts_filter)
        open_issues = open_issues.filter(open_issues_filter)
        transfers_in_transit = transfers_in_transit.filter(transfer_filter)
        pending_adjustments = pending_adjustments.filter(adjustment_filter)

    return {
        "pending_receipts": pending_receipts.count(),
        "open_issues": open_issues.count(),
        "transfers_in_transit": transfers_in_transit.count(),
        "pending_adjustments": pending_adjustments.count(),
    }


class ItemSummaryAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        data = item_summary()
        serializer = ItemSummarySerializer(data)
        return Response(serializer.data)


class DashboardKPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        today = timezone.now().date()
        thirty_days = today + timedelta(days=30)
        data = {
            "total_products": Product.objects.count(),
            "active_products": Product.objects.filter(status="Active").count(),
            "total_warehouses": Warehouse.objects.filter(is_active=True).count(),
            "total_stock_value": Product.objects.aggregate(
                val=Sum("on_hand", default=0)
            )["val"]
            or 0,
            "low_stock_items": Product.objects.filter(stock_status="Low Stock").count(),
            "out_of_stock_items": Product.objects.filter(
                stock_status="Out of Stock"
            ).count(),
            "pending_grns": GRN.objects.filter(status="Draft").count(),
            "pending_gins": GIN.objects.filter(status="Draft").count(),
            "transfers_in_transit": StockTransfer.objects.filter(
                status="In Transit"
            ).count(),
            "pending_quality_checks": QualityCheck.objects.filter(
                status="Pending"
            ).count(),
            "total_stock_moves_today": StockMove.objects.filter(
                date__date=today
            ).count(),
            "total_categories": Category.objects.filter(level="Main").count(),
            "pending_adjustments": StockAdjustment.objects.filter(
                status="Draft"
            ).count(),
            "quality_alerts": QualityAlert.objects.filter(status="New").count(),
            "expiring_soon": LotSerial.objects.filter(
                expiry_date__lte=thirty_days, expiry_date__gte=today
            ).count(),
        }
        serializer = DashboardKPISerializer(data)
        return Response(serializer.data)


class InventoryDashboardOverviewView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        generated_at = timezone.localtime()
        window_ended_at = generated_at
        window_started_at = generated_at - timedelta(days=30)

        warehouses = list(Warehouse.objects.filter(is_active=True).order_by("name", "code"))
        main_office_warehouse = _resolve_main_office_warehouse(warehouses)
        scope = _build_dashboard_scope(request, warehouses, main_office_warehouse)

        valuations = list(
            InventoryValuation.objects.select_related("warehouse", "product").all()
        )
        stock_moves_window = list(
            StockMove.objects.select_related("product", "done_by")
            .exclude(move_type="Status Change")
            .filter(date__gte=window_started_at)
            .order_by("-date", "-id")
        )
        recent_moves_pool = list(
            StockMove.objects.select_related("product", "done_by")
            .exclude(move_type="Status Change")
            .order_by("-date", "-id")[:200]
        )

        selected_snapshot = _build_dashboard_snapshot(
            scope,
            valuations,
            stock_moves_window,
            recent_moves_pool,
            active_warehouses_count=len(warehouses),
        )

        main_office_scope = _build_dashboard_scope(
            type("Request", (), {"query_params": {"warehouse": "main-office"}})(),
            warehouses,
            main_office_warehouse,
        )
        main_office_snapshot = _build_dashboard_snapshot(
            main_office_scope,
            valuations,
            stock_moves_window,
            recent_moves_pool,
            active_warehouses_count=1,
        )

        main_office_overview = {
            "label": "Main Office",
            "warehouse_id": main_office_scope["warehouse_id"],
            "warehouse_name": main_office_scope["warehouse_name"],
            "warehouse_code": main_office_scope["warehouse_code"],
            "warehouse_type": main_office_scope["warehouse_type"],
            "is_main_office": True,
            **main_office_snapshot["summary"],
        }

        # ── Totals for frontend KPI cards — sourced from LocationStock ──────
        # LocationStock is the single source of truth for on-hand quantities.
        # Using it directly (rather than Product.on_hand) guarantees that
        # total_on_hand always equals the sum of per-office on_hand_total values.
        from django.db.models import Sum as _Sum, F as _F, DecimalField as _DecimalField, ExpressionWrapper as _EW
        ls_totals_agg = (
            LocationStock.objects
            .filter(product__is_active=True)
            .aggregate(
                total_on_hand=_Sum("quantity", default=0),
                total_value=_Sum(
                    _EW(
                        _F("product__cost") * _F("quantity"),
                        output_field=_DecimalField(max_digits=18, decimal_places=2),
                    ),
                    default=0,
                ),
            )
        )
        totals = {
            "total_on_hand": float(ls_totals_agg["total_on_hand"] or 0),
            "total_value": float(ls_totals_agg["total_value"] or 0),
            "total_products": Product.objects.filter(is_active=True).count(),
        }

        # ── Stock grouped by LocationStock (source of truth) for bar chart ───
        from django.db.models import Count as _Count
        ls_offices_qs = (
            LocationStock.objects.filter(quantity__gt=0)
            .values(
                location=_F("office_location__name"),
                office_type=_F("office_location__type"),
            )
            .annotate(
                product_count=_Count("product_id", distinct=True),
                on_hand_total=_Sum("quantity"),
                stock_value=_Sum(
                    _EW(
                        _F("product__cost") * _F("quantity"),
                        output_field=_DecimalField(max_digits=18, decimal_places=2),
                    )
                ),
            )
            .order_by("-stock_value")
        )
        offices_list = [
            {
                "location": row["location"] or "Unassigned",
                "office_type": row["office_type"] or "",
                "product_count": row["product_count"] or 0,
                "on_hand_total": float(row["on_hand_total"] or 0),
                "stock_value": float(row["stock_value"] or 0),
            }
            for row in ls_offices_qs
        ]

        data = {
            "generated_at": generated_at,
            "window_started_at": window_started_at,
            "window_ended_at": window_ended_at,
            "selected_scope": {
                "key": scope["key"],
                "label": scope["label"],
                "warehouse_id": scope["warehouse_id"],
                "warehouse_name": scope["warehouse_name"],
                "warehouse_code": scope["warehouse_code"],
                "warehouse_type": scope["warehouse_type"],
                "is_main_office": scope["is_main_office"],
            },
            "summary": selected_snapshot["summary"],
            "totals": totals,
            "offices": offices_list,
            "main_office_overview": main_office_overview,
            "warehouse_options": _build_warehouse_options(
                warehouses,
                valuations,
                stock_moves_window,
                main_office_warehouse,
            ),
            "stock_status_breakdown": selected_snapshot["stock_status_breakdown"],
            "movement_mix": selected_snapshot["movement_mix"],
            "movement_timeline": selected_snapshot["movement_timeline"],
            "top_products": selected_snapshot["top_products"],
            "recent_moves": selected_snapshot["recent_moves"],
            "operational_overview": _build_operational_overview(scope),
        }
        serializer = InventoryDashboardOverviewSerializer(data)
        return Response(serializer.data)


class ABCAnalysisView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        products = Product.objects.filter(status="Active").values(
            "id", "name", "cost", "on_hand"
        )
        items = []
        for p in products:
            annual_value = float(p["cost"] or 0) * \
                float(p["on_hand"] or 0) * 12
            if annual_value > 0:
                items.append({
                    "product_id": p["id"],
                    "product_name": p["name"],
                    "annual_value": annual_value,
                })
        items.sort(key=lambda x: x["annual_value"], reverse=True)
        total = sum(i["annual_value"] for i in items)
        cumulative = 0
        for item in items:
            pct = (item["annual_value"] / total * 100) if total else 0
            cumulative += pct
            item["percentage"] = round(pct, 1)
            item["cumulative"] = round(cumulative, 1)
            if cumulative <= 80:
                item["class"] = "A"
            elif cumulative <= 95:
                item["class"] = "B"
            else:
                item["class"] = "C"
        return Response(items)


class ForecastedStockView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        products = Product.objects.filter(status="Active").values(
            "id", "name", "on_hand"
        )
        result = []
        for p in products:
            current = float(p["on_hand"] or 0)
            incoming = float(
                GRN.objects.filter(
                    status="Draft", line_items__product_id=p["id"]
                ).aggregate(total=Sum("line_items__quantity", default=0))["total"] or 0
            )
            outgoing = float(
                GIN.objects.filter(
                    status="Draft", line_items__product_id=p["id"]
                ).aggregate(total=Sum("line_items__quantity", default=0))["total"] or 0
            )
            forecasted = current + incoming - outgoing
            daily_usage = outgoing / 30 if outgoing else 0
            days = int(forecasted / daily_usage) if daily_usage > 0 else 999
            status = "Low" if days < 30 else "Adequate"
            result.append({
                "product_id": p["id"],
                "product_name": p["name"],
                "current_stock": current,
                "incoming": incoming,
                "outgoing": outgoing,
                "forecasted": forecasted,
                "days_of_stock": min(days, 999),
                "status": status,
            })
        result.sort(key=lambda x: x["days_of_stock"])
        return Response(result)


class StockAgingView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        today = timezone.now().date()
        products = Product.objects.filter(status="Active", on_hand__gt=0).values(
            "id", "name", "on_hand"
        )
        result = []
        for p in products:
            lots = LotSerial.objects.filter(product_id=p["id"])
            age_buckets = {
                "age_0_30": 0, "age_31_60": 0, "age_61_90": 0,
                "age_91_180": 0, "age_over_180": 0
            }
            oldest = None
            for lot in lots:
                lot_date = lot.manufacture_date or lot.created_at.date()
                if oldest is None or lot_date < oldest:
                    oldest = lot_date
                age_days = (today - lot_date).days
                qty = float(lot.quantity or 0)
                if age_days <= 30:
                    age_buckets["age_0_30"] += qty
                elif age_days <= 60:
                    age_buckets["age_31_60"] += qty
                elif age_days <= 90:
                    age_buckets["age_61_90"] += qty
                elif age_days <= 180:
                    age_buckets["age_91_180"] += qty
                else:
                    age_buckets["age_over_180"] += qty
            result.append({
                "product_id": p["id"],
                "product_name": p["name"],
                "total_qty": float(p["on_hand"]),
                **age_buckets,
                "oldest_lot_date": str(oldest) if oldest else None,
            })
        return Response(result)


class InventoryLogListView(APIView):
    permission_classes = [AllowAny]
    pagination_class = Pagination

    def get(self, request):
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        queryset = _filter_inventory_log_products(request).annotate(
            inventory_value=_inventory_value_expression(),
            last_movement_date=Max("stockmove__date"),
            movement_count_30d=Count(
                "stockmove",
                filter=Q(stockmove__date__gte=thirty_days_ago),
                distinct=True,
            ),
        )

        ordering = request.query_params.get("ordering", "-updated_at")
        allowed_ordering = {
            "name": "name",
            "-name": "-name",
            "code": "code",
            "-code": "-code",
            "on_hand": "on_hand",
            "-on_hand": "-on_hand",
            "available": "available",
            "-available": "-available",
            "inventory_value": "inventory_value",
            "-inventory_value": "-inventory_value",
            "last_movement_date": "last_movement_date",
            "-last_movement_date": "-last_movement_date",
            "movement_count_30d": "movement_count_30d",
            "-movement_count_30d": "-movement_count_30d",
            "updated_at": "updated_at",
            "-updated_at": "-updated_at",
        }
        queryset = queryset.order_by(
            allowed_ordering.get(ordering, "-updated_at"), "-id")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = InventoryLogListSerializer(
            page if page is not None else queryset, many=True)

        if page is not None:
            return paginator.get_paginated_response(serializer.data)

        return Response(serializer.data)


class InventoryLogAnalyticsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        reconcile_issued_gin_delivery_history()

        now = timezone.localtime()
        today = now.date()
        selected_period = _normalize_analytics_period(
            request.query_params.get("period"))

        # Custom date range support
        custom_date_from = _parse_date_param(request.query_params.get("date_from"))
        custom_date_to = _parse_date_param(request.query_params.get("date_to"))

        if selected_period == "custom" and custom_date_from and custom_date_to:
            if custom_date_from > custom_date_to:
                custom_date_from, custom_date_to = custom_date_to, custom_date_from
            period_start = timezone.make_aware(
                timezone.datetime(custom_date_from.year, custom_date_from.month, custom_date_from.day, 0, 0, 0)
            )
            period_end_date = custom_date_to
            period_label = f"{custom_date_from.strftime('%d %b %Y')} – {custom_date_to.strftime('%d %b %Y')}"
        else:
            period_start, period_label = _get_analytics_period_window(selected_period, now)
            period_end_date = today

        thirty_days_ago = now - timedelta(days=30)
        ninety_days_ago = now - timedelta(days=90)
        expiring_limit = today + timedelta(days=30)

        products = _filter_inventory_log_products(request)
        items = Item.objects.filter(id__in=products.values("id"))
        products_with_inventory = products.annotate(
            inventory_value=_inventory_value_expression(),
        )
        products_with_metrics = products_with_inventory.annotate(
            last_movement_date=Max("stockmove__date"),
        )
        history_queryset = _filter_inventory_log_history(request).filter(
            Q(product__in=products) | Q(product__isnull=True)
        )
        period_history_queryset = history_queryset.filter(
            date__gte=period_start,
            date__lte=now,
        )
        gin_queryset = (
            GIN.objects.select_related(
                "warehouse", "requested_by", "approved_by")
            .prefetch_related("line_items", "line_items__product")
            .filter(line_items__product__in=products)
            .distinct()
        )
        procurement_grn_queryset = (
            ProcurementGRN.objects.select_related(
                "supplier", "received_by", "created_by")
            .prefetch_related("grn_items", "grn_items__item")
            .filter(grn_items__item__in=products)
            .distinct()
        )
        gin_line_queryset = GINLineItem.objects.filter(gin__in=gin_queryset)
        issued_gin_line_queryset = gin_line_queryset.filter(
            gin__status="Issued")
        procurement_grn_line_queryset = ProcurementGRNItem.objects.select_related(
            "grn", "item", "grn__supplier", "grn__received_by", "grn__created_by"
        ).filter(
            grn__in=procurement_grn_queryset,
            item__in=products,
        )
        verified_procurement_grn_line_queryset = procurement_grn_line_queryset.filter(
            grn__status="Verified"
        )
        rolling_recent_moves = StockMove.objects.select_related("product", "done_by").filter(
            product__in=products,
            date__gte=thirty_days_ago,
        ).exclude(move_type__in=["Status Change", "Receipt"])
        period_moves = list(
            StockMove.objects.select_related("product", "done_by")
            .filter(
                product__in=products,
                date__gte=period_start,
                date__lte=now,
            )
            .exclude(move_type__in=["Status Change", "Receipt"])
            .order_by("-date", "-id")
        )
        latest_verified_grn_events = verified_procurement_grn_line_queryset.values(
            "item_id"
        ).annotate(latest_verified_at=Max("grn__updated_at"))
        latest_verified_grn_event_map = {
            row["item_id"]: timezone.localtime(row["latest_verified_at"])
            for row in latest_verified_grn_events
            if row["item_id"] and row["latest_verified_at"]
        }
        verified_grn_lines = list(verified_procurement_grn_line_queryset)
        rolling_verified_grn_lines = [
            grn_line
            for grn_line in verified_grn_lines
            if thirty_days_ago <= _get_procurement_grn_event_timestamp(grn_line.grn) <= now
        ]
        verified_period_grn_lines = [
            grn_line
            for grn_line in verified_grn_lines
            if period_start <= _get_procurement_grn_event_timestamp(grn_line.grn) <= now
        ]

        stock_totals = products_with_inventory.aggregate(
            total_stock_value=Sum("inventory_value", default=0),
            total_on_hand_qty=Sum("on_hand", default=0),
            total_available_qty=Sum("available", default=0),
        )
        movement_dates = []
        non_moving_items = 0

        for product in products_with_metrics:
            last_movement_date = product.last_movement_date
            latest_verified_grn_event = latest_verified_grn_event_map.get(
                product.id)

            if latest_verified_grn_event and (
                last_movement_date is None or latest_verified_grn_event > last_movement_date
            ):
                last_movement_date = latest_verified_grn_event

            if last_movement_date is not None:
                movement_dates.append(last_movement_date)

            if last_movement_date is None or last_movement_date < ninety_days_ago:
                non_moving_items += 1

        avg_days_since_movement = (
            round(sum((now - movement_date).days for movement_date in movement_dates) /
                  len(movement_dates), 1)
            if movement_dates
            else 0.0
        )
        stocked_products = products.filter(on_hand__gt=0).count()
        active_products = products.filter(is_active=True).count()
        history_direction_counts = {
            "stock_in": period_history_queryset.filter(
                Q(move_type__in=["Receipt", "Return"])
                | Q(move_type="Adjustment", source_location__iexact="Adjustment Increase")
            ).count(),
            "stock_out": period_history_queryset.filter(
                Q(move_type__in=["Delivery", "Scrap"])
                | Q(move_type="Adjustment", destination_location__iexact="Adjustment Decrease")
            ).count(),
            "stock_transfer": period_history_queryset.filter(move_type="Transfer").count(),
        }
        gin_status_totals = _build_status_totals(gin_queryset)
        grn_status_totals = _build_status_totals(procurement_grn_queryset)
        gin_period_queryset = gin_queryset.filter(
            issue_date__gte=period_start.date(), issue_date__lte=today)
        grn_period_queryset = procurement_grn_queryset.filter(
            updated_at__gte=period_start,
            updated_at__lte=now,
        )
        verified_grn_period_queryset = grn_period_queryset.filter(
            status="Verified")
        gin_value_expression = ExpressionWrapper(
            F("issued_qty") * F("unit_price"),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )
        verified_grn_received_quantity_total = sum(
            (Decimal(str(line.received_quantity or 0))
             for line in verified_grn_lines),
            Decimal("0"),
        )
        verified_grn_stocked_quantity_total = sum(
            (_get_procurement_grn_line_quantity(line)
             for line in verified_grn_lines),
            Decimal("0"),
        )
        verified_grn_rejected_quantity_total = sum(
            (Decimal(str(line.rejected_quantity or 0))
             for line in verified_grn_lines),
            Decimal("0"),
        )
        verified_grn_value_total = sum(
            (
                _get_procurement_grn_line_quantity(line)
                * Decimal(str(line.unit_price or 0))
                for line in verified_grn_lines
            ),
            Decimal("0"),
        )
        source_overview = {
            "items": {
                "total_records": items.count(),
                "active_records": items.filter(is_active=True).count(),
                "stocked_records": items.filter(on_hand__gt=0).count(),
                "low_stock_records": items.filter(stock_status="Low Stock").count(),
                "out_of_stock_records": items.filter(stock_status="Out of Stock").count(),
                "overstock_records": items.filter(stock_status="Overstock").count(),
                "total_on_hand_qty": stock_totals["total_on_hand_qty"] or 0,
                "total_available_qty": stock_totals["total_available_qty"] or 0,
                "total_stock_value": stock_totals["total_stock_value"] or 0,
            },
            "history": {
                "total_rows": history_queryset.count(),
                "window_rows": period_history_queryset.count(),
                "stock_in_rows": history_direction_counts["stock_in"],
                "stock_out_rows": history_direction_counts["stock_out"],
                "stock_transfer_rows": history_direction_counts["stock_transfer"],
                "latest_logged_at": history_queryset.order_by("-created_at", "-id").values_list("created_at", flat=True).first(),
            },
            "gin": {
                "total_documents": gin_queryset.count(),
                "window_documents": gin_period_queryset.count(),
                "issued_documents": gin_status_totals.get("Issued", 0),
                "draft_documents": gin_status_totals.get("Draft", 0),
                "cancelled_documents": gin_status_totals.get("Cancelled", 0),
                "issued_window_documents": gin_period_queryset.filter(status="Issued").count(),
                "line_items_total": gin_line_queryset.count(),
                "issued_quantity_total": issued_gin_line_queryset.aggregate(total=Sum("issued_qty", default=0))["total"] or 0,
                "issued_value_total": issued_gin_line_queryset.aggregate(total=Sum(gin_value_expression, default=0))["total"] or 0,
                "status_totals": gin_status_totals,
            },
            "grn": {
                "total_documents": procurement_grn_queryset.count(),
                "window_documents": grn_period_queryset.count(),
                "verified_documents": grn_status_totals.get("Verified", 0),
                "verified_window_documents": verified_grn_period_queryset.count(),
                "line_items_total": procurement_grn_line_queryset.count(),
                "received_quantity_total": verified_grn_received_quantity_total,
                "accepted_quantity_total": verified_grn_stocked_quantity_total,
                "rejected_quantity_total": verified_grn_rejected_quantity_total,
                "accepted_value_total": verified_grn_value_total,
                "status_totals": grn_status_totals,
            },
        }

        zero = Decimal("0")
        movement_summary = {
            "total_move_count": 0,
            "total_in_count": 0,
            "total_in_quantity": zero,
            "total_in_value": zero,
            "total_out_count": 0,
            "total_out_quantity": zero,
            "total_out_value": zero,
            "internal_count": 0,
            "net_quantity": zero,
            "net_value": zero,
        }
        timeline_buckets = _build_analytics_timeline(
            selected_period, period_start, now)
        inbound_products = {}
        outbound_products = {}
        recent_move_candidates = []

        for grn_line in verified_period_grn_lines:
            receipt_quantity = _get_procurement_grn_line_quantity(grn_line)

            if receipt_quantity <= 0:
                continue

            receipt_product = grn_line.item
            receipt_event_time = _get_procurement_grn_event_timestamp(
                grn_line.grn)
            receipt_unit_cost = Decimal(
                str(grn_line.unit_price or getattr(
                    receipt_product, "cost", 0) or 0)
            )
            receipt_value = receipt_quantity * receipt_unit_cost
            bucket = timeline_buckets.get(
                _truncate_analytics_period_bucket(
                    selected_period, receipt_event_time)
            )

            movement_summary["total_move_count"] += 1
            movement_summary["total_in_count"] += 1
            movement_summary["total_in_quantity"] += receipt_quantity
            movement_summary["total_in_value"] += receipt_value

            if bucket is not None:
                bucket["in_count"] += 1
                bucket["in_quantity"] += receipt_quantity
                bucket["in_value"] += receipt_value

            if receipt_product is not None:
                product_entry = inbound_products.setdefault(
                    receipt_product.id,
                    {
                        "product_id": receipt_product.id,
                        "product_code": getattr(receipt_product, "code", None),
                        "product_name": getattr(receipt_product, "name", None),
                        "move_count": 0,
                        "quantity": zero,
                        "value": zero,
                    },
                )
                product_entry["move_count"] += 1
                product_entry["quantity"] += receipt_quantity
                product_entry["value"] += receipt_value

            recent_move_candidates.append(
                {
                    "id": grn_line.id,
                    "reference": grn_line.grn.grn_number,
                    "date": receipt_event_time,
                    "product_name": getattr(receipt_product, "name", None),
                    "move_type": "Receipt",
                    "quantity": receipt_quantity,
                    "source_location": _get_vendor_display_name(grn_line.grn.supplier)
                    or "Vendor receipt",
                    "destination_location": (getattr(receipt_product, "location", None) or "").strip()
                    or "Main inventory",
                    "done_by_name": _get_procurement_grn_actor_name(grn_line.grn),
                    "sort_id": grn_line.id,
                }
            )

        for move in period_moves:
            flow = _get_stock_move_flow(
                move.move_type,
                source_location=move.source_location,
                destination_location=move.destination_location,
            )
            quantity = move.quantity or zero
            unit_cost = (
                getattr(move.product, "cost", None)
                if getattr(move, "product", None) is not None
                else None
            ) or zero
            move_value = quantity * unit_cost
            bucket = timeline_buckets.get(
                _truncate_analytics_period_bucket(selected_period, move.date))

            if flow in {"in", "out", "internal"}:
                movement_summary["total_move_count"] += 1
                recent_move_candidates.append(
                    {
                        "id": move.id,
                        "reference": move.reference,
                        "date": move.date,
                        "product_name": move.product.name if move.product else None,
                        "move_type": move.move_type,
                        "quantity": move.quantity,
                        "source_location": move.source_location,
                        "destination_location": move.destination_location,
                        "done_by_name": move.done_by.username if move.done_by else None,
                        "sort_id": move.id,
                    }
                )

            if flow == "internal":
                movement_summary["internal_count"] += 1
                if bucket is not None:
                    bucket["internal_count"] += 1
                continue

            if flow not in {"in", "out"}:
                continue

            quantity_key = f"total_{flow}_quantity"
            value_key = f"total_{flow}_value"
            count_key = f"total_{flow}_count"

            movement_summary[count_key] += 1
            movement_summary[quantity_key] += quantity
            movement_summary[value_key] += move_value

            if bucket is not None:
                bucket[f"{flow}_count"] += 1
                bucket[f"{flow}_quantity"] += quantity
                bucket[f"{flow}_value"] += move_value

            if not move.product_id:
                continue

            product_totals = inbound_products if flow == "in" else outbound_products
            product_entry = product_totals.setdefault(
                move.product_id,
                {
                    "product_id": move.product_id,
                    "product_code": getattr(move.product, "code", None),
                    "product_name": getattr(move.product, "name", None),
                    "move_count": 0,
                    "quantity": zero,
                    "value": zero,
                },
            )
            product_entry["move_count"] += 1
            product_entry["quantity"] += quantity
            product_entry["value"] += move_value

        movement_summary["net_quantity"] = (
            movement_summary["total_in_quantity"] -
            movement_summary["total_out_quantity"]
        )
        movement_summary["net_value"] = (
            movement_summary["total_in_value"] -
            movement_summary["total_out_value"]
        )

        movement_timeline = []
        for bucket in timeline_buckets.values():
            bucket["net_quantity"] = bucket["in_quantity"] - \
                bucket["out_quantity"]
            bucket["net_value"] = bucket["in_value"] - bucket["out_value"]
            movement_timeline.append(bucket)

        movement_mix = [
            {
                "key": "stock_in",
                "label": "Stock In",
                "count": movement_summary["total_in_count"],
                "quantity": movement_summary["total_in_quantity"],
                "value": movement_summary["total_in_value"],
            },
            {
                "key": "stock_out",
                "label": "Stock Out",
                "count": movement_summary["total_out_count"],
                "quantity": movement_summary["total_out_quantity"],
                "value": movement_summary["total_out_value"],
            },
            {
                "key": "internal",
                "label": "Internal Transfer",
                "count": movement_summary["internal_count"],
                "quantity": zero,
                "value": zero,
            },
        ]

        category_breakdown = [
            {
                "category_name": row["category__name"] or "Uncategorized",
                "sku_count": row["sku_count"],
                "on_hand": row["on_hand"] or 0,
                "stock_value": row["stock_value"] or 0,
            }
            for row in products_with_inventory.values("category__name")
            .annotate(
                sku_count=Count("id"),
                on_hand=Sum("on_hand", default=0),
                stock_value=Sum("inventory_value", default=0),
            )
            .order_by("-stock_value", "category__name")[:6]
        ]
        stock_status_breakdown = [
            {
                "stock_status": row["stock_status"] or "Unknown",
                "sku_count": row["sku_count"],
                "on_hand": row["on_hand"] or 0,
                "stock_value": row["stock_value"] or 0,
            }
            for row in products_with_inventory.values("stock_status")
            .annotate(
                sku_count=Count("id"),
                on_hand=Sum("on_hand", default=0),
                stock_value=Sum("inventory_value", default=0),
            )
            .order_by("-sku_count", "stock_status")
        ]
        top_inventory = [
            {
                "product_id": product.id,
                "product_code": product.code,
                "product_name": product.name,
                "inventory_value": product.inventory_value,
                "on_hand": product.on_hand,
                "stock_status": product.stock_status,
            }
            for product in products_with_metrics.order_by("-inventory_value", "name")[:5]
        ]
        recent_move_candidates.sort(
            key=lambda row: (row["date"], row["sort_id"]),
            reverse=True,
        )
        recent_moves_payload = [
            {
                "id": move["id"],
                "reference": move["reference"],
                "date": move["date"],
                "product_name": move["product_name"],
                "move_type": move["move_type"],
                "quantity": move["quantity"],
                "source_location": move["source_location"],
                "destination_location": move["destination_location"],
                "done_by_name": move["done_by_name"],
            }
            for move in recent_move_candidates[:8]
        ]
        latest_gins = [
            {
                "id": gin.id,
                "reference": gin.gin_number,
                "status": gin.status,
                "document_date": gin.issue_date,
                "created_at": gin.created_at,
                "context": gin.issued_to or gin.department or gin.project or gin.issue_from,
                "item_count": gin.line_items.count(),
                "quantity_label": "Issued",
                "quantity_total": sum(
                    (Decimal(str(line.issued_qty or 0))
                     for line in gin.line_items.all()),
                    Decimal("0"),
                ),
                "total_value": gin.total_value or 0,
            }
            for gin in gin_queryset.order_by("-created_at", "-id")[:5]
        ]
        latest_grns = [
            {
                "id": grn.id,
                "reference": grn.grn_number,
                "status": grn.status,
                "document_date": grn.receipt_date,
                "created_at": _get_procurement_grn_event_timestamp(grn),
                "context": _get_vendor_display_name(grn.supplier) or grn.invoice_number,
                "item_count": grn.grn_items.count(),
                "quantity_label": "Stocked" if grn.status == "Verified" else "Received",
                "quantity_total": sum(
                    (_get_procurement_grn_line_quantity(line)
                     for line in grn.grn_items.all()),
                    Decimal("0"),
                ),
                "secondary_quantity_label": "Rejected",
                "secondary_quantity_total": sum(
                    (Decimal(str(line.rejected_quantity or 0))
                     for line in grn.grn_items.all()),
                    Decimal("0"),
                ),
                "total_value": grn.total_received_value or 0,
            }
            for grn in procurement_grn_queryset.order_by("-updated_at", "-id")[:5]
        ]
        receipts_last_30_days = sum(
            1
            for line in rolling_verified_grn_lines
            if _get_procurement_grn_line_quantity(line) > 0
        )
        deliveries_last_30_days = rolling_recent_moves.filter(
            move_type="Delivery").count()
        transfers_last_30_days = rolling_recent_moves.filter(
            move_type="Transfer").count()
        adjustments_last_30_days = rolling_recent_moves.filter(
            move_type="Adjustment").count()
        returns_last_30_days = rolling_recent_moves.filter(
            move_type="Return").count()
        scrap_last_30_days = rolling_recent_moves.filter(
            move_type="Scrap").count()

        # ── Operations summary for each module ───────────────────────────────
        # GIN (Goods Issue Note) summary
        gin_all = GIN.objects.all()
        gin_status_counts = _build_status_totals(gin_all)
        gin_period_filter = gin_queryset.filter(
            issue_date__gte=period_start.date(),
            issue_date__lte=period_end_date,
        )
        gin_issued_period = gin_period_filter.filter(status="Issued")
        _gin_value_expr = ExpressionWrapper(
            F("issued_qty") * F("unit_price"),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )
        gin_period_issued_qty = GINLineItem.objects.filter(
            gin__in=gin_issued_period
        ).aggregate(total=Sum("issued_qty", default=0))["total"] or 0
        gin_period_issued_value = GINLineItem.objects.filter(
            gin__in=gin_issued_period
        ).aggregate(total=Sum(_gin_value_expr, default=0))["total"] or 0

        # Stock Transfer summary
        st_all = StockTransfer.objects.all()
        st_status_counts = _build_status_totals(st_all)
        st_period = st_all.filter(
            transfer_date__gte=period_start.date(),
            transfer_date__lte=period_end_date,
        )
        st_in_transit = st_all.filter(status="In Transit").count()
        st_period_value = st_period.aggregate(
            total=Sum("total_value", default=0))["total"] or 0

        # Stock Adjustment summary
        sa_all = StockAdjustment.objects.all()
        sa_status_counts = _build_status_totals(sa_all)
        sa_period = sa_all.filter(
            adjustment_date__gte=period_start.date(),
            adjustment_date__lte=period_end_date,
        )
        sa_period_posted = sa_period.filter(status="Posted")
        sa_period_value = sa_period_posted.aggregate(
            total=Sum("total_value", default=0))["total"] or 0
        from inventory.models.operations import StockAdjustmentLine as _SALine
        sa_period_in_qty = _SALine.objects.filter(
            adjustment__in=sa_period_posted,
            difference__gt=0,
        ).aggregate(total=Sum("difference", default=0))["total"] or 0
        sa_period_out_qty = abs(
            _SALine.objects.filter(
                adjustment__in=sa_period_posted,
                difference__lt=0,
            ).aggregate(total=Sum("difference", default=0))["total"] or 0
        )

        # Scrap Management summary
        scrap_period = ScrapRecord.objects.filter(
            date__gte=period_start.date(),
            date__lte=period_end_date,
        )
        scrap_all = ScrapRecord.objects.all()
        scrap_period_qty = scrap_period.aggregate(
            total=Sum("quantity", default=0))["total"] or 0
        scrap_status_counts = {}
        for row in scrap_all.values("status").annotate(total=Count("id")):
            scrap_status_counts[row["status"]] = row["total"]

        # Return Records (ScrapReturns module) summary
        rr_period = ReturnRecord.objects.filter(
            date__gte=period_start.date(),
            date__lte=period_end_date,
        )
        rr_all = ReturnRecord.objects.all()
        rr_period_qty = rr_period.aggregate(
            total=Sum("quantity", default=0))["total"] or 0
        rr_customer_period = rr_period.filter(return_type="customer").count()
        rr_supplier_period = rr_period.filter(return_type="supplier").count()
        rr_status_counts = {}
        for row in rr_all.values("status").annotate(total=Count("id")):
            rr_status_counts[row["status"]] = row["total"]

        # Return Management (ReturnHeader module) summary
        try:
            from returns.models import ReturnHeader as _ReturnHeader
            rm_all = _ReturnHeader.objects.all()
            rm_period = rm_all.filter(
                return_date__gte=period_start.date(),
                return_date__lte=period_end_date,
            )
            rm_in_transit = rm_all.filter(status="In Transit").count()
            rm_received = rm_all.filter(status="Received").count()
            rm_draft = rm_all.filter(status="Draft").count()
            rm_status_counts = {}
            for row in rm_all.values("status").annotate(total=Count("id")):
                rm_status_counts[row["status"]] = row["total"]
            rm_period_count = rm_period.count()
            rm_period_received = rm_period.filter(status="Received").count()
        except Exception:
            rm_in_transit = rm_received = rm_draft = rm_period_count = rm_period_received = 0
            rm_status_counts = {}

        # ── Live transit count (all in-transit operations) ─────────────────
        live_transit_count = st_in_transit + rm_in_transit

        operations_summary = {
            "gin": {
                "total": gin_all.count(),
                "period_total": gin_period_filter.count(),
                "period_issued": gin_issued_period.count(),
                "period_issued_qty": float(gin_period_issued_qty),
                "period_issued_value": float(gin_period_issued_value),
                "pending": gin_status_counts.get("Draft", 0) + gin_status_counts.get("Pending Approval", 0),
                "issued": gin_status_counts.get("Issued", 0),
                "cancelled": gin_status_counts.get("Cancelled", 0),
                "status_totals": gin_status_counts,
            },
            "stock_transfer": {
                "total": st_all.count(),
                "period_total": st_period.count(),
                "in_transit": st_in_transit,
                "received": st_status_counts.get("Received", 0),
                "draft": st_status_counts.get("Draft", 0),
                "cancelled": st_status_counts.get("Cancelled", 0),
                "period_value": float(st_period_value),
                "status_totals": st_status_counts,
            },
            "stock_adjustment": {
                "total": sa_all.count(),
                "period_total": sa_period.count(),
                "period_posted": sa_period_posted.count(),
                "period_in_qty": float(sa_period_in_qty),
                "period_out_qty": float(sa_period_out_qty),
                "period_value": float(sa_period_value),
                "pending": sa_status_counts.get("Draft", 0) + sa_status_counts.get("Pending Approval", 0),
                "posted": sa_status_counts.get("Posted", 0),
                "status_totals": sa_status_counts,
            },
            "scrap": {
                "total": scrap_all.count(),
                "period_total": scrap_period.count(),
                "period_qty": float(scrap_period_qty),
                "pending": scrap_status_counts.get("pending", 0),
                "approved": scrap_status_counts.get("approved", 0),
                "status_totals": scrap_status_counts,
            },
            "return_records": {
                "total": rr_all.count(),
                "period_total": rr_period.count(),
                "period_qty": float(rr_period_qty),
                "customer_returns": rr_customer_period,
                "supplier_returns": rr_supplier_period,
                "status_totals": rr_status_counts,
            },
            "return_management": {
                "total": rm_all.count() if rm_status_counts or rm_period_count else 0,
                "period_total": rm_period_count,
                "in_transit": rm_in_transit,
                "received": rm_received,
                "draft": rm_draft,
                "period_received": rm_period_received,
                "status_totals": rm_status_counts,
            },
        }

        data = {
            "selected_period": selected_period,
            "period_label": period_label,
            "window_started_at": period_start,
            "window_ended_at": now,
            "custom_date_from": custom_date_from.isoformat() if custom_date_from else None,
            "custom_date_to": custom_date_to.isoformat() if custom_date_to else None,
            "total_skus": products.count(),
            "active_skus": active_products,
            "low_stock_items": products.filter(stock_status="Low Stock").count(),
            "out_of_stock_items": products.filter(stock_status="Out of Stock").count(),
            "overstock_items": products.filter(stock_status="Overstock").count(),
            "expiring_soon_items": LotSerial.objects.filter(
                product__in=products,
                expiry_date__gte=today,
                expiry_date__lte=expiring_limit,
            ).count(),
            "non_moving_items": non_moving_items,
            "live_transit_count": live_transit_count,
            "inventory_overview": {
                "stock_product_count": stocked_products,
                "active_skus": active_products,
                "total_skus": products.count(),
                "total_stock_value": stock_totals["total_stock_value"] or 0,
                "total_on_hand_qty": stock_totals["total_on_hand_qty"] or 0,
                "total_available_qty": stock_totals["total_available_qty"] or 0,
            },
            "source_overview": source_overview,
            "movement_summary": movement_summary,
            "movement_mix": movement_mix,
            "movement_timeline": movement_timeline,
            "top_inbound_products": _build_top_movement_rows(inbound_products),
            "top_outbound_products": _build_top_movement_rows(outbound_products),
            "total_stock_value": stock_totals["total_stock_value"] or 0,
            "total_on_hand_qty": stock_totals["total_on_hand_qty"] or 0,
            "total_available_qty": stock_totals["total_available_qty"] or 0,
            "moves_last_30_days": receipts_last_30_days
            + deliveries_last_30_days
            + transfers_last_30_days
            + adjustments_last_30_days
            + returns_last_30_days
            + scrap_last_30_days,
            "receipts_last_30_days": receipts_last_30_days,
            "deliveries_last_30_days": deliveries_last_30_days,
            "transfers_last_30_days": transfers_last_30_days,
            "adjustments_last_30_days": adjustments_last_30_days,
            "returns_last_30_days": returns_last_30_days,
            "scrap_last_30_days": scrap_last_30_days,
            "avg_days_since_movement": avg_days_since_movement,
            "category_breakdown": category_breakdown,
            "stock_status_breakdown": stock_status_breakdown,
            "top_inventory": top_inventory,
            "recent_moves": recent_moves_payload,
            "latest_gins": latest_gins,
            "latest_grns": latest_grns,
            "operations_summary": operations_summary,
        }
        serializer = InventoryLogAnalyticsSerializer(data)
        return Response(serializer.data)


class InventoryLogHistoryView(APIView):
    permission_classes = [AllowAny]
    pagination_class = Pagination

    def get(self, request):
        reconcile_issued_gin_delivery_history()

        queryset = _filter_inventory_log_history(request)

        ordering = request.query_params.get("ordering", "-created_at")
        allowed_ordering = {
            "date": "date",
            "-date": "-date",
            "created_at": "created_at",
            "-created_at": "-created_at",
            "reference": "reference",
            "-reference": "-reference",
            "product_name": "product__name",
            "-product_name": "-product__name",
            "done_by_name": "done_by__username",
            "-done_by_name": "-done_by__username",
            "quantity": "quantity",
            "-quantity": "-quantity",
            "move_type": "move_type",
            "-move_type": "-move_type",
        }
        queryset = queryset.order_by(
            allowed_ordering.get(ordering, "-created_at"), "-id")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = InventoryLogHistorySerializer(
            page if page is not None else queryset, many=True)

        if page is not None:
            return paginator.get_paginated_response(serializer.data)

        return Response(serializer.data)


class InventoryDashboardOverviewView(APIView):
    """Simple dashboard: office-wise stock summary + recent 5 stock moves."""

    permission_classes = [AllowAny]

    def get(self, request):
        # ── Office-wise stock from LocationStock (single source of truth) ───
        # LocationStock.quantity is the authoritative per-location stock level.
        # Product.on_hand is derived from it via a post_save signal, so both
        # values are always in sync — but LocationStock is used here directly
        # so that totals.total_on_hand always equals SUM(offices[*].on_hand_total).
        office_rows = (
            LocationStock.objects
            .filter(product__is_active=True, quantity__gt=0)
            .values(
                location=F("office_location__name"),
                office_id=F("office_location__id"),
            )
            .annotate(
                product_count=Count("product_id", distinct=True),
                on_hand_total=Sum("quantity"),
                stock_value=Sum(
                    ExpressionWrapper(
                        F("product__cost") * F("quantity"),
                        output_field=DecimalField(max_digits=18, decimal_places=2),
                    )
                ),
            )
            .order_by("-on_hand_total")
        )

        offices = [
            {
                "location": row["location"] or "Unassigned",
                "office_id": row["office_id"],
                "product_count": row["product_count"] or 0,
                "on_hand_total": float(row["on_hand_total"] or 0),
                "stock_value": float(row["stock_value"] or 0),
            }
            for row in office_rows
        ]

        # ── Overall totals from LocationStock ───────────────────────────────
        # total_on_hand = SUM(LocationStock.quantity for active products).
        # This is mathematically identical to SUM(offices[*].on_hand_total),
        # so the KPI card and the per-office table are always consistent.
        from django.db.models import Sum as _Sum, F as _F, DecimalField as _DC, ExpressionWrapper as _EW
        ls_totals = (
            LocationStock.objects
            .filter(product__is_active=True)
            .aggregate(
                total_on_hand=_Sum("quantity", default=0),
                total_value=_Sum(
                    _EW(
                        _F("product__cost") * _F("quantity"),
                        output_field=_DC(max_digits=18, decimal_places=2),
                    ),
                    default=0,
                ),
            )
        )
        total_products = Product.objects.filter(is_active=True).count()

        # ── Recent 5 stock moves ────────────────────────────────────────────
        recent_moves_qs = (
            StockMove.objects.select_related("product", "done_by")
            .order_by("-date", "-id")[:5]
        )
        recent_moves = [
            {
                "id": move.id,
                "date": move.date.isoformat() if move.date else None,
                "reference": move.reference,
                "move_type": move.move_type,
                "product_name": move.product.name if move.product else None,
                "product_code": move.product.code if move.product else None,
                "quantity": float(move.quantity or 0),
                "uom": move.uom,
                "source_location": move.source_location,
                "destination_location": move.destination_location,
                "done_by": move.done_by.username if move.done_by else None,
            }
            for move in recent_moves_qs
        ]

        return Response(
            {
                "totals": {
                    "total_products": total_products,
                    "total_on_hand": float(ls_totals["total_on_hand"] or 0),
                    "total_value": float(ls_totals["total_value"] or 0),
                },
                "offices": offices,
                "recent_moves": recent_moves,
            }
        )


class InventoryOfficeItemCountView(APIView):
    """
    Returns item (product) counts grouped by office/warehouse (OfficeManagement).

    Each entry corresponds to an OfficeManagement record that has at least one
    active product directly assigned to it via the office_location FK.

    Response format:
    [
        {
            "office_id": 1,
            "office_name": "Dhaka Office",
            "office_type": "office",
            "item_count": 12,
            "on_hand_total": 340.0,
            "stock_value": 158000.0
        },
        ...
    ]
    """

    permission_classes = [AllowAny]

    def get(self, request):
        from django.db.models import Count, Sum, F, DecimalField, ExpressionWrapper

        # Use LocationStock as the source of truth for per-location quantities.
        # This correctly reflects stock that arrived via internal transfers,
        # not just the product's home office_location FK.
        rows = (
            LocationStock.objects.filter(quantity__gt=0)
            .values(
                office_id=F("office_location__id"),
                office_name=F("office_location__name"),
                office_type=F("office_location__type"),
            )
            .annotate(
                item_count=Count("product_id", distinct=True),
                on_hand_total=Sum("quantity"),
                stock_value=Sum(
                    ExpressionWrapper(
                        F("product__cost") * F("quantity"),
                        output_field=DecimalField(max_digits=18, decimal_places=2),
                    )
                ),
            )
            .order_by("office_name")
        )

        data = [
            {
                "office_id": row["office_id"],
                "office_name": row["office_name"] or "Unassigned",
                "office_type": row["office_type"] or "",
                "item_count": row["item_count"] or 0,
                "on_hand_total": float(row["on_hand_total"] or 0),
                "stock_value": float(row["stock_value"] or 0),
            }
            for row in rows
            if row["office_id"] is not None
        ]

        return Response(data)


class OfficeStockDetailView(APIView):
    """
    Returns all LocationStock rows for a specific office/warehouse location.
    Uses the LocationStock ledger (source of truth for per-location quantity)
    instead of Product.office_location, so items received via internal
    transfers show up correctly.

    GET /api/inventory-dashboard/office-stock-detail/?office_id=<id>

    Response:
    [
        {
            "product_id": 1,
            "product_name": "Laptop",
            "sku": "LAP-001",
            "quantity": 5.0,
            "unit": "pcs",
            "unit_price": 0.0,
            "stock_status": "In Stock",
            "storage_location_name": "Dhaka Main office"
        },
        ...
    ]
    """

    permission_classes = [AllowAny]

    def get(self, request):
        office_id = request.query_params.get("office_id")
        if not office_id:
            return Response({"error": "office_id is required"}, status=400)

        rows = (
            LocationStock.objects
            .filter(office_location_id=office_id, quantity__gt=0)
            .select_related(
                "product",
                "product__uom",
                "office_location",
            )
            .order_by("product__name")
        )

        data = [
            {
                "product_id": ls.product_id,
                "product_name": ls.product.name,
                "sku": ls.product.code or "",
                "quantity": float(ls.quantity),
                "unit": ls.product.uom.name if ls.product.uom_id else "",
                "unit_price": float(ls.product.cost or 0),
                "stock_status": ls.product.stock_status,
                "storage_location_name": ls.office_location.name,
            }
            for ls in rows
        ]

        return Response(data)
