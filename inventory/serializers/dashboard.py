from django.utils import timezone
from rest_framework import serializers

from inventory.models import Product, StockMove
from inventory.serializers.stock_move_helpers import (
    build_stock_move_document_cache,
    get_stock_move_direction,
    get_stock_move_history_status,
    resolve_stock_move_document,
)


class ItemSummarySerializer(serializers.Serializer):
    total_items = serializers.IntegerField()
    total_active_items = serializers.IntegerField()
    total_low_stock_items = serializers.IntegerField()
    total_categories = serializers.IntegerField()


class DashboardKPISerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    active_products = serializers.IntegerField()
    total_warehouses = serializers.IntegerField()
    total_stock_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    low_stock_items = serializers.IntegerField()
    out_of_stock_items = serializers.IntegerField()
    pending_grns = serializers.IntegerField()
    pending_gins = serializers.IntegerField()
    transfers_in_transit = serializers.IntegerField()
    pending_quality_checks = serializers.IntegerField()
    total_stock_moves_today = serializers.IntegerField()
    total_categories = serializers.IntegerField()
    pending_adjustments = serializers.IntegerField()
    quality_alerts = serializers.IntegerField()
    expiring_soon = serializers.IntegerField()


class InventoryDashboardOverviewSerializer(serializers.Serializer):
    generated_at = serializers.DateTimeField()
    window_started_at = serializers.DateTimeField()
    window_ended_at = serializers.DateTimeField()
    selected_scope = serializers.DictField(read_only=True)
    summary = serializers.DictField(read_only=True)
    totals = serializers.DictField(read_only=True)
    offices = serializers.ListField(child=serializers.DictField(), read_only=True)
    main_office_overview = serializers.DictField(read_only=True, allow_null=True)
    warehouse_options = serializers.ListField(child=serializers.DictField(), read_only=True)
    stock_status_breakdown = serializers.ListField(child=serializers.DictField(), read_only=True)
    movement_mix = serializers.ListField(child=serializers.DictField(), read_only=True)
    movement_timeline = serializers.ListField(child=serializers.DictField(), read_only=True)
    top_products = serializers.ListField(child=serializers.DictField(), read_only=True)
    recent_moves = serializers.ListField(child=serializers.DictField(), read_only=True)
    operational_overview = serializers.DictField(read_only=True)


class InventoryLogListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    subcategory_name = serializers.CharField(source="subcategory.name", read_only=True)
    uom_name = serializers.CharField(source="uom.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    inventory_value = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    movement_count_30d = serializers.IntegerField(read_only=True)
    last_movement_date = serializers.DateTimeField(read_only=True, allow_null=True)
    days_since_movement = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "code",
            "name",
            "product_type",
            "category",
            "category_name",
            "subcategory",
            "subcategory_name",
            "uom",
            "uom_name",
            "supplier",
            "supplier_name",
            "location",
            "on_hand",
            "reserved",
            "available",
            "reorder_level",
            "max_stock",
            "cost",
            "inventory_value",
            "stock_status",
            "status",
            "is_active",
            "tracking",
            "expiry_tracking",
            "last_movement_date",
            "movement_count_30d",
            "days_since_movement",
            "created_at",
            "updated_at",
        ]

    def get_days_since_movement(self, obj):
        last_movement_date = getattr(obj, "last_movement_date", None)

        if not last_movement_date:
            return None

        return max((timezone.now() - last_movement_date).days, 0)


class InventoryLogAnalyticsSerializer(serializers.Serializer):
    selected_period = serializers.CharField()
    period_label = serializers.CharField()
    window_started_at = serializers.DateTimeField()
    window_ended_at = serializers.DateTimeField()
    custom_date_from = serializers.CharField(allow_null=True, required=False)
    custom_date_to = serializers.CharField(allow_null=True, required=False)
    total_skus = serializers.IntegerField()
    active_skus = serializers.IntegerField()
    low_stock_items = serializers.IntegerField()
    out_of_stock_items = serializers.IntegerField()
    overstock_items = serializers.IntegerField()
    expiring_soon_items = serializers.IntegerField()
    non_moving_items = serializers.IntegerField()
    live_transit_count = serializers.IntegerField(default=0)
    total_stock_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_on_hand_qty = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_available_qty = serializers.DecimalField(max_digits=18, decimal_places=2)
    moves_last_30_days = serializers.IntegerField()
    receipts_last_30_days = serializers.IntegerField()
    deliveries_last_30_days = serializers.IntegerField()
    transfers_last_30_days = serializers.IntegerField()
    adjustments_last_30_days = serializers.IntegerField()
    returns_last_30_days = serializers.IntegerField()
    scrap_last_30_days = serializers.IntegerField()
    avg_days_since_movement = serializers.FloatField()
    inventory_overview = serializers.DictField(read_only=True)
    source_overview = serializers.DictField(read_only=True)
    movement_summary = serializers.DictField(read_only=True)
    movement_mix = serializers.ListField(child=serializers.DictField(), read_only=True)
    movement_timeline = serializers.ListField(child=serializers.DictField(), read_only=True)
    top_inbound_products = serializers.ListField(child=serializers.DictField(), read_only=True)
    top_outbound_products = serializers.ListField(child=serializers.DictField(), read_only=True)
    category_breakdown = serializers.ListField(child=serializers.DictField(), read_only=True)
    stock_status_breakdown = serializers.ListField(child=serializers.DictField(), read_only=True)
    top_inventory = serializers.ListField(child=serializers.DictField(), read_only=True)
    recent_moves = serializers.ListField(child=serializers.DictField(), read_only=True)
    latest_gins = serializers.ListField(child=serializers.DictField(), read_only=True)
    latest_grns = serializers.ListField(child=serializers.DictField(), read_only=True)
    operations_summary = serializers.DictField(read_only=True)


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


class InventoryLogHistorySerializer(StockMoveDocumentMixin, serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    done_by_name = serializers.CharField(source="done_by.username", read_only=True)
    done_by_email = serializers.CharField(source="done_by.email", read_only=True)
    direction = serializers.SerializerMethodField()
    history_status = serializers.SerializerMethodField()
    document_type = serializers.SerializerMethodField()
    document_id = serializers.SerializerMethodField()

    class Meta:
        model = StockMove
        fields = [
            "id",
            "date",
            "reference",
            "product",
            "product_name",
            "product_code",
            "source_location",
            "destination_location",
            "quantity",
            "uom",
            "move_type",
            "direction",
            "history_status",
            "done_by",
            "done_by_name",
            "done_by_email",
            "from_status",
            "to_status",
            "document_type",
            "document_id",
            "created_at",
        ]

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
