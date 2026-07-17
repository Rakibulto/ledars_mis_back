from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from paginations import Pagination
from inventory.views import CreatedByMixin
from ..models.treasury_models import TreasuryProcessing, PaymentRecord, PaymentTimeline
from ..serializers.treasury_serializers import (
    TreasuryProcessingSerializer,
    PaymentRecordSerializer,
    PaymentTimelineSerializer,
)


class TreasuryProcessingViewSet(CreatedByMixin, viewsets.ModelViewSet):
    queryset = TreasuryProcessing.objects.select_related(
        "payment_requisition",
        "payment_requisition__supplier",
        "reviewed_by",
        "approved_by",
        "created_by",
    ).all()
    serializer_class = TreasuryProcessingSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        "processing_number",
        "payment_requisition__prf_number",
        "status",
    ]
    ordering_fields = ["created_at", "approved_amount"]
    ordering = ["-created_at"]
    filterset_fields = ["status"]

    @action(detail=False, methods=["get"], url_path="finance-review")
    def finance_review(self, request):
        qs = self.get_queryset().filter(status__in=["Pending Review", "Under Review"])
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="analytics")
    def analytics(self, request):
        qs = TreasuryProcessing.objects.all()
        from django.db.models import Sum, Avg
        from ..models.payment_requisition_models import PaymentRequisition
        from datetime import datetime

        current_month = datetime.now().month
        current_year = datetime.now().year

        total_paid = float(
            PaymentRequisition.objects.filter(status="Paid").aggregate(
                total=Sum("total_amount")
            )["total"]
            or 0
        )
        total_pending = float(
            PaymentRequisition.objects.filter(
                status__in=["Pending Approval", "Submitted", "Processing"]
            ).aggregate(total=Sum("total_amount"))["total"]
            or 0
        )

        data = {
            "total": qs.count(),
            "pending_review": qs.filter(status="Pending Review").count(),
            "pending_amount": total_pending,
            "approved": qs.filter(status="Approved for Payment").count(),
            "processed": qs.filter(status="Payment Processed").count(),
            "processed_this_month": qs.filter(
                status="Payment Processed",
                created_at__month=current_month,
                created_at__year=current_year,
            ).count(),
            "on_hold": qs.filter(status="On Hold").count(),
            "total_approved": float(
                qs.aggregate(total=Sum("approved_amount"))["total"] or 0
            ),
            "total_paid": total_paid,
            "total_pending": total_pending,
            "total_requisitions": PaymentRequisition.objects.count(),
            "avg_processing_time": 5,  # Default avg days
        }
        return Response(data)


class PaymentRecordViewSet(viewsets.ModelViewSet):
    queryset = PaymentRecord.objects.select_related(
        "treasury_processing", "supplier", "processed_by"
    ).all()
    serializer_class = PaymentRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["reference_number", "supplier__name", "status"]
    ordering_fields = ["payment_date", "amount", "created_at"]
    ordering = ["-created_at"]
    filterset_fields = ["status", "payment_method", "supplier"]

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(processed_by=self.request.user)


class PaymentTimelineViewSet(viewsets.ModelViewSet):
    queryset = PaymentTimeline.objects.select_related(
        "payment_requisition", "performed_by"
    ).all()
    serializer_class = PaymentTimelineSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["payment_requisition", "stage"]
    ordering = ["timestamp"]

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(performed_by=self.request.user)
