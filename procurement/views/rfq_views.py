from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count, Q, Sum

from inventory.views import CreatedByMixin
from paginations import Pagination
from vendorportal.views.atomic import AtomicModelViewSetMixin

from ..models.rfq_models import RFQ, RFQVendorInvitation, RFQAttachment, RFQLineItem
from ..serializers.rfq_serializers import (
    RFQSerializer,
    RFQCreateUpdateSerializer,
    RFQAttachmentSerializer,
    RFQInvitedVendorSerializer,
    RFQVendorInvitationSerializer,
    RFQInvitedVendorsSummarySerializer,
    RFQLineItemSerializer,
    SimpleRFQSerializer,
)
from ..filters.rfq_filters import RFQFilter, RFQInvitedVendorFilter, RFQAttachmentFilter


class RFQAttachmentViewSet(AtomicModelViewSetMixin, CreatedByMixin, viewsets.ModelViewSet):
    queryset = RFQAttachment.objects.select_related("rfq", "created_by").all()
    serializer_class = RFQAttachmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = RFQAttachmentFilter
    search_fields = [
        "rfq__rfq_number",
        "rfq__rfq_title",
        "created_by__username",
        "created_by__email",
    ]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

class RFQVendorInvitationViewSet(AtomicModelViewSetMixin, CreatedByMixin, viewsets.ModelViewSet):
    queryset = RFQVendorInvitation.objects.select_related("rfq", "vendor").all()
    serializer_class = RFQVendorInvitationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = RFQInvitedVendorFilter
    search_fields = ["rfq__rfq_number", "vendor__name", "invite_status", "email_status"]
    ordering_fields = ["invited_at", "updated_at", "invite_status", "email_status"]
    ordering = ["-invited_at"]





class RFQViewSet(AtomicModelViewSetMixin, CreatedByMixin, viewsets.ModelViewSet):
    queryset = (
        RFQ.objects.select_related("rfq_category", "created_by")
        .prefetch_related(
            "requisitions",
            "requisitions__material_items__item",
            "items",
            "rfq_attachment",
            "vendor_invitations__vendor",
            "line_items__item",
            "line_items__source_material_item__item",
        )
        .all()
    )
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = RFQFilter
    search_fields = [
        "rfq_number",
        "rfq_title",
        "description",
        "status",
        "rfq_category__name",
        "vendor_invitations__vendor__name",
        "vendor_invitations__vendor__user__username",
        "vendor_invitations__vendor__user__email",
        "created_by__username",
        "created_by__email",
    ]
    ordering_fields = [
        "created_at",
        "vendors_count",
        "responses_received",
        "total_estimated_value",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return RFQCreateUpdateSerializer
        return RFQSerializer

    def dispatch(self, request, *args, **kwargs):
        # Run auto-close and comparative-statement generation BEFORE the
        # @transaction.atomic wrapper in AtomicModelViewSetMixin kicks in.
        # SQLite only allows one writer at a time; doing a write inside a
        # read-transaction causes "database is locked" errors.
        try:
            from procurement.signals import create_comparative_statements_for_expired_rfqs
            create_comparative_statements_for_expired_rfqs()
        except Exception:
            pass
        return super().dispatch(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="simple_rfq")
    def simple_rfq(self, request):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = SimpleRFQSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)
        serializer = SimpleRFQSerializer(qs, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="invited_vendors_summary")
    def invited_vendors_summary(self, request):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        serializer = RFQInvitedVendorsSummarySerializer(
            page if page is not None else qs,
            many=True,
            context=self.get_serializer_context(),
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="rfq_summary")
    def rfq_summary(self, request):
        qs = self.filter_queryset(self.get_queryset())
        aggregates = qs.aggregate(
            total=Count("id"),
            total_vendors=Sum("vendors_count"),
            total_estimated_value=Sum("total_estimated_value"),
            draft=Count("id", filter=Q(status__iexact="draft")),
            published=Count("id", filter=Q(status__iexact="published")),
            open=Count("id", filter=Q(status__iexact="open")),
            under_evaluation=Count(
                "id", filter=Q(status__iexact="under_evaluation")
            ),
            closed=Count("id", filter=Q(status__iexact="closed")),
            awarded=Count("id", filter=Q(status__iexact="awarded")),
            cancelled=Count("id", filter=Q(status__iexact="cancelled")),
        )

        data = {
            "total": aggregates["total"] or 0,
            "draft": aggregates["draft"] or 0,
            "published": aggregates["published"] or 0,
            "open": aggregates["open"] or 0,
            "under_evaluation": aggregates["under_evaluation"] or 0,
            "closed": aggregates["closed"] or 0,
            "awarded": aggregates["awarded"] or 0,
            "cancelled": aggregates["cancelled"] or 0,
            "total_vendors": aggregates["total_vendors"] or 0,
            "total_estimated_value": aggregates["total_estimated_value"] or 0,
        }
        return Response(data)


class RFQLineItemViewSet(viewsets.ModelViewSet):
    queryset = RFQLineItem.objects.select_related(
        "rfq",
        "requisition",
        "source_material_item",
        "item",
    ).all()
    serializer_class = RFQLineItemSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        "rfq__rfq_number",
        "requisition__requisition_no",
        "item_name",
        "item__item_name",
    ]
    ordering_fields = ["created_at", "quantity", "estimated_unit_price"]
    ordering = ["-created_at"]
    filterset_fields = ["rfq", "requisition", "item"]

    def get_queryset(self):
        qs = super().get_queryset()
        rfq_number = self.request.query_params.get("rfq_number")
        if rfq_number:
            qs = qs.filter(rfq__rfq_number=rfq_number)
        return qs
