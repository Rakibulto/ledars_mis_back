from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.db.models import Q
from paginations import Pagination
from vendorportal.views.atomic import AtomicModelViewSetMixin
from inventory.views import CreatedByMixin

from ..models.comparative_models import (
    ComparativeStatement,
    ComparativeLineItem,
    ComparativeApprovalWorkflow,
    ComparativeNote,
    ComparativeVendorEvaluation,
    ComparativeVendorFinancial,
    ComparativeNotificationLog,
)
from ..serializers.comparative_serializers import (
    ComparativeStatementSerializer,
    ComparativeStatementCreateSerializer,
    ComparativeLineItemSerializer,
    ComparativeLineItemCreateSerializer,
    ComparativeApprovalWorkflowSerializer,
    ComparativeNoteSerializer,
    ComparativeVendorEvaluationSerializer,
    ComparativeVendorEvaluationCreateSerializer,
    ComparativeVendorFinancialSerializer,
)


class ComparativeStatementViewSet(AtomicModelViewSetMixin, CreatedByMixin, viewsets.ModelViewSet):
    queryset = (
        ComparativeStatement.objects.select_related(
            "rfq__rfq_category", "recommended_vendor", "created_by", "approved_by"
        )
        .prefetch_related(
            "line_items__item",
            "line_items__vendor",
            "approval_workflow__approver",
            "notes__author",
            "vendor_evaluations__vendor",
            "vendor_evaluations__criteria",
            "vendor_financials__vendor",
            "notification_logs",
            "rfq__line_items",
            "rfq__requisitions__budget_code",
            "rfq__requisitions__project",
            "rfq__requisitions__requesting_office",
            "rfq__vendor_submissions",
            "rfq__vendor_submissions__financial_proposal__items",
        )
        .all()
    )
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        "cs_number",
        "title",
        "rfq__rfq_number",
        "rfq__rfq_title",
        "status",
        "project",
        "office",
        "budget_code",
    ]
    ordering_fields = ["created_at", "cs_number", "status"]
    ordering = ["-created_at"]
    filterset_fields = ["status", "rfq"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ComparativeStatementCreateSerializer
        return ComparativeStatementSerializer

    def list(self, request, *args, **kwargs):
        """Auto-create CS for any expired RFQs before returning the list."""
        from procurement.signals import create_comparative_statements_for_expired_rfqs
        create_comparative_statements_for_expired_rfqs()
        return super().list(request, *args, **kwargs)

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = ComparativeStatement.objects.all()
        data = {
            "total": qs.count(),
            "draft": qs.filter(status__iexact="draft").count(),
            "under_review": qs.filter(
                Q(status="under_review") | Q(status__iexact="Under Review")
            ).count(),
            "pending_approval": qs.filter(
                Q(status="pending_approval") | Q(status__iexact="Pending Approval")
            ).count(),
            "approved": qs.filter(status__iexact="approved").count(),
            "rejected": qs.filter(status__iexact="rejected").count(),
        }
        return Response(data)

    @action(detail=False, methods=["delete", "post"], url_path="delete-all")
    def delete_all(self, request):
        qs = ComparativeStatement.objects.all()
        count = qs.count()
        qs.delete()
        return Response({"deleted": count})


class ComparativeLineItemViewSet(viewsets.ModelViewSet):
    queryset = ComparativeLineItem.objects.select_related(
        "comparative", "item", "quotation", "vendor"
    ).all()
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["comparative", "vendor", "is_recommended", "is_lowest"]
    search_fields = ["item__item_name", "vendor__name"]
    ordering_fields = ["quoted_price", "total_price"]
    ordering = ["item", "quoted_price"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ComparativeLineItemCreateSerializer
        return ComparativeLineItemSerializer


class ComparativeApprovalWorkflowViewSet(viewsets.ModelViewSet):
    queryset = ComparativeApprovalWorkflow.objects.select_related(
        "comparative", "approver"
    ).all()
    serializer_class = ComparativeApprovalWorkflowSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["comparative", "status", "level"]
    ordering_fields = ["level"]
    ordering = ["level"]


class ComparativeNoteViewSet(viewsets.ModelViewSet):
    queryset = ComparativeNote.objects.select_related("comparative", "author").all()
    serializer_class = ComparativeNoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["comparative"]
    search_fields = ["text", "author__username"]
    ordering_fields = ["date"]
    ordering = ["date"]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class ComparativeVendorEvaluationViewSet(viewsets.ModelViewSet):
    queryset = (
        ComparativeVendorEvaluation.objects.select_related("comparative", "vendor")
        .prefetch_related("criteria")
        .all()
    )
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["comparative", "vendor", "is_recommended"]
    ordering_fields = ["total_score"]
    ordering = ["-total_score"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ComparativeVendorEvaluationCreateSerializer
        return ComparativeVendorEvaluationSerializer


class ComparativeVendorFinancialViewSet(viewsets.ModelViewSet):
    queryset = ComparativeVendorFinancial.objects.select_related(
        "comparative", "vendor", "quotation"
    ).all()
    serializer_class = ComparativeVendorFinancialSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["comparative", "vendor"]
    ordering_fields = ["grand_total", "subtotal"]
    ordering = ["grand_total"]
