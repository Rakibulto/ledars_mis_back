from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Sum
from django.utils import timezone

from paginations import Pagination
from inventory.views import CreatedByMixin
from ..filters.procurement_filters import WorkOrderFilter
from ..models.award_models import Award
from ..models.work_order_models import (
    WorkOrder,
    WorkOrderItem,
    WorkOrderApprovalHistory,
    WorkOrderNotificationLog,
    WorkOrderAttachment,
    VendorAcceptance,
)
from ..serializers.work_order_serializers import (
    WorkOrderSerializer,
    WorkOrderLeanSerializer,
    WorkOrderCreateSerializer,
    WorkOrderItemSerializer,
    WorkOrderItemCreateSerializer,
    WorkOrderApprovalHistorySerializer,
    WorkOrderNotificationLogSerializer,
    WorkOrderAttachmentSerializer,
    VendorAcceptanceSerializer,
)


class WorkOrderViewSet(CreatedByMixin, viewsets.ModelViewSet):
    queryset = (
        WorkOrder.objects.select_related(
            "award", "vendor", "approved_by", "created_by"
        )
        .prefetch_related(
            "work_order_items__item",
            "approval_history",
            "notification_log",
            "attachments",
        )
        .all()
    )
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        "wo_number",
        "vendor__name",
        "title",
        "category",
        "status",
        "award__award_number",
        "award__comparative_statement__cs_number",
        "award__rfq__rfq_number",
        "award__comparative_statement__rfq__requisitions__requisition_no",
    ]
    ordering_fields = ["created_at", "total_amount", "delivery_date", "order_date"]
    ordering = ["-created_at"]
    filterset_class = WorkOrderFilter

    def get_queryset(self):
        queryset = super().get_queryset()
        mode = (self.request.query_params.get("mode") or "").strip().lower()
        exclude_pending = (self.request.query_params.get("exclude_pending_approval") or "").strip().lower()

        if mode == "pending":
            queryset = queryset.filter(approval_status__in=["pending-approval", "draft"])
        elif exclude_pending in {"1", "true", "yes", "on"}:
            queryset = queryset.exclude(approval_status__in=["pending-approval", "draft"])

        return queryset

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return WorkOrderCreateSerializer
        return WorkOrderSerializer

    @action(detail=False, methods=["get"], url_path="lean")
    def lean(self, request):
        """Return lightweight work order list for dropdowns.
        Uses WorkOrderLeanSerializer with only essential fields."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = WorkOrderLeanSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = WorkOrderLeanSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="full")
    def retrieve_full(self, request, pk=None):
        """Return the full work order details (heavy serializer).
        Used when a specific work order is selected from the dropdown."""
        instance = self.get_object()
        serializer = WorkOrderSerializer(instance)
        return Response(serializer.data)

    # ── helpers ─────────────────────────────────────────────────────────────
    def _get_vendor_for_wo(self, work_order):
        if work_order.award and getattr(work_order.award, "vendor_profile", None):
            return work_order.award.vendor_profile
        return work_order.vendor

    def _recipient_str(self, vendor):
        if not vendor:
            return ""
        name = getattr(vendor, "name", "") or ""
        email = getattr(vendor, "email", "") or ""
        return f"{name} <{email}>" if email else name

    def _handle_notification_sent(self, work_order):
        """When notificationSent becomes True: set vendorStatus=sent, create log once."""
        if not work_order.notification_sent:
            return
        if work_order.vendor_status == "not-sent":
            work_order.vendor_status = "sent"
            work_order.save(update_fields=["vendor_status"])
        already_logged = WorkOrderNotificationLog.objects.filter(
            work_order=work_order, status="sent"
        ).exists()
        if not already_logged:
            vendor = self._get_vendor_for_wo(work_order)
            WorkOrderNotificationLog.objects.create(
                work_order=work_order,
                channel=work_order.notification_channel or "email",
                date=timezone.now().strftime("%Y-%m-%d %H:%M"),
                status="sent",
                recipient=self._recipient_str(vendor),
            )

    def _handle_vendor_acceptance(self, work_order, old_vendor_status):
        """When vendorStatus transitions to accepted/rejected, log the event."""
        if work_order.vendor_status == "accepted" and old_vendor_status in ("sent", "pending-acceptance"):
            if not work_order.vendor_acceptance_date:
                work_order.vendor_acceptance_date = timezone.now().date()
                work_order.save(update_fields=["vendor_acceptance_date"])
            vendor = self._get_vendor_for_wo(work_order)
            WorkOrderNotificationLog.objects.create(
                work_order=work_order,
                channel=work_order.notification_channel or "system",
                date=timezone.now().strftime("%Y-%m-%d %H:%M"),
                status="vendor-accepted",
                recipient=self._recipient_str(vendor),
            )
        elif work_order.vendor_status == "rejected" and old_vendor_status in ("sent", "pending-acceptance"):
            vendor = self._get_vendor_for_wo(work_order)
            WorkOrderNotificationLog.objects.create(
                work_order=work_order,
                channel=work_order.notification_channel or "system",
                date=timezone.now().strftime("%Y-%m-%d %H:%M"),
                status="vendor-rejected",
                recipient=self._recipient_str(vendor),
            )

    def perform_create(self, serializer):
        work_order = serializer.save()
        # Auto-assign approver from the Approval Matrix for module "Work Order"
        try:
            from ..models.settings_models import ApprovalMatrix
            matrix_entry = (
                ApprovalMatrix.objects
                .filter(module="Work Order", is_active=True)
                .order_by("approval_level")
                .prefetch_related("approvers__user")
                .select_related("approver__user")
                .first()
            )
            if matrix_entry:
                approver_user = None
                # Prefer M2M approvers list (level 1 first approver)
                first_emp = matrix_entry.approvers.select_related("user").first()
                if first_emp and hasattr(first_emp, "user"):
                    approver_user = first_emp.user
                elif matrix_entry.approver and hasattr(matrix_entry.approver, "user"):
                    approver_user = matrix_entry.approver.user
                if approver_user:
                    work_order.approver = approver_user
                    work_order.save(update_fields=["approver"])
        except Exception:
            pass
        self._handle_notification_sent(work_order)

    def perform_update(self, serializer):
        old = serializer.instance
        old_approval_status = old.approval_status
        old_vendor_status = old.vendor_status
        work_order = serializer.save()
        # If approval_status transitioned to fully-approved via PATCH (not via /approve action)
        if (
            old_approval_status != "fully-approved"
            and work_order.approval_status == "fully-approved"
        ):
            self._run_approval_chain(work_order, self.request.user)
        else:
            self._handle_notification_sent(work_order)
        self._handle_vendor_acceptance(work_order, old_vendor_status)

    # ── central approval chain ───────────────────────────────────────────────
    def _run_approval_chain(self, wo, request_user):
        """
        Full auto-chain triggered when approval_status reaches fully-approved:
          1. status → Approved
          2. approved_by → Employee linked to the user who clicked approve
          3. approved_date → now
          4. notification_sent → True
          5. vendor_status → sent (if not already)
          6. WorkOrderApprovalHistory entry
          7. WorkOrderNotificationLog entry
        """
        update_fields = ["status", "approved_date", "notification_sent"]

        wo.status = "Approved"
        wo.approved_date = timezone.now()
        wo.notification_sent = True

        # Resolve Employee record from the user who performed the approval action
        emp = None
        try:
            from employee.models import Employee
            emp = Employee.objects.filter(user=request_user).first()
            if emp:
                wo.approved_by = emp
                update_fields.append("approved_by")
        except Exception:
            pass

        if wo.vendor_status in ("not-sent", ""):
            wo.vendor_status = "sent"
            update_fields.append("vendor_status")

        wo.save(update_fields=update_fields)

        # Approver display name: prefer employee name, then full name, then username
        approver_name = (
            getattr(emp, "employee_name", None)
            or request_user.get_full_name()
            or request_user.username
        )
        # Designation from employee record (designation is a FK, stringify it)
        designation = ""
        if emp and emp.designation:
            designation = str(emp.designation)

        WorkOrderApprovalHistory.objects.create(
            work_order=wo,
            approver=approver_name,
            role=designation,
            action="Approved",
            date=timezone.now().strftime("%Y-%m-%d %H:%M"),
            comments="Approved and notification sent to vendor.",
        )

        # Create notification log entry
        vendor = self._get_vendor_for_wo(wo)
        WorkOrderNotificationLog.objects.create(
            work_order=wo,
            channel=wo.notification_channel or "email",
            date=timezone.now().strftime("%Y-%m-%d %H:%M"),
            status="sent",
            recipient=self._recipient_str(vendor),
        )

    # ── accepted awards for WO creation ─────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="accepted-awards")
    def accepted_awards(self, request):
        """Return awards with acceptance_status=accepted that can be used to create a WO."""
        from ..serializers.award_serializers import AwardSerializer
        awards = Award.objects.filter(acceptance_status="accepted").select_related(
            "rfq", "rfq__rfq_category", "vendor_profile"
        )
        serializer = AwardSerializer(awards, many=True, context={"request": request})
        return Response(serializer.data)

    # ── summary ──────────────────────────────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = WorkOrder.objects.all()
        data = {
            "total": qs.count(),
            "draft": qs.filter(status="Draft").count(),
            "pending_approval": qs.filter(status="Pending Approval").count(),
            "approved": qs.filter(status="Approved").count(),
            "in_progress": qs.filter(status="In Progress").count(),
            "completed": qs.filter(status="Completed").count(),
            "total_value": qs.aggregate(total=Sum("total_amount"))["total"] or 0,
            "total_paid": qs.aggregate(total=Sum("amount_paid"))["total"] or 0,
        }
        return Response(data)

    # ── approve action ───────────────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        wo = self.get_object()
        if wo.approver_id and wo.approver_id != request.user.id:
            return Response(
                {"detail": "Only the selected approver can approve this work order."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if wo.approval_status == "fully-approved":
            return Response(
                {"detail": "Work order is already approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        wo.approval_status = "fully-approved"
        wo.save(update_fields=["approval_status"])
        self._run_approval_chain(wo, request.user)
        wo.refresh_from_db()
        return Response(WorkOrderSerializer(wo, context={"request": request}).data)

    # ── reject action ────────────────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        wo = self.get_object()
        comments = request.data.get("comments", "")
        wo.approval_status = "rejected"
        wo.status = "Cancelled"
        wo.save(update_fields=["approval_status", "status"])
        approver_name = (
            request.user.get_full_name() or request.user.username
        )
        WorkOrderApprovalHistory.objects.create(
            work_order=wo,
            approver=approver_name,
            role="",
            action="Rejected",
            date=timezone.now().strftime("%Y-%m-%d %H:%M"),
            comments=comments,
        )
        wo.refresh_from_db()
        return Response(WorkOrderSerializer(wo, context={"request": request}).data)

    # ── send to vendor ───────────────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="send-to-vendor")
    def send_to_vendor(self, request, pk=None):
        wo = self.get_object()
        wo.status = "Sent to Vendor"
        wo.vendor_status = "sent"
        wo.notification_sent = True
        wo.save(update_fields=["status", "vendor_status", "notification_sent"])
        self._handle_notification_sent(wo)
        wo.refresh_from_db()
        return Response(WorkOrderSerializer(wo, context={"request": request}).data)


class WorkOrderItemViewSet(viewsets.ModelViewSet):
    queryset = WorkOrderItem.objects.select_related("work_order", "item").all()
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["work_order"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return WorkOrderItemCreateSerializer
        return WorkOrderItemSerializer


class WorkOrderApprovalHistoryViewSet(viewsets.ModelViewSet):
    queryset = WorkOrderApprovalHistory.objects.select_related("work_order").all()
    serializer_class = WorkOrderApprovalHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["work_order"]


class WorkOrderNotificationLogViewSet(viewsets.ModelViewSet):
    queryset = WorkOrderNotificationLog.objects.select_related("work_order").all()
    serializer_class = WorkOrderNotificationLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["work_order"]


class WorkOrderAttachmentViewSet(viewsets.ModelViewSet):
    queryset = WorkOrderAttachment.objects.select_related("work_order").all()
    serializer_class = WorkOrderAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["work_order"]


class VendorAcceptanceViewSet(viewsets.ModelViewSet):
    queryset = VendorAcceptance.objects.select_related("work_order").all()
    serializer_class = VendorAcceptanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["work_order", "status"]

    def _sync_work_order(self, acceptance):
        """Mirror vendor acceptance status back to the WorkOrder and log it."""
        wo = acceptance.work_order
        if acceptance.status == "Accepted":
            new_vs = "accepted"
            log_status = "vendor-accepted"
        elif acceptance.status == "Rejected":
            new_vs = "rejected"
            log_status = "vendor-rejected"
        else:
            return  # Pending / Negotiation – nothing to mirror

        update_fields = ["vendor_status"]
        wo.vendor_status = new_vs
        if new_vs == "accepted" and not wo.vendor_acceptance_date:
            wo.vendor_acceptance_date = timezone.now().date()
            update_fields.append("vendor_acceptance_date")
        wo.save(update_fields=update_fields)

        vendor = None
        if wo.award and getattr(wo.award, "vendor_profile", None):
            vendor = wo.award.vendor_profile
        elif wo.vendor:
            vendor = wo.vendor
        name = getattr(vendor, "name", "") or "" if vendor else ""
        email = getattr(vendor, "email", "") or "" if vendor else ""
        recipient = f"{name} <{email}>" if email else name

        WorkOrderNotificationLog.objects.create(
            work_order=wo,
            channel=wo.notification_channel or "system",
            date=timezone.now().strftime("%Y-%m-%d %H:%M"),
            status=log_status,
            recipient=recipient,
        )

    def perform_create(self, serializer):
        acceptance = serializer.save()
        self._sync_work_order(acceptance)

    def perform_update(self, serializer):
        old_status = serializer.instance.status
        acceptance = serializer.save()
        if acceptance.status != old_status:
            self._sync_work_order(acceptance)
