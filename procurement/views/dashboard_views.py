from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Avg, F, Q
from django.utils import timezone
from datetime import timedelta
from vendorportal.models.models import VendorProfile

from ..models.models import PurchaseOrder, PurchaseRequisition
from ..models.requisition_models import MaterialRequisition
from ..models.rfq_models import RFQ
from ..models.quotation_models import VendorQuotation
from ..models.comparative_models import ComparativeStatement
from ..models.award_models import Award
from ..models.work_order_models import WorkOrder
from ..models.grn_models import GoodsReceiptNote
from ..models.payment_requisition_models import PaymentRequisition
from ..models.treasury_models import TreasuryProcessing


class ProcurementDashboardAPIView(APIView):
    """Comprehensive procurement dashboard with all module stats."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Gather stats
        requisition_total = MaterialRequisition.objects.count()
        requisition_pending = MaterialRequisition.objects.filter(
            status="Pending Approval"
        ).count()
        requisition_approved = MaterialRequisition.objects.filter(
            status="Approved"
        ).count()

        rfq_total = RFQ.objects.count()
        rfq_open = RFQ.objects.filter(status="Open").count()

        wo_total = WorkOrder.objects.count()
        wo_in_progress = WorkOrder.objects.filter(status="In Progress").count()

        suppliers_total = VendorProfile.objects.count()
        suppliers_active = VendorProfile.objects.filter(status="Active").count()

        payments_total = PaymentRequisition.objects.count()
        payments_pending = PaymentRequisition.objects.filter(
            status="Pending Approval"
        ).count()
        payments_paid = PaymentRequisition.objects.filter(status="Paid").count()
        payments_total_amount = (
            PaymentRequisition.objects.aggregate(total=Sum("total_amount"))["total"]
            or 0
        )

        awards_total = Award.objects.count()

        # Recent activities from latest records across modules
        recent_activities = []
        for mr in MaterialRequisition.objects.order_by("-created_at")[:3]:
            recent_activities.append(
                {
                    "description": f"Material Requisition {mr.requisition_no} - {mr.status}",
                    "action": "requisition",
                    "timestamp": mr.created_at,
                    "created_at": mr.created_at,
                }
            )
        for wo in WorkOrder.objects.order_by("-created_at")[:3]:
            recent_activities.append(
                {
                    "description": f"Work Order {wo.wo_number} - {wo.status}",
                    "action": "work_order",
                    "timestamp": wo.created_at,
                    "created_at": wo.created_at,
                }
            )
        for prf in PaymentRequisition.objects.order_by("-created_at")[:2]:
            recent_activities.append(
                {
                    "description": f"Payment Requisition {prf.prf_number} - {prf.status}",
                    "action": "payment",
                    "timestamp": prf.created_at,
                    "created_at": prf.created_at,
                }
            )
        recent_activities.sort(key=lambda x: x["timestamp"], reverse=True)
        recent_activities = recent_activities[:10]

        data = {
            # Flat keys matching frontend expectations (for overview.jsx)
            "active_requisitions": requisition_total,
            "open_rfqs": rfq_open,
            "pending_approvals": requisition_pending + payments_pending,
            "active_work_orders": wo_in_progress,
            "total_vendors": suppliers_total,
            "total_payments": float(payments_total_amount),
            "recent_activities": recent_activities,
            # Also keep nested stats for dashboard.jsx
            "stats": {
                "active_requisitions": requisition_total,
                "open_rfqs": rfq_open,
                "pending_approvals": requisition_pending + payments_pending,
                "active_work_orders": wo_in_progress,
                "total_vendors": suppliers_total,
                "total_payments": float(payments_total_amount),
                "recent_activities": recent_activities,
            },
            # Detailed nested data
            "requisitions": {
                "total": requisition_total,
                "pending": requisition_pending,
                "approved": requisition_approved,
            },
            "purchase_requisitions": {
                "total": PurchaseRequisition.objects.count(),
                "draft": PurchaseRequisition.objects.filter(status="Draft").count(),
                "submitted": PurchaseRequisition.objects.filter(
                    status="Submitted"
                ).count(),
                "approved": PurchaseRequisition.objects.filter(
                    status="Approved"
                ).count(),
            },
            "rfq": {
                "total": rfq_total,
                "open": rfq_open,
                "closed": RFQ.objects.filter(status="Closed").count(),
                "awarded": RFQ.objects.filter(status="Awarded").count(),
            },
            "quotations": {
                "total": VendorQuotation.objects.count(),
                "submitted": VendorQuotation.objects.filter(status="Submitted").count(),
                "under_review": VendorQuotation.objects.filter(
                    status="Under Review"
                ).count(),
            },
            "comparative_statements": {
                "total": ComparativeStatement.objects.count(),
                "pending_approval": ComparativeStatement.objects.filter(
                    status="Pending Approval"
                ).count(),
                "approved": ComparativeStatement.objects.filter(
                    status="Approved"
                ).count(),
            },
            "awards": {
                "total": awards_total,
                "accepted": Award.objects.filter(status="Accepted").count(),
                "total_value": float(
                    Award.objects.aggregate(total=Sum("total_amount"))["total"] or 0
                ),
            },
            "work_orders": {
                "total": wo_total,
                "in_progress": wo_in_progress,
                "completed": WorkOrder.objects.filter(status="Completed").count(),
                "total_value": float(
                    WorkOrder.objects.aggregate(total=Sum("total_amount"))["total"] or 0
                ),
            },
            "grn": {
                "total": GoodsReceiptNote.objects.count(),
                "pending_verification": GoodsReceiptNote.objects.filter(
                    status="Pending Verification"
                ).count(),
                "verified": GoodsReceiptNote.objects.filter(status="Verified").count(),
            },
            "payments": {
                "total": payments_total,
                "pending": payments_pending,
                "paid": payments_paid,
                "total_amount": float(payments_total_amount),
            },
            "treasury": {
                "total": TreasuryProcessing.objects.count(),
                "pending_review": TreasuryProcessing.objects.filter(
                    status="Pending Review"
                ).count(),
                "processed": TreasuryProcessing.objects.filter(
                    status="Payment Processed"
                ).count(),
            },
            "suppliers": {
                "total": suppliers_total,
                "active": suppliers_active,
                "avg_rating": float(
                    VendorProfile.objects.aggregate(avg=Avg("rating"))["avg"] or 0
                ),
            },
        }
        return Response(data)
