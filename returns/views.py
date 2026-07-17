from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend

try:
    from paginations import Pagination
except ImportError:
    from rest_framework.pagination import PageNumberPagination as Pagination

from .models import ReturnHeader, ReturnLine, ReturnDamageHistory
from .serializers import (
    ReturnHeaderReadSerializer,
    ReturnHeaderWriteSerializer,
    ReturnLineSerializer,
    ReturnDamageHistorySerializer,
)

# ─── Status transition map ────────────────────────────────────────────────────
_TRANSITIONS = {
    'Draft': 'submit',
    'Pending Approval': 'dispatch',
    'In Transit': 'receive',
}
_ALLOWED_FROM = {
    'submit': ['Draft'],
    'dispatch': ['Pending Approval'],
    'receive': ['In Transit'],
    'cancel': ['Draft', 'Pending Approval', 'In Transit'],
}
_TARGET_STATUS = {
    'submit': 'Pending Approval',
    'dispatch': 'In Transit',
    'receive': 'Received',
    'cancel': 'Cancelled',
}


class ReturnHeaderViewSet(ModelViewSet):
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        'return_number', 'source_location', 'destination_location',
        'project', 'remarks', 'lines__source_document_number',
        'lines__item_name', 'lines__item_code',
    ]
    ordering_fields = ['return_number', 'return_date', 'status', 'created_at']
    ordering = ['-created_at']
    filterset_fields = ['return_type', 'source_document_type', 'status', 'created_by']

    def get_queryset(self):
        qs = ReturnHeader.objects.prefetch_related(
            'lines', 'damage_histories'
        ).select_related('created_by', 'approved_by', 'received_by').all()

        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(return_date__gte=date_from)
        if date_to:
            qs = qs.filter(return_date__lte=date_to)
        return qs

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return ReturnHeaderReadSerializer
        return ReturnHeaderWriteSerializer

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        instance = serializer.save(created_by=user)
        self._auto_populate_locations(instance)

    def _auto_populate_locations(self, obj):
        """
        Auto-set source_location and destination_location from the first line's
        source document (GIN or InternalTransfer) after creation.
        source_location  = where the items currently are (returning FROM here)
        destination_location = where the items should go back (returning TO here)
        """
        first_line = obj.lines.first()
        if not first_line:
            return
        source_doc_num = first_line.source_document_number
        if not source_doc_num:
            return
        try:
            if obj.source_document_type == 'GIN':
                from inventory.models.operations import GIN
                gin = GIN.objects.select_related('office_location').filter(
                    gin_number=source_doc_num
                ).first()
                if gin:
                    # Items were issued FROM office_location TO the project/issued_to
                    returning_from = gin.issued_to or gin.project or source_doc_num
                    returning_to = (
                        gin.office_location.name if gin.office_location
                        else (gin.issue_from or source_doc_num)
                    )
                    obj.source_location = returning_from
                    obj.destination_location = returning_to
                    obj.save(update_fields=['source_location', 'destination_location'])
            elif obj.source_document_type == 'INTERNAL_TRANSFER':
                from inventory.models.operations import InternalTransfer
                it = InternalTransfer.objects.select_related(
                    'from_office', 'to_office'
                ).filter(transfer_number=source_doc_num).first()
                if it:
                    # Items are currently at to_office; return them to from_office
                    returning_from = it.to_office.name if it.to_office else source_doc_num
                    returning_to = it.from_office.name if it.from_office else source_doc_num
                    obj.source_location = returning_from
                    obj.destination_location = returning_to
                    obj.save(update_fields=['source_location', 'destination_location'])
        except Exception:
            pass  # Do not break the create if location lookup fails

    def _action_transition(self, request, pk, action_key):
        """Generic handler for submit / dispatch / receive / cancel."""
        obj = self.get_object()
        allowed = _ALLOWED_FROM.get(action_key, [])
        if obj.status not in allowed:
            return Response(
                {'detail': f'Cannot {action_key} from status "{obj.status}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            obj.status = _TARGET_STATUS[action_key]
            now = timezone.now()
            if action_key == 'submit':
                obj.submitted_at = now
                obj.approved_by = request.user if request.user.is_authenticated else None
            elif action_key == 'dispatch':
                obj.dispatched_at = now
                # Save transport / courier details supplied by the caller
                transport_fields = [
                    'transport_person', 'transport_phone', 'transport_address',
                    'vehicle_number', 'tracking_number', 'dispatch_date', 'dispatch_remarks',
                ]
                for field in transport_fields:
                    value = request.data.get(field)
                    if value is not None:
                        setattr(obj, field, value)
                self._process_dispatch(obj)
            elif action_key == 'receive':
                obj.received_at = now
                obj.received_by = request.user if request.user.is_authenticated else None
                self._process_receive(request, obj)
            obj.save()

        serializer = ReturnHeaderReadSerializer(obj)
        return Response(serializer.data)

    def _process_dispatch(self, obj):
        """
        On dispatch of an internal_transfer_return: deduct return_quantity from
        the to_office (current holder) for each line.
        Project returns are skipped — no inventory movement on dispatch.
        Raises ValueError if any line has insufficient stock (triggers rollback).
        """
        if obj.return_type != 'internal_transfer_return':
            return

        to_office_id = self._resolve_dispatch_location_id(obj)
        if not to_office_id:
            raise ValueError(
                'Cannot dispatch: could not determine the current holding location '
                'from the source internal transfer.'
            )

        from decimal import Decimal
        from inventory.models.product import LocationStock, Product

        for line in obj.lines.all():
            if not line.item:
                continue

            ret_qty = Decimal(str(line.return_quantity or 0))
            if ret_qty <= 0:
                continue

            product = Product.objects.filter(pk=line.item).first()
            if not product:
                raise ValueError(
                    f'Cannot dispatch: product id {line.item} ("{line.item_name}") not found.'
                )

            ls = LocationStock.objects.select_for_update().filter(
                product=product, office_location_id=to_office_id
            ).first()

            if not ls:
                raise ValueError(
                    f'Cannot dispatch: no stock record found for "{line.item_name}" '
                    f'at the destination location (office id {to_office_id}).'
                )

            if ls.quantity < ret_qty:
                raise ValueError(
                    f'Insufficient stock for "{line.item_name}": '
                    f'available {ls.quantity}, required {ret_qty}.'
                )

            ls.quantity -= ret_qty
            ls.save(update_fields=['quantity'])
            # post_save signal on LocationStock auto-syncs Product.on_hand

    def _resolve_dispatch_location_id(self, obj):
        """
        Return the to_office FK id from the source InternalTransfer —
        this is the location currently holding the stock that will be sent back.
        """
        first_line = obj.lines.first()
        source_doc_num = first_line.source_document_number if first_line else None
        if not source_doc_num:
            return None
        try:
            from inventory.models.operations import InternalTransfer
            it = InternalTransfer.objects.filter(transfer_number=source_doc_num).first()
            return it.to_office_id if it else None
        except Exception:
            pass
        return None

    def _process_receive(self, request, obj):
        """
        On receive: validate good+damaged=return_qty, persist the split on each
        line, record damage histories, and restore good quantities to the
        source office location stock.
        Raises ValueError on validation failure (transaction rolls back automatically).
        """
        lines_data = request.data.get('lines', [])
        lines_map = {item['id']: item for item in lines_data if 'id' in item}

        source_location_id = self._resolve_source_location_id(obj)

        for line in obj.lines.all():
            override = lines_map.get(line.pk, {})
            good_qty = float(override.get('good_quantity', line.good_quantity or 0))
            damaged_qty = float(override.get('damaged_quantity', line.damaged_quantity or 0))
            ret_qty = float(line.return_quantity or 0)

            # Validate: good + damaged must equal return_quantity
            if abs((good_qty + damaged_qty) - ret_qty) > 0.001:
                raise ValueError(
                    f'"{line.item_name}": good ({good_qty}) + damaged ({damaged_qty}) '
                    f'must equal return quantity ({ret_qty}).'
                )

            line.good_quantity = good_qty
            line.damaged_quantity = damaged_qty
            line.save(update_fields=['good_quantity', 'damaged_quantity'])

            # Record damage history
            if damaged_qty > 0:
                ReturnDamageHistory.objects.create(
                    return_header=obj,
                    return_line=line,
                    item_name=line.item_name,
                    item_code=line.item_code,
                    item=line.item,
                    damaged_quantity=damaged_qty,
                    source_document_number=line.source_document_number,
                    remarks=line.remarks,
                )

            # Restore good stock to source location
            if good_qty > 0 and source_location_id:
                self._restore_location_stock(line, good_qty, source_location_id)

    def _resolve_source_location_id(self, obj):
        """
        Return the integer PK of the OfficeManagement where returned goods belong.
        - GIN return  → GIN.office_location_id  (the office that issued the goods)
        - IT return   → InternalTransfer.from_office_id  (the transfer origin)
        Returns None if the lookup fails (stock update is then skipped gracefully).
        """
        first_line = obj.lines.first()
        source_doc_num = first_line.source_document_number if first_line else None
        if not source_doc_num:
            return None
        try:
            if obj.source_document_type == 'GIN':
                from inventory.models.operations import GIN
                gin = GIN.objects.filter(gin_number=source_doc_num).first()
                return gin.office_location_id if gin else None
            if obj.source_document_type == 'INTERNAL_TRANSFER':
                from inventory.models.operations import InternalTransfer
                it = InternalTransfer.objects.filter(transfer_number=source_doc_num).first()
                return it.from_office_id if it else None
        except Exception:
            pass
        return None

    def _restore_location_stock(self, line, qty, office_location_id):
        """
        Add qty back to LocationStock at the given office.
        Creates the row if it does not yet exist.
        The LocationStock post_save signal automatically re-syncs Product.on_hand,
        so no separate Product update is needed.
        """
        from decimal import Decimal
        from inventory.models.product import LocationStock, Product
        from procurement.models.office_models import OfficeManagement

        if not line.item:
            return

        product = Product.objects.filter(pk=line.item).first()
        if not product:
            return

        office = OfficeManagement.objects.filter(pk=office_location_id).first()
        if not office:
            return

        ls, _ = LocationStock.objects.get_or_create(
            product=product,
            office_location=office,
            defaults={'quantity': Decimal('0')},
        )
        ls.quantity = Decimal(str(ls.quantity)) + Decimal(str(qty))
        ls.save(update_fields=['quantity'])

    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        return self._action_transition(request, pk, 'submit')

    @action(detail=True, methods=['post'], url_path='dispatch')
    def dispatch_return(self, request, pk=None):
        try:
            return self._action_transition(request, pk, 'dispatch')
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='receive')
    def receive(self, request, pk=None):
        try:
            return self._action_transition(request, pk, 'receive')
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        return self._action_transition(request, pk, 'cancel')


class ReturnLineViewSet(ModelViewSet):
    queryset = ReturnLine.objects.select_related('return_header').all()
    serializer_class = ReturnLineSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ['source_document_number', 'item_name', 'item_code']
    filterset_fields = ['return_header', 'source_document_number']
    ordering = ['id']


class ReturnDamageHistoryViewSet(ModelViewSet):
    queryset = ReturnDamageHistory.objects.select_related('return_header', 'return_line').all()
    serializer_class = ReturnDamageHistorySerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ['item_name', 'item_code', 'source_document_number', 'return_header__return_number']
    filterset_fields = ['return_header', 'return_line']
    ordering = ['-recorded_at']
    http_method_names = ['get', 'head', 'options']  # read-only

