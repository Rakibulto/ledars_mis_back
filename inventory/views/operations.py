from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status as http_status
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import F, Q
from paginations import Pagination
from inventory.models import (
    GRN,
    GIN,
    StockTransfer,
    StockAdjustment,
    CycleCount,
    LotSerial,
    StockMove,
)
from inventory.serializers import (
    GRNReadSerializer,
    GRNWriteSerializer,
    GINReadSerializer,
    GINWriteSerializer,
    StockTransferReadSerializer,
    StockTransferWriteSerializer,
    StockAdjustmentReadSerializer,
    StockAdjustmentWriteSerializer,
    CycleCountReadSerializer,
    CycleCountWriteSerializer,
    LotSerialSerializer,
    StockMoveSerializer,
)


class GRNViewSet(ModelViewSet):
    queryset = (
        GRN.objects.select_related("supplier", "warehouse", "received_by")
        .prefetch_related("line_items", "line_items__product")
        .all()
    )
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "grn_number",
        "invoice_number",
        "challan_number",
        "vehicle_number",
        "supplier__name",
        "supplier__legal_name",
        "supplier__company_name_bn",
        "warehouse__name",
        "po_number__po_number",
    ]
    ordering_fields = ["grn_number", "receive_date", "created_at", "total_value"]
    ordering = ["-receive_date", "-created_at"]
    filterset_fields = ["status", "supplier", "warehouse", "received_by"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return GRNReadSerializer
        return GRNWriteSerializer

    def filter_queryset(self, queryset):
        vendor_id = self.request.query_params.get("vendor")

        if vendor_id:
            queryset = queryset.filter(supplier_id=vendor_id)

        return super().filter_queryset(queryset)

    def perform_destroy(self, instance):
        with transaction.atomic():
            StockMove.objects.filter(
                reference=instance.grn_number, move_type="Receipt"
            ).delete()
            instance.delete()


class BackorderViewSet(GRNViewSet):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(line_items__ordered_qty__gt=F("line_items__received_qty"))
            .distinct()
        )


