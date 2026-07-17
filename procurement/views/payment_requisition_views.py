from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from paginations import Pagination
from inventory.views import CreatedByMixin
from ..models.payment_requisition_models import (
    PaymentRequisition,
    PaymentRequisitionItem,
)
from ..serializers.payment_requisition_serializers import (
    PaymentRequisitionSerializer,
    PaymentRequisitionCreateSerializer,
    PaymentRequisitionItemSerializer,
)


class PaymentRequisitionViewSet(CreatedByMixin, viewsets.ModelViewSet):
    queryset = (
        PaymentRequisition.objects.select_related(
            "work_order",
            "grn",
            "supplier",
            "budget_code",
            "account_code",
            "project",
            "department",
            "approver",
            "created_by",
        )
        .prefetch_related("prf_items")
        .all()
    )
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        "prf_number",
        "supplier__name",
        "invoice_number",
        "status",
    ]
    ordering_fields = ["created_at", "total_amount", "invoice_date"]
    ordering = ["-created_at"]
    filterset_fields = ["status", "supplier", "priority", "department"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return PaymentRequisitionCreateSerializer
        return PaymentRequisitionSerializer

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = PaymentRequisition.objects.all()
        from django.db.models import Sum

        data = {
            "total": qs.count(),
            "draft": qs.filter(status="Draft").count(),
            "pending": qs.filter(status="Pending Approval").count(),
            "approved": qs.filter(status="Approved").count(),
            "paid": qs.filter(status="Paid").count(),
            "total_amount": qs.aggregate(total=Sum("total_amount"))["total"] or 0,
        }
        return Response(data)


class PaymentRequisitionItemViewSet(viewsets.ModelViewSet):
    queryset = PaymentRequisitionItem.objects.select_related(
        "payment_requisition", "item"
    ).all()
    serializer_class = PaymentRequisitionItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["payment_requisition"]
