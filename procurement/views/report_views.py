from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Avg, F, Q
from django.db.models.functions import TruncMonth
from vendorportal.models.models import VendorProfile

from ..models.models import PurchaseOrder, PurchaseRequisition
from ..models.requisition_models import MaterialRequisition
from ..models.rfq_models import RFQ
from ..models.award_models import Award
from ..models.work_order_models import WorkOrder
from ..models.grn_models import GoodsReceiptNote
from ..models.payment_requisition_models import PaymentRequisition
from ..models.vendor_models import VendorPerformance
from ..models.budget_models import Budget


class RequisitionReportAPIView(APIView):
    """Requisition report with status breakdown and trends."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = MaterialRequisition.objects.all()
        status_breakdown = qs.values("status").annotate(count=Count("id"))
        priority_breakdown = qs.values("priority").annotate(count=Count("id"))
        monthly_trend = (
            qs.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        return Response(
            {
                "total": qs.count(),
                "status_breakdown": list(status_breakdown),
                "priority_breakdown": list(priority_breakdown),
                "monthly_trend": list(monthly_trend),
            }
        )


class RFQReportAPIView(APIView):
    """RFQ report with status and response analysis."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = RFQ.objects.all()
        status_breakdown = qs.values("status").annotate(count=Count("id"))
        agg = qs.aggregate(
            total_value=Sum("total_estimated_value"),
            avg_suppliers=Avg("vendors_count"),
            avg_responses=Avg("responses_received"),
        )
        return Response(
            {
                "total": qs.count(),
                "status_breakdown": list(status_breakdown),
                **agg,
            }
        )


class VendorParticipationReportAPIView(APIView):
    """Vendor participation across RFQs and quotations."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from ..models.quotation_models import VendorQuotation

        vendor_stats = (
            VendorQuotation.objects.values("vendor__name", "vendor__code")
            .annotate(
                quotations_submitted=Count("id"),
                total_amount=Sum("grand_total"),
            )
            .order_by("-quotations_submitted")
        )

        return Response(
            {
                "total_vendors": VendorProfile.objects.count(),
                "active_vendors": VendorProfile.objects.filter(status="Active").count(),
                "vendor_participation": list(vendor_stats[:50]),
            }
        )


class VendorAwardReportAPIView(APIView):
    """Report on awards given to vendors."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor_awards = (
            Award.objects.values("vendor_profile__name", "vendor_profile__code")
            .annotate(
                awards_count=Count("id"),
                total_value=Sum("total_amount"),
            )
            .order_by("-total_value")
        )

        return Response(
            {
                "total_awards": Award.objects.count(),
                "total_value": Award.objects.aggregate(total=Sum("total_amount"))[
                    "total"
                ]
                or 0,
                "vendor_awards": list(vendor_awards[:50]),
            }
        )


class WorkOrderReportAPIView(APIView):
    """Work order status and value report."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = WorkOrder.objects.all()
        status_breakdown = qs.values("status").annotate(
            count=Count("id"), total_value=Sum("total_amount")
        )
        return Response(
            {
                "total": qs.count(),
                "total_value": qs.aggregate(total=Sum("total_amount"))["total"] or 0,
                "status_breakdown": list(status_breakdown),
            }
        )


class InventoryReceivedReportAPIView(APIView):
    """Report on goods received via GRN."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = GoodsReceiptNote.objects.all()
        status_breakdown = qs.values("status").annotate(count=Count("id"))
        monthly_trend = (
            qs.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(
                count=Count("id"),
                total_value=Sum("total_received_value"),
            )
            .order_by("month")
        )

        return Response(
            {
                "total_grns": qs.count(),
                "total_value": qs.aggregate(total=Sum("total_received_value"))["total"]
                or 0,
                "status_breakdown": list(status_breakdown),
                "monthly_trend": list(monthly_trend),
            }
        )


class PaymentStatusReportAPIView(APIView):
    """Payment requisition status and amount report."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = PaymentRequisition.objects.all()
        status_breakdown = qs.values("status").annotate(
            count=Count("id"), total_amount=Sum("total_amount")
        )
        return Response(
            {
                "total": qs.count(),
                "total_amount": qs.aggregate(total=Sum("total_amount"))["total"] or 0,
                "status_breakdown": list(status_breakdown),
            }
        )


class BudgetUtilizationReportAPIView(APIView):
    """Budget utilization and spending report."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        budgets = Budget.objects.all()
        budget_data = []
        for budget in budgets:
            utilized = (
                PaymentRequisition.objects.filter(
                    budget_code=budget, status="Paid"
                ).aggregate(total=Sum("total_amount"))["total"]
                or 0
            )
            budget_data.append(
                {
                    "code": budget.code,
                    "name": budget.name,
                    "allocated": budget.allocated_amount,
                    "utilized": utilized,
                    "remaining": budget.allocated_amount - utilized,
                    "utilization_pct": round(
                        (
                            (utilized / budget.allocated_amount * 100)
                            if budget.allocated_amount
                            else 0
                        ),
                        1,
                    ),
                }
            )

        total_allocated = budgets.aggregate(total=Sum("allocated_amount"))["total"] or 0

        return Response(
            {
                "total_budgets": budgets.count(),
                "total_allocated": total_allocated,
                "budgets": budget_data,
            }
        )