class GINViewSet(ModelViewSet):
    queryset = (
        GIN.objects.select_related(
            "warehouse", "office_location", "requested_by", "approved_by", "issued_by"
        )
        .prefetch_related("line_items", "line_items__product")
        .all()
    )
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "gin_number",
        "issued_to",
        "issue_from",
        "department",
        "project",
        "purpose",
        "warehouse__name",
        "office_location__name",
    ]
    ordering_fields = ["gin_number", "issue_date", "created_at", "total_value"]
    ordering = ["-issue_date", "-created_at"]
    filterset_fields = [
        "status",
        "warehouse",
        "office_location",
        "department",
        "project",
        "requested_by",
        "approved_by",
    ]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return GINReadSerializer
        return GINWriteSerializer

    def perform_destroy(self, instance):
        with transaction.atomic():
            StockMove.objects.filter(
                reference=instance.gin_number, move_type="Delivery"
            ).delete()
            instance.delete()

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """
        POST /api/gin/{id}/approve/

        Workflow approval for Goods Issue Notes. Body may include line_items.
        """
        from decimal import Decimal
        from django.utils import timezone as tz

        from rest_framework.exceptions import ValidationError

        from inventory.models.operations import GINLineItem
        from inventory.serializers.operations import (
            GINLineItemSerializer,
            _apply_gin_stock_reduction,
            _create_gin_status_log,
            _rebuild_gin_totals_and_stock_moves,
            _replace_line_items,
        )
        from inventory.services.gin_workflow import (
            compute_gin_total_value,
            get_level_users,
            get_user_level_entry,
            resolve_matched_level_for_gin,
            user_already_approved,
        )

        gin = self.get_object()
        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response(
                {"detail": "Authentication required."},
                status=http_status.HTTP_401_UNAUTHORIZED,
            )

        if gin.status != "Pending Approval":
            return Response(
                {"detail": f"Cannot approve GIN in '{gin.status}' status."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        workflow, matched_level = resolve_matched_level_for_gin(gin)
        if not workflow:
            return Response(
                {"detail": "No active approval workflow configured for goods issue notes."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if not matched_level:
            total_value = compute_gin_total_value(gin)
            return Response(
                {"detail": f"No workflow level matches GIN value {total_value}."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        level_users = get_level_users(matched_level)
        user_entry = get_user_level_entry(level_users, user)
        if not user_entry:
            return Response(
                {"detail": "You are not an authorized approver for this GIN."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        if user_already_approved(gin, user):
            return Response(
                {"detail": "You have already approved this GIN."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        current_approval_level = gin.approval_level or 0
        min_required = matched_level.minimum_approval_required or 1
        ordered = matched_level.level_maintain_require == "yes"

        if ordered:
            next_order = current_approval_level + 1
            if user_entry.approval_order != next_order:
                return Response(
                    {
                        "detail": (
                            f"Approval order requires user with order {next_order} "
                            "to approve next."
                        )
                    },
                    status=http_status.HTTP_403_FORBIDDEN,
                )
        elif current_approval_level >= min_required:
            return Response(
                {"detail": "All required approvals have already been received."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        line_items_data = request.data.get("line_items")
        if line_items_data is not None:
            line_serializer = GINLineItemSerializer(data=line_items_data, many=True)
            line_serializer.is_valid(raise_exception=True)
            line_items_data = line_serializer.validated_data

        new_approval_level = current_approval_level + 1
        is_final = new_approval_level >= min_required
        from_status = gin.status
        to_status = "Approved" if is_final else "Pending Approval"

        log_entry = {
            "gin_code": gin.gin_number or f"GIN-{gin.pk}",
            "action": "approval",
            "name": user.get_full_name() or user.username or user.email or "Unknown",
            "email": user.email or "",
            "status_from": from_status,
            "status_to": to_status,
            "log_time": tz.localtime().isoformat(),
        }

        current_log = list(gin.approval_log or [])
        current_log.append(log_entry)

        with transaction.atomic():
            update_fields = {
                "approval_level": new_approval_level,
                "approval_log": current_log,
                "status": to_status,
            }
            if is_final:
                update_fields["approved_by"] = user

            GIN.objects.filter(pk=gin.pk).update(**update_fields)
            gin.refresh_from_db()

            lines = _replace_line_items(
                gin,
                line_items_data,
                "line_items",
                GINLineItem,
                "gin",
            )

            try:
                if is_final:
                    _apply_gin_stock_reduction(gin, lines, apply_changes=False)

                _create_gin_status_log(
                    gin=gin,
                    from_status=from_status,
                    to_status=to_status,
                    actor=user,
                )

                _rebuild_gin_totals_and_stock_moves(gin, lines)
            except ValidationError as exc:
                transaction.set_rollback(True)
                return Response(exc.detail, status=http_status.HTTP_400_BAD_REQUEST)

        serializer = GINReadSerializer(gin, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="issue")
    def issue(self, request, pk=None):
        """
        POST /api/gin/{id}/issue/

        Issue an approved GIN. Only level_users from the matched workflow level may issue.
        """
        from django.utils import timezone as tz

        from rest_framework.exceptions import ValidationError

        from inventory.serializers.operations import (
            _apply_gin_stock_reduction,
            _create_gin_status_log,
            _rebuild_gin_totals_and_stock_moves,
        )
        from inventory.services.gin_workflow import (
            get_level_users,
            get_user_level_entry,
            resolve_matched_level_for_gin,
        )

        gin = self.get_object()
        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response(
                {"detail": "Authentication required."},
                status=http_status.HTTP_401_UNAUTHORIZED,
            )

        if gin.status != "Approved":
            return Response(
                {"detail": f"Cannot issue GIN in '{gin.status}' status."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        _, matched_level = resolve_matched_level_for_gin(gin)
        if not matched_level:
            return Response(
                {"detail": "No matching workflow level found for this GIN."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        level_users = get_level_users(matched_level)
        user_entry = get_user_level_entry(level_users, user)
        if not user_entry:
            return Response(
                {"detail": "You are not authorized to issue this GIN."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        transport_person = (request.data.get("transport_person") or "").strip()
        transport_phone = (request.data.get("transport_phone") or "").strip()
        dispatch_date = request.data.get("dispatch_date")

        if not transport_person or not transport_phone or not dispatch_date:
            return Response(
                {
                    "detail": (
                        "transport_person, transport_phone, and dispatch_date "
                        "are required to issue."
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        from_status = gin.status
        transport_keys = [
            "transport_person",
            "transport_phone",
            "transport_address",
            "vehicle_number",
            "dispatch_date",
        ]

        with transaction.atomic():
            update_fields = {"status": "Issued", "issued_by": user}
            for key in transport_keys:
                value = request.data.get(key)
                if value is not None:
                    update_fields[key] = value

            GIN.objects.filter(pk=gin.pk).update(**update_fields)
            gin.refresh_from_db()

            lines = list(gin.line_items.select_related("product").all())
            try:
                status_log = _create_gin_status_log(
                    gin=gin,
                    from_status=from_status,
                    to_status=gin.status,
                    actor=user,
                )
                _apply_gin_stock_reduction(gin, lines)
                _rebuild_gin_totals_and_stock_moves(
                    gin,
                    lines,
                    movement_timestamp=status_log.date if status_log else tz.localtime(),
                )
            except ValidationError as exc:
                transaction.set_rollback(True)
                return Response(exc.detail, status=http_status.HTTP_400_BAD_REQUEST)

        serializer = GINReadSerializer(gin, context={"request": request})
        return Response(serializer.data)


class DropshippingViewSet(GINViewSet):
    pass


class StockTransferViewSet(ModelViewSet):
    queryset = (
        StockTransfer.objects.select_related(
            "from_warehouse", "to_warehouse", "sent_by", "received_by"
        )
        .prefetch_related("lines", "lines__product")
        .all()
    )
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "transfer_number",
        "from_location",
        "to_location",
        "vehicle_number",
        "driver_name",
        "notes",
        "lines__item_code",
        "lines__item_name",
        "lines__product__name",
        "lines__product__code",
        "from_warehouse__name",
        "to_warehouse__name",
        "sent_by__username",
        "received_by__username",
    ]
    ordering_fields = ["transfer_number", "transfer_date", "created_at", "total_value"]
    ordering = ["-transfer_date", "-created_at"]
    filterset_fields = ["status", "from_warehouse", "to_warehouse", "sent_by", "received_by"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return StockTransferReadSerializer
        return StockTransferWriteSerializer

    def get_queryset(self):
        return super().get_queryset().distinct()

    def perform_destroy(self, instance):
        with transaction.atomic():
            StockMove.objects.filter(
                reference=instance.transfer_number, move_type="Transfer"
            ).delete()
            instance.delete()


class CrossDockingViewSet(StockTransferViewSet):
    pass


class BatchTransferViewSet(StockTransferViewSet):
    pass


class StockAdjustmentViewSet(ModelViewSet):
    queryset = (
        StockAdjustment.objects.select_related(
            "warehouse", "adjusted_by", "approved_by"
        )
        .prefetch_related("lines", "lines__product")
        .all()
    )
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "adjustment_number",
        "reason",
        "location",
        "adjustment_type",
        "warehouse__name",
        "adjusted_by__username",
        "approved_by__username",
    ]
    ordering_fields = [
        "adjustment_number",
        "adjustment_date",
        "created_at",
        "total_value",
    ]
    ordering = ["-adjustment_date", "-created_at"]
    filterset_fields = [
        "status",
        "adjustment_type",
        "warehouse",
        "adjusted_by",
        "approved_by",
    ]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return StockAdjustmentReadSerializer
        return StockAdjustmentWriteSerializer

    def perform_destroy(self, instance):
        with transaction.atomic():
            StockMove.objects.filter(
                reference=instance.adjustment_number, move_type="Adjustment"
            ).delete()
            instance.delete()

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """
        POST /api/stock-adjustments/{id}/approve/

        Optional body: { "force_unordered": true } for product-list approvals.
        """
        from django.utils import timezone as tz
        from rest_framework.exceptions import ValidationError

        from inventory.serializers.operations import (
            _apply_stock_adjustment_product_delta,
            _create_adjustment_status_log,
            _rebuild_adjustment_totals_and_stock_moves,
        )
        from inventory.services.adjustment_workflow import (
            get_level_users,
            get_user_level_entry,
            resolve_matched_level_for_adjustment,
            user_already_approved,
        )

        adjustment = self.get_object()
        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response(
                {"detail": "Authentication required."},
                status=http_status.HTTP_401_UNAUTHORIZED,
            )

        if adjustment.status != "Pending Approval":
            return Response(
                {"detail": f"Cannot approve adjustment in '{adjustment.status}' status."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        workflow, matched_level = resolve_matched_level_for_adjustment(adjustment)
        if not workflow:
            return Response(
                {"detail": "No active approval workflow configured for stock adjustments."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if not matched_level:
            from inventory.services.adjustment_workflow import compute_adjustment_total_value

            total_value = compute_adjustment_total_value(adjustment)
            return Response(
                {"detail": f"No workflow level matches adjustment value {total_value}."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        level_users = get_level_users(matched_level)
        user_entry = get_user_level_entry(level_users, user)
        if not user_entry:
            return Response(
                {"detail": "You are not an authorized approver for this adjustment."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        if user_already_approved(adjustment, user):
            return Response(
                {"detail": "You have already approved this adjustment."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        current_approval_level = adjustment.approval_level or 0
        min_required = matched_level.minimum_approval_required or 1
        force_unordered = bool(request.data.get("force_unordered"))
        ordered = matched_level.level_maintain_require == "yes" and not force_unordered

        if ordered:
            next_order = current_approval_level + 1
            if user_entry.approval_order != next_order:
                return Response(
                    {
                        "detail": (
                            f"Approval order requires user with order {next_order} "
                            "to approve next."
                        )
                    },
                    status=http_status.HTTP_403_FORBIDDEN,
                )
        elif current_approval_level >= min_required:
            return Response(
                {"detail": "All required approvals have already been received."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        new_approval_level = current_approval_level + 1
        is_final = new_approval_level >= min_required
        from_status = adjustment.status
        to_status = "Approved" if is_final else "Pending Approval"

        log_entry = {
            "adjustment_code": adjustment.adjustment_number or f"ADJ-{adjustment.pk}",
            "action": "approval",
            "name": user.get_full_name() or user.username or user.email or "Unknown",
            "email": user.email or "",
            "status_from": from_status,
            "status_to": to_status,
            "log_time": tz.localtime().isoformat(),
        }

        current_log = list(adjustment.approval_log or [])
        current_log.append(log_entry)

        with transaction.atomic():
            update_fields = {
                "approval_level": new_approval_level,
                "approval_log": current_log,
                "status": to_status,
            }
            if is_final:
                update_fields["approved_by"] = user

            StockAdjustment.objects.filter(pk=adjustment.pk).update(**update_fields)
            adjustment.refresh_from_db()

            lines = list(adjustment.lines.select_related("product").all())

            try:
                if is_final:
                    _apply_stock_adjustment_product_delta(lines)

                _create_adjustment_status_log(
                    adjustment=adjustment,
                    from_status=from_status,
                    to_status=to_status,
                    actor=user,
                )

                _rebuild_adjustment_totals_and_stock_moves(adjustment, lines)
            except ValidationError as exc:
                transaction.set_rollback(True)
                return Response(exc.detail, status=http_status.HTTP_400_BAD_REQUEST)

        serializer = StockAdjustmentReadSerializer(adjustment, context={"request": request})
        return Response(serializer.data)


class CycleCountViewSet(ModelViewSet):
    queryset = (
        CycleCount.objects.select_related("warehouse", "owner", "reviewer")
        .prefetch_related("lines", "lines__product")
        .all()
    )
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "count_number",
        "count_type",
        "scope",
        "notes",
        "warehouse__name",
        "owner__username",
        "reviewer__username",
    ]
    ordering_fields = ["count_number", "scheduled_date", "created_at", "updated_at"]
    ordering = ["-scheduled_date", "-created_at"]
    filterset_fields = ["status", "warehouse", "count_type", "owner", "reviewer"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return CycleCountReadSerializer
        return CycleCountWriteSerializer


class LotSerialViewSet(ModelViewSet):
    queryset = LotSerial.objects.select_related("product", "warehouse").all()
    serializer_class = LotSerialSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["number", "product__name", "product__code"]
    filterset_fields = ["lot_type", "status", "product", "warehouse"]


class StockMoveViewSet(ModelViewSet):
    queryset = StockMove.objects.select_related("product", "done_by").all()
    serializer_class = StockMoveSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "reference",
        "product__name",
        "product__code",
        "source_location",
        "destination_location",
        "done_by__username",
        "done_by__email",
        "from_status",
        "to_status",
        "uom",
    ]
    ordering_fields = [
        "date",
        "created_at",
        "reference",
        "quantity",
        "move_type",
        "product__name",
    ]
    ordering = ["-date"]
    filterset_fields = ["move_type", "product", "done_by"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        direction = (params.get("direction") or "").strip().lower()

        if date_from:
            queryset = queryset.filter(date__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(date__date__lte=date_to)

        if direction == "in":
            queryset = queryset.filter(
                Q(move_type__in=["Receipt", "Return"])
                | Q(move_type="Adjustment", source_location__iexact="Adjustment Increase")
            )
        elif direction == "out":
            queryset = queryset.filter(
                Q(move_type__in=["Delivery", "Scrap"])
                | Q(
                    move_type="Adjustment",
                    destination_location__iexact="Adjustment Decrease",
                )
            )
        elif direction == "internal":
            queryset = queryset.filter(move_type="Transfer")

        return queryset


# ─────────────────────────────────────────────────────────────
#  INTERNAL TRANSFER  (office/warehouse stock movement)
# ─────────────────────────────────────────────────────────────
from decimal import Decimal  # noqa: E402
from django.utils import timezone  # noqa: E402
from rest_framework.decorators import action  # noqa: E402
from rest_framework.response import Response  # noqa: E402
from rest_framework import status as http_status  # noqa: E402
from rest_framework.views import APIView  # noqa: E402
from inventory.models import InternalTransfer, InternalTransferLine  # noqa: E402
from inventory.models.operations import StockAdjustment, StockAdjustmentLine  # noqa: E402
from inventory.serializers.operations import (  # noqa: E402
    InternalTransferReadSerializer,
    InternalTransferWriteSerializer,
    _rebuild_adjustment_totals_and_stock_moves,
)
from inventory.services.transfer import (  # noqa: E402
    deduct_location_stock,
    restore_location_stock,
    add_location_stock,
)


class InternalTransferViewSet(ModelViewSet):
    queryset = (
        InternalTransfer.objects.select_related(
            "from_office", "to_office", "created_by"
        )
        .prefetch_related("lines", "lines__product")
        .all()
    )
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "transfer_number",
        "notes",
        "from_office__name",
        "to_office__name",
        "lines__product_name",
        "lines__product_code",
        "created_by__username",
    ]
    ordering_fields = ["transfer_number", "transfer_date", "created_at", "status"]
    ordering = ["-transfer_date", "-created_at"]
    filterset_fields = ["status", "from_office", "to_office"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return InternalTransferReadSerializer
        return InternalTransferWriteSerializer

    # ── Approval Workflow action ──────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """
        POST /api/internal-transfers/{id}/approve/

        Body (optional - only first approver needs transport):
        {
            "transport_person": "...",
            "transport_phone": "...",
            "transport_address": "...",
            "vehicle_number": "...",
            "dispatch_date": "YYYY-MM-DD"
        }

        Workflow logic:
        1. Find matching workflow level by transfer total_value.
        2. Check if user is an allowed approver for that level.
        3. If level_maintain_require="yes", enforce approval_order sequence.
        4. Increment approval_level.
        5. Append to status_log.
        6. When minimum_approval_required is reached, dispatch if transport details exist,
           otherwise wait for final approver's approve call with transport details.
        """
        from decimal import Decimal
        from django.utils import timezone as tz
        from approval_workflow.models import ApprovalWorkflow, ApprovalLevel, ApprovalLevelUser

        transfer = self.get_object()
        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response(
                {"detail": "Authentication required."},
                status=http_status.HTTP_401_UNAUTHORIZED,
            )

        if transfer.status not in ("Draft", "Pending Transit Approval"):
            return Response(
                {"detail": f"Cannot approve transfer in '{transfer.status}' status."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # 1. Compute total_value from line items
        lines_qs = transfer.lines.select_related("product").all()
        total_value = sum(
            Decimal(str(line.quantity or 0)) * Decimal(str(line.unit_price or 0))
            for line in lines_qs
        )

        # 2. Find active workflow for internal_transfers
        workflow = ApprovalWorkflow.objects.filter(
            module_type_name="inventory",
            menu_name="internal_transfers",
            is_active=True,
        ).prefetch_related("levels__level_users__user").first()

        if not workflow:
            return Response(
                {"detail": "No active approval workflow configured for internal transfers."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # 3. Find matching level by total_value range
        matched_level = None
        for lvl in workflow.levels.all():
            from_amt = Decimal(str(lvl.from_amount or 0))
            to_amt = lvl.to_amount
            if to_amt is None:
                if total_value >= from_amt:
                    matched_level = lvl
                    break
            else:
                to_amt = Decimal(str(to_amt))
                if from_amt <= total_value <= to_amt:
                    matched_level = lvl
                    break

        if not matched_level:
            return Response(
                {"detail": f"No workflow level matches transfer value {total_value}."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # 4. Check if user is an allowed approver
        level_users = list(matched_level.level_users.select_related("user").all())
        user_entry = next(
            (lu for lu in level_users if lu.user_id == user.id),
            None
        )

        if not user_entry:
            return Response(
                {"detail": "You are not an authorized approver for this transfer."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        # 5. Check approval sequence if level_maintain_require == "yes"
        current_approval_level = transfer.approval_level or 0
        min_required = matched_level.minimum_approval_required or 1
        ordered = matched_level.level_maintain_require == "yes"

        if ordered:
            next_order = current_approval_level + 1
            if user_entry.approval_order != next_order:
                return Response(
                    {"detail": f"Approval order requires user with order {next_order} to approve next."},
                    status=http_status.HTTP_403_FORBIDDEN,
                )
        else:
            # In "no" mode, any user can approve but only up to min_required
            if current_approval_level >= min_required:
                return Response(
                    {"detail": "All required approvals have already been received."},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

        # 6. Determine if this is the final approval needed
        new_approval_level = current_approval_level + 1
        is_final = new_approval_level >= min_required

        # 7. Create status_log entry
        from_status = transfer.status
        to_status = "In Transit" if is_final else "Pending Transit Approval"

        log_entry = {
            "internal_transfer_code": transfer.transfer_number or f"IT-{transfer.pk}",
            "name": user.username or user.email or "Unknown",
            "email": user.email or "",
            "status_from": from_status,
            "status_to": to_status,
            "log_time": tz.localtime().isoformat(),
        }

        current_log = list(transfer.status_log or [])
        current_log.append(log_entry)

        # 8. Update line item quantities if provided in request
        lines_data = request.data.get("lines")
        if lines_data and isinstance(lines_data, list):
            for line_data in lines_data:
                line_id = line_data.get("id")
                if not line_id:
                    continue
                new_qty = line_data.get("quantity")
                if new_qty is not None:
                    try:
                        InternalTransferLine.objects.filter(
                            pk=line_id, transfer=transfer
                        ).update(quantity=Decimal(str(new_qty)))
                    except Exception:
                        pass
            # Refresh lines_qs after update for accurate total_value and deduction
            transfer.refresh_from_db()
            lines_qs = transfer.lines.select_related("product").all()
            total_value = sum(
                Decimal(str(line.quantity or 0)) * Decimal(str(line.unit_price or 0))
                for line in lines_qs
            )
            import time
            time.sleep(0.05)
            transfer.refresh_from_db()

        # 9. Prepare update fields
        update_fields = {
            "approval_level": new_approval_level,
            "status_log": current_log,
        }

        # Always save transport details if provided (for any approval step)
        transport_keys = [
            "transport_person", "transport_phone", "transport_address",
            "vehicle_number", "dispatch_date",
        ]
        has_new_transport = bool(request.data.get("transport_person"))
        
        if has_new_transport:
            for key in transport_keys:
                value = request.data.get(key)
                if value is not None:
                    update_fields[key] = value

        if is_final:
            # Final approval - dispatch the transfer
            transport_person = request.data.get("transport_person")
            if not transport_person:
                # If transport details weren't provided in this request,
                # check if they were previously saved
                if not transfer.transport_person:
                    return Response(
                        {"detail": "Transportation details are required for final dispatch. Provide transport_person, transport_phone, transport_address, dispatch_date."},
                        status=http_status.HTTP_400_BAD_REQUEST,
                    )
                # Already have transport details - just dispatch
                update_fields["status"] = "In Transit"
            else:
                update_fields["status"] = "In Transit"
        else:
            update_fields["status"] = "Pending Transit Approval"

        with transaction.atomic():
            InternalTransfer.objects.filter(pk=transfer.pk).update(**update_fields)
            transfer.refresh_from_db()

            # Apply stock transition logic
            self._apply_status_transition(
                transfer, from_status, transfer.status,
                user=user,
            )

        serializer = InternalTransferReadSerializer(transfer, context={"request": request})
        return Response(serializer.data)

    # ── business logic ───────────────────────────────────────────────────────

    @staticmethod
    def _deduct_source_stock(transfer):
        """
        Deduct quantities from source LocationStock rows.
        Idempotent — guarded by the stock_deducted flag.
        Never touches Product records directly.
        """
        if transfer.stock_deducted:
            return
        if not transfer.from_office_id:
            return

        for line in transfer.lines.select_related("product").all():
            if not line.product or not line.quantity:
                continue
            deduct_location_stock(
                location=transfer.from_office,
                product=line.product,
                quantity=line.quantity,
            )

        InternalTransfer.objects.filter(pk=transfer.pk).update(stock_deducted=True)
        transfer.stock_deducted = True

    @staticmethod
    def _restore_source_stock(transfer):
        """
        Return previously deducted quantities to source LocationStock rows.
        Used when cancelling an In Transit transfer.
        Idempotent — guarded by the stock_deducted flag.
        Never touches Product records directly.
        """
        if not transfer.stock_deducted:
            return
        if not transfer.from_office_id:
            return

        for line in transfer.lines.select_related("product").all():
            if not line.product or not line.quantity:
                continue
            restore_location_stock(
                location=transfer.from_office,
                product=line.product,
                quantity=line.quantity,
            )

        InternalTransfer.objects.filter(pk=transfer.pk).update(stock_deducted=False)
        transfer.stock_deducted = False

    @staticmethod
    def _receive_stock(transfer):
        """
        Add quantities to destination LocationStock rows.
        Idempotent — guarded by the stock_received flag.
        Never creates new Product records; uses the same Product FK
        from each transfer line and simply adds to the destination location.
        """
        if transfer.stock_received or not transfer.to_office_id:
            return

        for line in transfer.lines.select_related("product").all():
            if not line.product or not line.quantity:
                continue
            add_location_stock(
                location=transfer.to_office,
                product=line.product,
                quantity=line.quantity,
            )

        InternalTransfer.objects.filter(pk=transfer.pk).update(stock_received=True)
        transfer.stock_received = True

    def _apply_status_transition(self, transfer, old_status, new_status, user=None):
        if old_status == new_status:
            return
        if new_status == "In Transit" and old_status in ("Draft", "Pending Transit Approval"):
            self._deduct_source_stock(transfer)
            self._create_transfer_moves(transfer, old_status, new_status, user)
        elif new_status == "Received" and old_status == "In Transit":
            self._receive_stock(transfer)
            self._create_transfer_moves(transfer, old_status, new_status, user)
        elif new_status == "Back Transit" and old_status == "In Transit":
            # Products are being returned — no stock change yet
            self._create_transfer_moves(transfer, old_status, new_status, user)
        elif new_status == "Back Received" and old_status == "Back Transit":
            # Products arrived back at source — restore their stock
            self._restore_source_stock(transfer)
            self._create_transfer_moves(transfer, old_status, new_status, user)
        elif new_status == "Cancelled":
            if old_status in ("In Transit", "Back Transit") and not transfer.stock_received:
                self._restore_source_stock(transfer)
                self._create_transfer_moves(transfer, old_status, new_status, user)

    @staticmethod
    def _create_transfer_moves(transfer, old_status, new_status, user=None):
        """Bulk-create StockMove history rows — one per transfer line."""
        from_name = transfer.from_office.name if transfer.from_office else "Unknown"
        to_name = transfer.to_office.name if transfer.to_office else "Unknown"
        reference = transfer.transfer_number or f"IT-{transfer.pk}"
        now = timezone.now()
        move_type = "Adjustment" if new_status == "Cancelled" else "Transfer"

        moves = [
            StockMove(
                date=now,
                reference=reference,
                product=line.product,
                source_location=from_name,
                destination_location=to_name,
                quantity=line.quantity,
                uom=line.unit or "",
                move_type=move_type,
                done_by=user,
                from_status=old_status,
                to_status=new_status,
            )
            for line in transfer.lines.select_related("product").all()
            if line.quantity
        ]
        if moves:
            StockMove.objects.bulk_create(moves)

    def perform_create(self, serializer):
        with transaction.atomic():
            serializer.save()

    def perform_update(self, serializer):
        old_status = serializer.instance.status
        try:
            with transaction.atomic():
                transfer = serializer.save()
                new_status = transfer.status
                self._apply_status_transition(
                    transfer, old_status, new_status,
                    user=self.request.user if self.request.user.is_authenticated else None,
                )
        except ValueError as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(exc)})

    def perform_destroy(self, instance):
        with transaction.atomic():
            if instance.stock_deducted and not instance.stock_received:
                self._restore_source_stock(instance)
            instance.delete()

    # ── quick status-change action ────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="change-status")
    def change_status(self, request, pk=None):
        transfer = self.get_object()
        new_status = (request.data.get("status") or "").strip()
        valid = [c[0] for c in InternalTransfer.STATUS_CHOICES]
        if new_status not in valid:
            return Response(
                {"detail": f"Invalid status. Choose from: {valid}"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        old_status = transfer.status
        try:
            with transaction.atomic():
                update_fields = {"status": new_status}
                # Save transport details when dispatching (Draft → In Transit)
                if old_status == "Draft" and new_status == "In Transit":
                    transport_keys = [
                        "transport_person", "transport_phone", "transport_address",
                        "vehicle_number", "dispatch_date",
                    ]
                    for key in transport_keys:
                        value = request.data.get(key)
                        if value is not None:
                            update_fields[key] = value
                InternalTransfer.objects.filter(pk=transfer.pk).update(**update_fields)
                transfer.refresh_from_db()
                self._apply_status_transition(
                    transfer, old_status, new_status,
                    user=request.user if request.user.is_authenticated else None,
                )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        serializer = InternalTransferReadSerializer(transfer, context={"request": request})
        return Response(serializer.data)

    # ── back-receive: inspect returned goods, restore good stock, log damage ──
    @action(detail=True, methods=["post"], url_path="back-receive")
    def back_receive(self, request, pk=None):
        """
        POST /api/internal-transfers/{id}/back-receive/

        Body: { "lines": [{"line_id": 1, "good_qty": 3, "damaged_qty": 2}, ...] }

        For each line:
          - good_qty is added back to the source LocationStock
          - damaged_qty is recorded in ReturnDamageHistory (via a new ReturnHeader)
          - good_qty + damaged_qty must equal the original transfer line quantity
        Transfer status is updated to "Back Received".
        """
        from returns.models import ReturnHeader, ReturnLine, ReturnDamageHistory
        from django.utils import timezone as tz

        transfer = self.get_object()
        if transfer.status != "Back Transit":
            return Response(
                {"detail": "Transfer must be in 'Back Transit' status to back-receive."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        lines_data = request.data.get("lines", [])
        if not lines_data:
            return Response(
                {"detail": "No line data provided."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Validate all lines before touching the DB
        errors = []
        processed = []
        for item in lines_data:
            line_id = item.get("line_id")
            try:
                good_qty = Decimal(str(item.get("good_qty", 0)))
                damaged_qty = Decimal(str(item.get("damaged_qty", 0)))
            except Exception:
                errors.append(f"Line {line_id}: invalid quantity values.")
                continue

            try:
                line = transfer.lines.select_related("product").get(pk=line_id)
            except Exception:
                errors.append(f"Line {line_id}: not found on this transfer.")
                continue

            expected = Decimal(str(line.quantity))
            if (good_qty + damaged_qty) != expected:
                errors.append(
                    f"Line {line_id} ({line.product_name}): "
                    f"good_qty ({good_qty}) + damaged_qty ({damaged_qty}) "
                    f"must equal transfer quantity ({expected})."
                )
                continue

            if good_qty < 0 or damaged_qty < 0:
                errors.append(f"Line {line_id}: quantities cannot be negative.")
                continue

            processed.append((line, good_qty, damaged_qty))

        if errors:
            return Response(
                {"detail": " | ".join(errors)},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                # 1. Restore good quantities to source location
                if transfer.from_office_id:
                    for line, good_qty, _damaged in processed:
                        if good_qty > 0 and line.product:
                            add_location_stock(
                                location=transfer.from_office,
                                product=line.product,
                                quantity=good_qty,
                            )

                # 2. Create ReturnHeader (always, for audit trail) with new type
                reference = transfer.transfer_number or f"IT-{transfer.pk}"
                source_name = transfer.from_office.name if transfer.from_office else ""
                header = ReturnHeader.objects.create(
                    return_type="instant_it_return",
                    source_document_type="INTERNAL_TRANSFER",
                    status="Received",
                    return_date=tz.localdate(),
                    source_location=source_name,
                    destination_location=source_name,
                    remarks=f"Back-receive from internal transfer {reference}",
                )
                for line, good_qty, damaged_qty in processed:
                    item_name = line.product_name or (
                        line.product.name if line.product else ""
                    )
                    item_code = line.product_code or ""
                    ret_line = ReturnLine.objects.create(
                        return_header=header,
                        source_document_number=reference,
                        source_line_id=line.pk,
                        item_name=item_name,
                        item_code=item_code,
                        item=line.product_id,
                        unit=line.unit,
                        return_quantity=line.quantity,
                        good_quantity=good_qty,
                        damaged_quantity=damaged_qty,
                    )
                    if damaged_qty > 0:
                        ReturnDamageHistory.objects.create(
                            return_header=header,
                            return_line=ret_line,
                            item_name=item_name,
                            item_code=item_code,
                            item=line.product_id,
                            damaged_quantity=damaged_qty,
                            source_document_number=reference,
                        )

                # 3. Update transfer status
                InternalTransfer.objects.filter(pk=transfer.pk).update(
                    status="Back Received",
                    stock_deducted=False,
                )
                transfer.refresh_from_db()
                self._create_transfer_moves(
                    transfer, "Back Transit", "Back Received",
                    user=request.user if request.user.is_authenticated else None,
                )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        serializer = InternalTransferReadSerializer(transfer, context={"request": request})
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────
#  STOCK-IN BATCH ENDPOINT
#  POST /api/stock-in/
#  Creates one StockAdjustment (Pending Approval) per row, all in a single
#  atomic transaction so SQLite never sees concurrent writes from the same
#  request and "database is locked" cannot occur.
# ─────────────────────────────────────────────────────────────
class StockInBatchView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from datetime import date as _date  # noqa: PLC0415

        product_id = request.data.get('product')
        rows = request.data.get('rows', [])
        raw_date = request.data.get('adjustment_date')

        # Always work with a real date object so that _movement_timestamp(.year) works
        if raw_date:
            try:
                adjustment_date = _date.fromisoformat(str(raw_date))
            except ValueError:
                adjustment_date = timezone.localdate()
        else:
            adjustment_date = timezone.localdate()

        if not product_id:
            return Response({'error': 'product is required'}, status=http_status.HTTP_400_BAD_REQUEST)

        if not rows:
            return Response({'error': 'rows must be a non-empty list'}, status=http_status.HTTP_400_BAD_REQUEST)

        from inventory.models.product import Product  # noqa: PLC0415
        try:
            source_product = Product.objects.select_related('uom', 'category', 'subcategory').get(
                id=product_id, is_active=True
            )
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=http_status.HTTP_404_NOT_FOUND)

        # Shared defaults from the source product
        unit_price = float(source_product.cost or 0)
        unit = source_product.uom.name if source_product.uom_id else 'Unit'
        actor = request.user if getattr(request.user, 'is_authenticated', False) else None

        # Validate that all referenced offices exist (keep office_location on the adjustment
        # for traceability) but do NOT clone the product per-office — the source product's
        # on_hand tracks the overall total and must never change its code/SKU.
        from procurement.models.office_models import OfficeManagement  # noqa: PLC0415
        office_ids = [r.get('office_location') for r in rows if r.get('office_location')]
        offices_by_id = {
            str(o.pk): o
            for o in OfficeManagement.objects.filter(pk__in=office_ids)
        }

        system_qty = float(source_product.on_hand or 0)

        created = []
        errors = []

        with transaction.atomic():
            for idx, row in enumerate(rows):
                office_id = row.get('office_location')
                try:
                    qty = float(row.get('qty', 0) or 0)
                except (TypeError, ValueError):
                    qty = 0

                if not office_id or qty <= 0:
                    errors.append(f"Row {idx + 1}: office_location and qty > 0 are required.")
                    continue

                if offices_by_id.get(str(office_id)) is None:
                    errors.append(f"Row {idx + 1}: office_location {office_id} not found.")
                    continue

                adj = StockAdjustment(
                    adjustment_date=adjustment_date,
                    adjustment_type='Increase',
                    reason='Stock addition request',
                    status='Pending Approval',
                    office_location_id=office_id,
                    adjusted_by=actor,
                )
                adj.save()  # generates adjustment_number via model.save()

                line = StockAdjustmentLine.objects.create(
                    adjustment=adj,
                    product=source_product,          # ← always the original product (no clones)
                    item_code=source_product.code or '',
                    item_name=source_product.name or '',
                    system_qty=system_qty,           # ← current total on_hand
                    counted_qty=system_qty + qty,
                    difference=qty,
                    unit=unit,
                    unit_price=unit_price,
                    reason='Stock addition request',
                )

                _rebuild_adjustment_totals_and_stock_moves(adj, [line])
                created.append({'id': adj.id, 'adjustment_number': adj.adjustment_number})

        if not created:
            return Response(
                {'error': 'No valid rows to process.', 'details': errors},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {'created': created, 'count': len(created), 'errors': errors},
            status=http_status.HTTP_201_CREATED,
        )
