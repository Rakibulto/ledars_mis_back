from decimal import Decimal

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from paginations import Pagination
from inventory.views import CreatedByMixin
from inventory.models import Item, StockMove, Product
from inventory.models.product import LocationStock
from ..models.grn_models import GoodsReceiptNote, GRNItem, GRNVerification
from ..models.office_models import OfficeManagement
from ..serializers.grn_serializers import (
    GoodsReceiptNoteSerializer,
    GRNCreateSerializer,
    GRNItemSerializer,
    GRNVerificationSerializer,
)


class GoodsReceiptNoteViewSet(CreatedByMixin, viewsets.ModelViewSet):
    queryset = (
        GoodsReceiptNote.objects.select_related(
            "work_order",
            "purchase_order",
            "direct_purchase",
            "supplier",
            "received_by",
            "created_by",
            "receive_location",
        )
        .prefetch_related("grn_items__item")
        .all()
    )
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        "grn_number",
        "supplier__name",
        "direct_vendor_name",
        "invoice_number",
        "status",
    ]
    ordering_fields = ["created_at", "receipt_date", "total_received_value"]
    ordering = ["-created_at"]
    filterset_fields = {
        "id": ["in", "exact"],
        "status": ["iexact"],
        "supplier": ["exact"],
        "work_order": ["exact"],
    }

    @staticmethod
    def _extract_item_name(grn_item):
        if grn_item.item and grn_item.item.name:
            return grn_item.item.name.strip()

        remarks = (grn_item.remarks or "").strip()
        if remarks.startswith("Item: "):
            return remarks.split(" | ")[0].replace("Item: ", "").strip()

        return ""

    @staticmethod
    def _resolve_inventory_item(grn_item):
        """Return the matching inventory Item for a GRNItem.
        Priority: FK → match by name → match by Item Code.
        """
        if grn_item.item:
            return grn_item.item

        # Build search candidates from remarks
        remarks = (grn_item.remarks or "").strip()
        item_name = ""
        item_code = ""
        if remarks.startswith("Item: "):
            parts = remarks.split(" | ")
            item_name = parts[0].replace("Item: ", "").strip()
            for part in parts[1:]:
                if part.startswith("Code: "):
                    item_code = part.replace("Code: ", "").strip()

        qs = Item.objects.select_related("uom")
        if item_name:
            match = qs.filter(name__iexact=item_name).order_by("id").first()
            if match:
                return match
        if item_code:
            match = qs.filter(code__iexact=item_code).order_by("id").first()
            if match:
                return match
        return None

    @staticmethod
    def _movement_timestamp(document_date):
        timestamp = timezone.localtime()

        if not document_date:
            return timestamp

        return timestamp.replace(
            year=document_date.year,
            month=document_date.month,
            day=document_date.day,
        )

    @staticmethod
    def _get_supplier_display_name(supplier):
        if not supplier:
            return None

        return (
            getattr(supplier, "name", None)
            or getattr(supplier, "legal_name", None)
            or getattr(supplier, "company_name_bn", None)
            or getattr(supplier, "code", None)
        )

    @staticmethod
    def _resolve_stock_move_actor(grn):
        received_by = getattr(grn, "received_by", None)
        received_by_user = getattr(received_by, "user", None)

        if received_by_user:
            return received_by_user

        return getattr(grn, "created_by", None)

    def _build_receipt_stock_move(
        self, grn, inventory_item, quantity, *, destination_office=None
    ):
        if not inventory_item or quantity <= 0:
            return None

        supplier_name = (
            self._get_supplier_display_name(grn.supplier) or "Vendor receipt"
        )
        if destination_office:
            destination_location = destination_office.name
        else:
            destination_location = (
                getattr(inventory_item, "location", None) or ""
            ).strip() or "Main inventory"

        return StockMove(
            date=self._movement_timestamp(grn.receipt_date),
            reference=grn.grn_number,
            product=inventory_item,
            source_location=supplier_name,
            destination_location=destination_location,
            quantity=quantity,
            uom=getattr(inventory_item, "unit", None) or None,
            move_type="Receipt",
            done_by=self._resolve_stock_move_actor(grn),
        )

    @transaction.atomic
    def _sync_verified_grn_to_inventory(self, grn):
        """
        When a GRN reaches Verified status:
          1. Use accepted_quantity (not received_quantity) — only accepted goods
             enter stock.
          2. Match inventory Item via FK → Item Name → Item Code.
          3. Use grn.receive_location as the destination office.
          4. Create or increment LocationStock (signal keeps Product.on_hand in sync).
             If no location, update Product.on_hand directly.
          5. Write a StockMove audit row per item.
        """
        receive_location = grn.receive_location  # OfficeManagement instance or None

        grn_items = grn.grn_items.select_related("item", "item__uom").all()
        stock_moves = []

        for grn_item in grn_items:
            # Use accepted_quantity — only goods accepted after inspection go to stock
            quantity = int(grn_item.accepted_quantity or 0)
            if quantity <= 0:
                continue

            # Resolve inventory item: FK first, then by name/code
            inventory_item = self._resolve_inventory_item(grn_item)
            if not inventory_item:
                continue

            # Persist the resolved FK so future lookups are instant
            if not grn_item.item:
                grn_item.item = inventory_item
                grn_item.save(update_fields=["item"])

            # ── Update LocationStock or Product.on_hand directly ────────
            if receive_location:
                ls, created = LocationStock.objects.get_or_create(
                    product=inventory_item,
                    office_location=receive_location,
                    defaults={"quantity": quantity},
                )
                if not created:
                    # select_for_update is already covered by outer @transaction.atomic
                    ls.quantity = (ls.quantity or 0) + quantity
                    ls.save(update_fields=["quantity", "updated_at"])
                # The post_save signal on LocationStock fires in both branches and
                # calls _sync_product_on_hand → keeps Product.on_hand accurate.
            else:
                # No location set — increment Product.on_hand directly and
                # recalculate stock_status without breaking LocationStock integrity.
                product = inventory_item
                new_on_hand = (product.on_hand or Decimal("0")) + Decimal(str(quantity))
                if new_on_hand <= 0:
                    new_status = "Out of Stock"
                elif product.reorder_level and new_on_hand <= product.reorder_level:
                    new_status = "Low Stock"
                elif product.max_stock and new_on_hand > product.max_stock:
                    new_status = "Overstock"
                else:
                    new_status = "In Stock"
                Product.objects.filter(pk=product.pk).update(
                    on_hand=F("on_hand") + Decimal(str(quantity)),
                    available=F("available") + Decimal(str(quantity)),
                    stock_status=new_status,
                )

            # ── Update item unit_price from GRN line unit_price ───────────
            # Product.save() automatically preserves the previous cost in
            # old_unit_price (see Product.save() in inventory/models/product.py).
            grn_line_unit_price = Decimal(str(grn_item.unit_price or 0))
            if grn_line_unit_price > 0 and inventory_item.cost != grn_line_unit_price:
                inventory_item.cost = grn_line_unit_price
                inventory_item.save(update_fields=["cost", "old_unit_price"])

            # ── Audit: StockMove receipt row ──────────────────────────────
            dest_name = receive_location.name if receive_location else "Main inventory"
            supplier_name = (
                self._get_supplier_display_name(grn.supplier) or "Vendor receipt"
            )
            stock_moves.append(
                StockMove(
                    date=self._movement_timestamp(grn.receipt_date),
                    reference=grn.grn_number,
                    product=inventory_item,
                    source_location=supplier_name,
                    destination_location=dest_name,
                    quantity=quantity,
                    uom=getattr(inventory_item, "unit", None) or None,
                    move_type="Receipt",
                    done_by=self._resolve_stock_move_actor(grn),
                )
            )

        if stock_moves:
            StockMove.objects.bulk_create(stock_moves)

    def get_serializer_class(self):
        if self.action in ["create"]:
            return GRNCreateSerializer
        return GoodsReceiptNoteSerializer

    @transaction.atomic
    def perform_update(self, serializer):
        previous_status = serializer.instance.status
        grn = serializer.save()

        if previous_status != "Verified" and grn.status == "Verified":
            self._sync_verified_grn_to_inventory(grn)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = GoodsReceiptNote.objects.all()
        from django.db.models import Sum

        data = {
            "total": qs.count(),
            "pending_verification": qs.filter(status="Pending Verification").count(),
            "verified": qs.filter(status="Verified").count(),
            "rejected": qs.filter(status="Rejected").count(),
            "total_value": qs.aggregate(total=Sum("total_received_value"))["total"]
            or 0,
        }
        return Response(data)


class GRNItemViewSet(viewsets.ModelViewSet):
    queryset = GRNItem.objects.select_related("grn", "item").all()
    serializer_class = GRNItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["grn", "condition"]


class GRNVerificationViewSet(viewsets.ModelViewSet):
    queryset = GRNVerification.objects.select_related(
        "grn", "grn_item", "verified_by"
    ).all()
    serializer_class = GRNVerificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["grn", "status"]
