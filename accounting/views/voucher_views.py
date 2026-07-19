from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.utils import timezone

from accounting.models import (
    Voucher,
    VoucherApproval,
    VoucherAttachment,
)
from accounting.serializers.voucher_serializers import (
    VoucherListSerializer,
    VoucherDetailSerializer,
    VoucherWriteSerializer,
    VoucherApprovalSerializer,
    VoucherAttachmentSerializer,
)
from accounting.views.status_transition_mixin import StatusTransitionMixin
from accounting.services.voucher_posting import post_voucher, reverse_voucher
from accounting.services.exceptions import PostingError


class VoucherViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = (
        Voucher.objects.select_related(
            "journal", "created_by", "approved_by", "project", "ngo_project"
        )
        .prefetch_related("lines__account")
        .all()
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "voucher_type",
        "status",
        "journal",
        "date",
        "ngo_project",
        "project",
    ]
    search_fields = ["voucher_number", "payee", "narration"]
    ordering_fields = ["date", "voucher_number", "total_amount", "created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return VoucherListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return VoucherWriteSerializer
        return VoucherDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="submit-voucher")
    def submit(self, request, pk=None):
        """Submit voucher for approval."""
        voucher = self.get_object()
        if voucher.status != "draft":
            return Response(
                {"detail": "Only draft vouchers can be submitted."}, status=400
            )
        voucher.status = "pending"
        voucher.save(update_fields=["status"])
        return Response({"detail": "Voucher submitted for approval."})

    @action(detail=True, methods=["post"], url_path="approve-voucher")
    def approve(self, request, pk=None):
        """Approve a voucher."""
        voucher = self.get_object()
        if voucher.status != "pending":
            return Response(
                {"detail": "Only pending vouchers can be approved."}, status=400
            )

        with transaction.atomic():
            voucher.status = "approved"
            voucher.approved_by = request.user
            voucher.approved_at = timezone.now()
            voucher.save(update_fields=["status", "approved_by", "approved_at"])

            VoucherApproval.objects.create(
                voucher=voucher,
                approver=request.user,
                status="approved",
                acted_at=timezone.now(),
            )
        return Response({"detail": "Voucher approved."})

    @action(detail=True, methods=["post"], url_path="reject-voucher")
    def reject(self, request, pk=None):
        """Reject a voucher."""
        voucher = self.get_object()
        remarks = request.data.get("remarks", "")
        voucher.status = "rejected"
        voucher.save(update_fields=["status"])
        VoucherApproval.objects.create(
            voucher=voucher,
            approver=request.user,
            status="rejected",
            remarks=remarks,
            acted_at=timezone.now(),
        )
        return Response({"detail": "Voucher rejected."})

    @action(detail=True, methods=["post"], url_path="post-voucher")
    def post_voucher_action(self, request, pk=None):
        """Post an approved voucher — JE + GL + bank adjustment (atomic)."""
        voucher = self.get_object()
        try:
            locked, entry, bank_txns = post_voucher(voucher, user=request.user)
        except PostingError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "detail": f"Voucher posted. Journal entry {entry.reference} created.",
                "voucher_id": locked.pk,
                "journal_entry": entry.reference,
                "bank_transactions": len(bank_txns),
            }
        )

    @action(detail=True, methods=["post"], url_path="reverse-voucher")
    def reverse_voucher_action(self, request, pk=None):
        """Reverse a posted voucher (JE + bank); mark cancelled."""
        voucher = self.get_object()
        remarks = request.data.get("remarks", "")
        try:
            locked, reversal = reverse_voucher(
                voucher, user=request.user, remarks=remarks
            )
        except PostingError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "detail": f"Voucher reversed. Reversal entry {reversal.reference}.",
                "voucher_id": locked.pk,
                "status": locked.status,
                "reversal_entry": reversal.reference,
            }
        )


class VoucherApprovalViewSet(viewsets.ModelViewSet):
    queryset = VoucherApproval.objects.select_related("voucher", "approver").all()
    serializer_class = VoucherApprovalSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["voucher", "status"]


class VoucherAttachmentViewSet(viewsets.ModelViewSet):
    queryset = VoucherAttachment.objects.all()
    serializer_class = VoucherAttachmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["voucher"]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)
