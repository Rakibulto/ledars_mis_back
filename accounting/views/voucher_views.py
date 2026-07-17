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
    VoucherLine,
    VoucherApproval,
    VoucherAttachment,
    JournalEntry,
    JournalItem,
)
from accounting.serializers.voucher_serializers import (
    VoucherListSerializer,
    VoucherDetailSerializer,
    VoucherWriteSerializer,
    VoucherApprovalSerializer,
    VoucherAttachmentSerializer,
)
from accounting.views.status_transition_mixin import StatusTransitionMixin


class VoucherViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = Voucher.objects.select_related(
        "journal", "created_by", "approved_by", "project"
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["voucher_type", "status", "journal", "date"]
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
    def post_voucher(self, request, pk=None):
        """Post an approved voucher — creates journal entry and updates balances."""
        voucher = self.get_object()
        if voucher.status != "approved":
            return Response(
                {"detail": "Only approved vouchers can be posted."}, status=400
            )

        with transaction.atomic():
            entry = JournalEntry.objects.create(
                journal=voucher.journal,
                date=voucher.date,
                narration=voucher.narration,
                status="posted",
                is_auto_generated=True,
                source_document=voucher.voucher_number,
                created_by=request.user,
                posted_by=request.user,
                posted_at=timezone.now(),
            )
            total_debit = 0
            total_credit = 0
            for line in voucher.lines.select_related("account").all():
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=line.account,
                    label=line.description,
                    debit=line.debit,
                    credit=line.credit,
                )
                account = line.account
                account.current_balance += line.debit - line.credit
                account.save(update_fields=["current_balance"])
                total_debit += line.debit
                total_credit += line.credit

            entry.total_debit = total_debit
            entry.total_credit = total_credit
            entry.save(update_fields=["total_debit", "total_credit"])

            voucher.journal_entry = entry
            voucher.status = "posted"
            voucher.save(update_fields=["journal_entry", "status"])

        return Response(
            {"detail": f"Voucher posted. Journal entry {entry.reference} created."}
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
