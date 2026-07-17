import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from datetime import timedelta, date

logger = logging.getLogger(__name__)


class CentralDashboardAPIView(APIView):
    """
    Central dashboard API that aggregates data from all modules.
    Returns a single response with KPIs, charts, activities, schedule, and recent records.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)

        data = {
            "kpis": self._get_kpis(today),
            "charts": self._get_charts(today),
            "recent_activities": self._get_recent_activities(),
            "today_schedule": self._get_today_schedule(today),
            "notifications": self._get_notifications(today),
            "recent": self._get_recent_records(),
        }
        return Response(data)

    def _get_kpis(self, today):
        """Gather KPI data from all modules."""
        kpis = {}

        # Projects (from project_managements app - NGO projects)
        try:
            from project_managements.models import ProjectManagementProject
            projects_qs = ProjectManagementProject.objects.all()
            kpis["projects"] = {
                "total": projects_qs.count(),
                "active": projects_qs.filter(status="Active").count(),
                "completed": projects_qs.filter(status="Completed").count(),
                "delayed": projects_qs.filter(status="On Hold").count(),
            }
        except Exception as e:
            logger.warning("CentralDashboard KPI - Projects failed: %s", e)
            kpis["projects"] = {"total": 0, "active": 0, "completed": 0, "delayed": 0}

        # Procurement (all sub-modules)
        try:
            from procurement.models.requisition_models import MaterialRequisition
            from procurement.models.rfq_models import RFQ
            from procurement.models.quotation_models import VendorQuotation
            from procurement.models.comparative_models import ComparativeStatement
            from procurement.models.award_models import Award
            from procurement.models.work_order_models import WorkOrder
            from procurement.models.direct_purchase_models import DirectPurchase
            from procurement.models.grn_models import GoodsReceiptNote

            def _status_counts(qs, status_field="status"):
                return dict(qs.values_list(status_field).annotate(c=Count("id")).values_list("status", "c"))

            mr_qs = MaterialRequisition.objects.all()
            rfq_qs = RFQ.objects.all()
            qt_qs = VendorQuotation.objects.all()
            cs_qs = ComparativeStatement.objects.all()
            aw_qs = Award.objects.all()
            wo_qs = WorkOrder.objects.all()
            dp_qs = DirectPurchase.objects.all()
            grn_qs = GoodsReceiptNote.objects.all()

            kpis["procurement"] = {
                "total": mr_qs.count() + rfq_qs.count() + qt_qs.count() + cs_qs.count() + aw_qs.count() + wo_qs.count() + dp_qs.count() + grn_qs.count(),
                "pending": mr_qs.filter(status="Pending Approval").count(),
                "approved": mr_qs.filter(status="Approved").count(),
                "rejected": mr_qs.filter(status="Rejected").count(),
                "sub_modules": {
                    "material_requisition": {
                        "label": "Material Requisition",
                        "total": mr_qs.count(),
                        "statuses": _status_counts(mr_qs),
                    },
                    "rfq": {
                        "label": "RFQ",
                        "total": rfq_qs.count(),
                        "statuses": _status_counts(rfq_qs),
                    },
                    "quotation": {
                        "label": "Quotation",
                        "total": qt_qs.count(),
                        "statuses": _status_counts(qt_qs),
                    },
                    "comparative_statement": {
                        "label": "Comparative Statement",
                        "total": cs_qs.count(),
                        "statuses": _status_counts(cs_qs),
                    },
                    "award": {
                        "label": "Awards",
                        "total": aw_qs.count(),
                        "statuses": _status_counts(aw_qs),
                    },
                    "work_order": {
                        "label": "Work Orders",
                        "total": wo_qs.count(),
                        "statuses": _status_counts(wo_qs),
                    },
                    "direct_purchase": {
                        "label": "Direct Purchase",
                        "total": dp_qs.count(),
                        "statuses": _status_counts(dp_qs),
                    },
                    "grn": {
                        "label": "GRN",
                        "total": grn_qs.count(),
                        "statuses": _status_counts(grn_qs),
                    },
                },
            }
        except Exception as e:
            logger.warning("CentralDashboard KPI - Procurement failed: %s", e)
            kpis["procurement"] = {"total": 0, "pending": 0, "approved": 0, "rejected": 0, "sub_modules": {}}

        # Employees (HRM)
        try:
            from employee.models import Employee
            from attendance.models import AttendanceData
            employees_qs = Employee.objects.all()
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            present_count = AttendanceData.objects.filter(
                timestamp__range=(today_start, today_end),
                attendance_status="Present"
            ).values("employee").distinct().count()
            on_leave_count = 0
            kpis["employees"] = {
                "total": employees_qs.count(),
                "present": present_count,
                "on_leave": on_leave_count,
            }
        except Exception as e:
            logger.warning("CentralDashboard KPI - Employees failed: %s", e)
            kpis["employees"] = {"total": 0, "present": 0, "on_leave": 0}

        # Beneficiaries
        try:
            from beneficiary.models import Beneficiary
            beneficiaries_qs = Beneficiary.objects.all()
            month_start = today.replace(day=1)
            kpis["beneficiaries"] = {
                "total": beneficiaries_qs.count(),
                "active": beneficiaries_qs.filter(status="Active").count(),
                "new_this_month": beneficiaries_qs.filter(created_at__date__gte=month_start).count(),
            }
        except Exception as e:
            logger.warning("CentralDashboard KPI - Beneficiaries failed: %s", e)
            kpis["beneficiaries"] = {"total": 0, "active": 0, "new_this_month": 0}

        # Inventory
        try:
            from inventory.models import Item
            items_qs = Item.objects.all()
            total_items = items_qs.count()
            low_stock = items_qs.filter(on_hand__lte=F("reorder_level")).count()
            kpis["inventory"] = {
                "total_items": total_items,
                "low_stock": low_stock,
                "out_of_stock": items_qs.filter(on_hand=0).count(),
            }
        except Exception as e:
            logger.warning("CentralDashboard KPI - Inventory failed: %s", e)
            kpis["inventory"] = {"total_items": 0, "low_stock": 0, "out_of_stock": 0}

        # Meetings
        try:
            from meeting_management.models import Meeting
            meetings_today = Meeting.objects.filter(date=today)
            kpis["meetings"] = {
                "today": meetings_today.count(),
                "upcoming": Meeting.objects.filter(date__gt=today, status="scheduled").count(),
                "pending": Meeting.objects.filter(status="scheduled", date__gte=today).count(),
            }
        except Exception as e:
            logger.warning("CentralDashboard KPI - Meetings failed: %s", e)
            kpis["meetings"] = {"today": 0, "upcoming": 0, "pending": 0}

        # Tasks (Todo)
        try:
            from todo.models import Todo
            todos_qs = Todo.objects.all()
            kpis["tasks"] = {
                "today": todos_qs.filter(
                    created_at__date=today
                ).count(),
                "pending": todos_qs.filter(status__in=["pending", "draft"]).count(),
                "completed": todos_qs.filter(status="completed").count(),
            }
        except Exception as e:
            logger.warning("CentralDashboard KPI - Tasks failed: %s", e)
            kpis["tasks"] = {"today": 0, "pending": 0, "completed": 0}

        # CRM Leads
        try:
            from crm.models import Lead
            leads_qs = Lead.objects.all()
            kpis["crm"] = {
                "total_leads": leads_qs.count(),
                "new_leads": leads_qs.filter(status="new").count(),
                "won": leads_qs.filter(status="won").count(),
                "lost": leads_qs.filter(status="lost").count(),
            }
        except Exception as e:
            logger.warning("CentralDashboard KPI - CRM failed: %s", e)
            kpis["crm"] = {"total_leads": 0, "new_leads": 0, "won": 0, "lost": 0}

        # Accounting (simplified - try to get basic totals)
        try:
            from accounting.models.account_models import Account
            revenue_accounts = Account.objects.filter(
                account_type__name__icontains="Revenue"
            )
            expense_accounts = Account.objects.filter(
                account_type__name__icontains="Expense"
            )
            total_revenue = sum(a.balance for a in revenue_accounts if a.balance)
            total_expense = sum(a.balance for a in expense_accounts if a.balance)
            kpis["accounting"] = {
                "revenue": float(total_revenue),
                "expense": float(total_expense),
                "balance": float(total_revenue - total_expense),
            }
        except Exception as e:
            logger.warning("CentralDashboard KPI - Accounting failed: %s", e)
            kpis["accounting"] = {"revenue": 0, "expense": 0, "balance": 0}

        # Movement Management (Travel)
        try:
            from movement_management.models import MovementManagement
            movements_qs = MovementManagement.objects.all()
            kpis["movement_management"] = {
                "total": movements_qs.count(),
                "draft": movements_qs.filter(status="draft").count(),
                "submitted": movements_qs.filter(status="submitted").count(),
                "approved": movements_qs.filter(status="approved").count(),
            }
        except Exception as e:
            logger.warning("CentralDashboard KPI - Movement Management failed: %s", e)
            kpis["movement_management"] = {"total": 0, "draft": 0, "submitted": 0, "approved": 0}

        return kpis

    def _get_charts(self, today):
        """Generate chart data for the dashboard."""
        charts = {}

        # Procurement Status Distribution
        try:
            from procurement.models.requisition_models import MaterialRequisition
            procurement_data = MaterialRequisition.objects.values("status").annotate(
                count=Count("id")
            )
            charts["procurement_status"] = [
                {"name": item["status"] or "Unknown", "value": item["count"]}
                for item in procurement_data
            ]
        except Exception as e:
            logger.warning("CentralDashboard Chart - Procurement Status failed: %s", e)
            charts["procurement_status"] = []

        # Project Progress
        try:
            from project_managements.models import ProjectManagementProject
            project_data = ProjectManagementProject.objects.values("status").annotate(
                count=Count("id")
            )
            charts["project_progress"] = [
                {"name": item["status"] or "Unknown", "value": item["count"]}
                for item in project_data
            ]
        except Exception as e:
            logger.warning("CentralDashboard Chart - Project Progress failed: %s", e)
            charts["project_progress"] = []

        # Revenue vs Expense (last 6 months)
        try:
            from accounting.models.account_models import Account
            from django.db.models.functions import TruncMonth
            months = []
            for i in range(5, -1, -1):
                month_date = today.replace(day=1) - timedelta(days=i * 30)
                month_name = month_date.strftime("%b")
                months.append({
                    "name": month_name,
                    "revenue": 0,
                    "expense": 0,
                })
            charts["revenue_vs_expense"] = months
        except Exception as e:
            logger.warning("CentralDashboard Chart - Revenue vs Expense failed: %s", e)
            charts["revenue_vs_expense"] = []

        # Beneficiary Distribution (by sex)
        try:
            from beneficiary.models import Beneficiary
            sex_data = Beneficiary.objects.values("sex").annotate(
                count=Count("id")
            )
            charts["beneficiary_distribution"] = [
                {"name": item["sex"] or "Unknown", "value": item["count"]}
                for item in sex_data
            ]
        except Exception as e:
            logger.warning("CentralDashboard Chart - Beneficiary Distribution failed: %s", e)
            charts["beneficiary_distribution"] = []

        # Employee Distribution (by department)
        try:
            from employee.models import Employee, Department
            dept_data = Employee.objects.values("department__name").annotate(
                count=Count("id")
            ).exclude(department__name__isnull=True)
            charts["employee_distribution"] = [
                {"name": item["department__name"], "value": item["count"]}
                for item in dept_data
            ]
        except Exception as e:
            logger.warning("CentralDashboard Chart - Employee Distribution failed: %s", e)
            charts["employee_distribution"] = []

        # Lead Status Distribution
        try:
            from crm.models import Lead
            lead_data = Lead.objects.values("status").annotate(
                count=Count("id")
            )
            charts["lead_status"] = [
                {"name": item["status"].replace("_", " ").title(), "value": item["count"]}
                for item in lead_data
            ]
        except Exception as e:
            logger.warning("CentralDashboard Chart - Lead Status failed: %s", e)
            charts["lead_status"] = []

        # Inventory Movement (12 months)
        try:
            from inventory.models import StockMove
            from django.db.models.functions import TruncMonth

            months_data = []
            for i in range(11, -1, -1):
                month_date = today.replace(day=1) - timedelta(days=i * 30)
                month_name = month_date.strftime("%b %Y")
                month_start = month_date.replace(day=1)
                if i > 0:
                    next_month = (month_date + timedelta(days=32)).replace(day=1)
                else:
                    next_month = today + timedelta(days=1)

                inbound = StockMove.objects.filter(
                    date__gte=month_start,
                    date__lt=next_month,
                    move_type__in=["Receipt", "Return"]
                ).aggregate(total=Sum("quantity"))["total"] or 0

                outbound = StockMove.objects.filter(
                    date__gte=month_start,
                    date__lt=next_month,
                    move_type__in=["Delivery", "Scrap"]
                ).aggregate(total=Sum("quantity"))["total"] or 0

                months_data.append({
                    "name": month_name,
                    "inbound": float(inbound),
                    "outbound": float(outbound),
                })
            charts["inventory_movement"] = months_data
        except Exception as e:
            logger.warning("CentralDashboard Chart - Inventory Movement failed: %s", e)
            charts["inventory_movement"] = []

        # Task Completion
        try:
            from todo.models import Todo
            task_data = Todo.objects.values("status").annotate(
                count=Count("id")
            )
            charts["task_completion"] = [
                {"name": item["status"].title(), "value": item["count"]}
                for item in task_data
            ]
        except Exception as e:
            logger.warning("CentralDashboard Chart - Task Completion failed: %s", e)
            charts["task_completion"] = []

        return charts

    def _get_recent_activities(self):
        """Gather recent activities from all modules."""
        activities = []

        # Recent Procurement — all sub-modules unified
        _procurement_activity_limit = 2
        try:
            from procurement.models.requisition_models import MaterialRequisition
            for mr in MaterialRequisition.objects.order_by("-created_at")[:_procurement_activity_limit]:
                activities.append({
                    "id": f"procurement-mr-{mr.id}",
                    "module": "procurement",
                    "sub_module": "Material Requisition",
                    "title": f"Material Requisition {mr.requisition_no}",
                    "description": mr.status,
                    "user": str(mr.created_by) if mr.created_by else None,
                    "time": mr.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Material Requisition failed: %s", e)

        try:
            from procurement.models.rfq_models import RFQ
            for rfq in RFQ.objects.order_by("-created_at")[:_procurement_activity_limit]:
                activities.append({
                    "id": f"procurement-rfq-{rfq.id}",
                    "module": "procurement",
                    "sub_module": "RFQ",
                    "title": f"RFQ {rfq.rfq_number}",
                    "description": rfq.status.replace("_", " ").title(),
                    "user": str(rfq.created_by) if rfq.created_by else None,
                    "time": rfq.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - RFQ failed: %s", e)

        try:
            from procurement.models.quotation_models import VendorQuotation
            for qt in VendorQuotation.objects.order_by("-created_at")[:_procurement_activity_limit]:
                activities.append({
                    "id": f"procurement-qt-{qt.id}",
                    "module": "procurement",
                    "sub_module": "Quotation",
                    "title": f"Quotation {qt.quotation_number}",
                    "description": qt.status.replace("_", " ").title(),
                    "user": str(qt.created_by) if qt.created_by else None,
                    "time": qt.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Quotation failed: %s", e)

        try:
            from procurement.models.comparative_models import ComparativeStatement
            for cs in ComparativeStatement.objects.order_by("-created_at")[:_procurement_activity_limit]:
                activities.append({
                    "id": f"procurement-cs-{cs.id}",
                    "module": "procurement",
                    "sub_module": "Comparative Statement",
                    "title": f"Comparative Statement {cs.cs_number}",
                    "description": cs.status.replace("_", " ").title(),
                    "user": str(cs.created_by) if cs.created_by else None,
                    "time": cs.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Comparative Statement failed: %s", e)

        try:
            from procurement.models.award_models import Award
            for aw in Award.objects.order_by("-created_at")[:_procurement_activity_limit]:
                activities.append({
                    "id": f"procurement-aw-{aw.id}",
                    "module": "procurement",
                    "sub_module": "Award",
                    "title": f"Award {aw.award_number}",
                    "description": aw.status.replace("_", " ").title(),
                    "user": str(aw.awarded_by) if aw.awarded_by else None,
                    "time": aw.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Award failed: %s", e)

        try:
            from procurement.models.work_order_models import WorkOrder
            for wo in WorkOrder.objects.order_by("-created_at")[:_procurement_activity_limit]:
                activities.append({
                    "id": f"procurement-wo-{wo.id}",
                    "module": "procurement",
                    "sub_module": "Work Order",
                    "title": f"Work Order {wo.wo_number}",
                    "description": wo.status.replace("_", " ").title(),
                    "user": str(wo.created_by) if wo.created_by else None,
                    "time": wo.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Work Order failed: %s", e)

        try:
            from procurement.models.direct_purchase_models import DirectPurchase
            for dp in DirectPurchase.objects.order_by("-created_at")[:_procurement_activity_limit]:
                activities.append({
                    "id": f"procurement-dp-{dp.id}",
                    "module": "procurement",
                    "sub_module": "Direct Purchase",
                    "title": f"Direct Purchase {dp.dp_number}",
                    "description": dp.status.replace("_", " ").title(),
                    "user": str(dp.created_by) if dp.created_by else None,
                    "time": dp.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Direct Purchase failed: %s", e)

        try:
            from procurement.models.grn_models import GoodsReceiptNote
            for grn in GoodsReceiptNote.objects.order_by("-created_at")[:_procurement_activity_limit]:
                activities.append({
                    "id": f"procurement-grn-{grn.id}",
                    "module": "procurement",
                    "sub_module": "GRN",
                    "title": f"GRN {grn.grn_number}",
                    "description": grn.status.replace("_", " ").title(),
                    "user": str(grn.created_by) if grn.created_by else None,
                    "time": grn.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - GRN failed: %s", e)

        # Recent Projects
        try:
            from project_managements.models import ProjectManagementProject
            for proj in ProjectManagementProject.objects.order_by("-created_at")[:3]:
                activities.append({
                    "id": f"project-{proj.id}",
                    "module": "projects",
                    "title": f"Project: {proj.title}",
                    "description": proj.status,
                    "user": str(proj.created_by) if proj.created_by else None,
                    "time": proj.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Projects failed: %s", e)

        # Recent Beneficiaries
        try:
            from beneficiary.models import Beneficiary
            for ben in Beneficiary.objects.order_by("-created_at")[:3]:
                activities.append({
                    "id": f"beneficiary-{ben.id}",
                    "module": "beneficiaries",
                    "title": f"Beneficiary: {ben.name or ben.ben_code or 'Unknown'}",
                    "description": ben.status,
                    "user": str(ben.created_by) if ben.created_by else None,
                    "time": ben.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Beneficiaries failed: %s", e)

        # Recent Leads
        try:
            from crm.models import Lead
            for lead in Lead.objects.order_by("-created_at")[:3]:
                activities.append({
                    "id": f"lead-{lead.id}",
                    "module": "crm",
                    "title": f"Lead: {lead.name}",
                    "description": lead.status.replace("_", " ").title(),
                    "user": str(lead.created_by) if lead.created_by else None,
                    "time": lead.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Leads failed: %s", e)

        # Recent Tasks
        try:
            from todo.models import Todo
            for todo_item in Todo.objects.order_by("-created_at")[:3]:
                activities.append({
                    "id": f"todo-{todo_item.id}",
                    "module": "todo",
                    "title": f"Task: {todo_item.todo_title}",
                    "description": todo_item.status.title(),
                    "user": todo_item.creator_name or (str(todo_item.creator) if todo_item.creator else None),
                    "time": todo_item.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Tasks failed: %s", e)

        # Recent Meetings
        try:
            from meeting_management.models import Meeting
            for meeting in Meeting.objects.order_by("-created_at")[:3]:
                activities.append({
                    "id": f"meeting-{meeting.id}",
                    "module": "meetings",
                    "title": f"Meeting: {meeting.title}",
                    "description": meeting.status.replace("_", " ").title(),
                    "user": str(meeting.created_by) if meeting.created_by else None,
                    "time": meeting.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Meetings failed: %s", e)

        # Recent Movement Management (Travel)
        try:
            from movement_management.models import MovementManagement
            for movement in MovementManagement.objects.order_by("-created_at")[:3]:
                activities.append({
                    "id": f"movement-{movement.id}",
                    "module": "movement_management",
                    "title": f"Movement: {movement.name}",
                    "description": f"{movement.project_name} - {movement.status.title()}",
                    "user": str(movement.created_by) if movement.created_by else None,
                    "time": movement.created_at,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Movements failed: %s", e)

        # Recent Inventory Stock Moves
        try:
            from inventory.models import StockMove
            for move in StockMove.objects.select_related("product").order_by("-date")[:3]:
                activities.append({
                    "id": f"stockmove-{move.id}",
                    "module": "inventory",
                    "title": f"Stock {move.move_type}: {move.product.name if move.product else 'Unknown'}",
                    "description": f"Qty: {move.quantity} - {move.source_location or ''} to {move.destination_location or ''}",
                    "user": move.done_by.username if move.done_by else None,
                    "time": move.date,
                })
        except Exception as e:
            logger.warning("CentralDashboard Activity - Stock Moves failed: %s", e)

        # Sort by time descending and limit
        activities.sort(key=lambda x: x.get("time") or "", reverse=True)
        return activities[:15]

    def _get_today_schedule(self, today):
        """Get today's meetings and tasks."""
        schedule = []

        # Today's Meetings
        try:
            from meeting_management.models import Meeting
            for meeting in Meeting.objects.filter(date=today).order_by("start_time"):
                schedule.append({
                    "id": f"meeting-{meeting.id}",
                    "type": "meeting",
                    "title": meeting.title,
                    "time": f"{today.isoformat()}T{meeting.start_time.isoformat()}",
                    "location": meeting.location or "",
                })
        except Exception as e:
            logger.warning("CentralDashboard Schedule - Meetings failed: %s", e)

        # Today's Tasks (created today)
        try:
            from todo.models import Todo
            for todo_item in Todo.objects.filter(
                created_at__date=today
            ).exclude(status="completed"):
                schedule.append({
                    "id": f"todo-{todo_item.id}",
                    "type": "task",
                    "title": todo_item.todo_title,
                    "time": todo_item.created_at.isoformat() if todo_item.created_at else "",
                    "location": "",
                })
        except Exception as e:
            logger.warning("CentralDashboard Schedule - Tasks failed: %s", e)

        # Sort by time
        schedule.sort(key=lambda x: x.get("time") or "")
        return schedule

    def _get_notifications(self, today):
        """Generate notifications/alerts."""
        notifications = []

        # Low Stock Warning
        try:
            from inventory.models import Item
            low_stock_items = Item.objects.filter(
                on_hand__lte=F("reorder_level")
            )[:5]
            for item in low_stock_items:
                notifications.append({
                    "id": f"low-stock-{item.id}",
                    "type": "warning",
                    "title": "Low Stock Warning",
                    "message": f"{item.name} is running low on stock",
                })
        except Exception as e:
            logger.warning("CentralDashboard Notifications - Low Stock failed: %s", e)

        # Pending Procurement Approvals
        try:
            from procurement.models.requisition_models import MaterialRequisition
            pending_count = MaterialRequisition.objects.filter(
                status="Pending Approval"
            ).count()
            if pending_count > 0:
                notifications.append({
                    "id": "pending-procurement",
                    "type": "info",
                    "title": "Pending Procurement Approvals",
                    "message": f"{pending_count} procurement request(s) awaiting approval",
                })
        except Exception as e:
            logger.warning("CentralDashboard Notifications - Procurement failed: %s", e)

        # Overdue Tasks
        try:
            from todo.models import Todo
            overdue_count = Todo.objects.filter(
                status__in=["pending", "draft"],
                created_at__date__lt=today
            ).count()
            if overdue_count > 0:
                notifications.append({
                    "id": "overdue-tasks",
                    "type": "danger",
                    "title": "Overdue Tasks",
                    "message": f"{overdue_count} task(s) are overdue",
                })
        except Exception as e:
            logger.warning("CentralDashboard Notifications - Tasks failed: %s", e)

        # Pending Leave Requests
        try:
            from leave.models import LeaveRequest
            pending_leaves = LeaveRequest.objects.filter(
                status="pending"
            ).count()
            if pending_leaves > 0:
                notifications.append({
                    "id": "pending-leaves",
                    "type": "info",
                    "title": "Pending Leave Requests",
                    "message": f"{pending_leaves} leave request(s) pending approval",
                })
        except Exception as e:
            logger.warning("CentralDashboard Notifications - Leave failed: %s", e)

        return notifications

    def _get_recent_records(self):
        """Get recent records from each module for the recent lists section."""
        recent = {}

        # Recent Projects
        try:
            from project_managements.models import ProjectManagementProject
            projects = ProjectManagementProject.objects.order_by("-created_at")[:5]
            recent["projects"] = [
                {
                    "id": p.id,
                    "name": p.title,
                    "status": p.status,
                }
                for p in projects
            ]
        except Exception as e:
            logger.warning("CentralDashboard Recent - Projects failed: %s", e)
            recent["projects"] = []

        # Recent Meetings
        try:
            from meeting_management.models import Meeting
            meetings = Meeting.objects.order_by("-created_at")[:5]
            recent["meetings"] = [
                {
                    "id": m.id,
                    "title": m.title,
                    "date": m.date.isoformat() if m.date else "",
                    "status": m.status.replace("_", " ").title(),
                }
                for m in meetings
            ]
        except Exception as e:
            logger.warning("CentralDashboard Recent - Meetings failed: %s", e)
            recent["meetings"] = []

        # Recent Procurement
        try:
            from procurement.models.requisition_models import MaterialRequisition
            procurements = MaterialRequisition.objects.order_by("-created_at")[:5]
            recent["procurement"] = [
                {
                    "id": p.id,
                    "reference": p.requisition_no,
                    "type": "Material Requisition",
                    "status": p.status,
                }
                for p in procurements
            ]
        except Exception as e:
            logger.warning("CentralDashboard Recent - Procurement failed: %s", e)
            recent["procurement"] = []

        # Recent Tasks
        try:
            from todo.models import Todo
            tasks = Todo.objects.order_by("-created_at")[:5]
            recent["tasks"] = [
                {
                    "id": t.id,
                    "title": t.todo_title,
                    "due_date": t.created_at.date().isoformat() if t.created_at else "",
                    "status": t.status.title(),
                }
                for t in tasks
            ]
        except Exception as e:
            logger.warning("CentralDashboard Recent - Tasks failed: %s", e)
            recent["tasks"] = []

        # Recent Leads
        try:
            from crm.models import Lead
            leads = Lead.objects.order_by("-created_at")[:5]
            recent["leads"] = [
                {
                    "id": l.id,
                    "name": l.name,
                    "source": l.source or "Unknown",
                    "status": l.status.replace("_", " ").title(),
                }
                for l in leads
            ]
        except Exception as e:
            logger.warning("CentralDashboard Recent - Leads failed: %s", e)
            recent["leads"] = []

        # Recent Beneficiaries
        try:
            from beneficiary.models import Beneficiary
            beneficiaries = Beneficiary.objects.order_by("-created_at")[:5]
            recent["beneficiaries"] = [
                {
                    "id": b.id,
                    "name": b.name or b.ben_code or "Unknown",
                    "status": b.status,
                    "date": b.created_at.date().isoformat() if b.created_at else "",
                }
                for b in beneficiaries
            ]
        except Exception as e:
            logger.warning("CentralDashboard Recent - Beneficiaries failed: %s", e)
            recent["beneficiaries"] = []

        # Recent Movement Management (Travel)
        try:
            from movement_management.models import MovementManagement
            movements = MovementManagement.objects.order_by("-created_at")[:5]
            recent["movements"] = [
                {
                    "id": m.id,
                    "name": m.name,
                    "project": m.project_name,
                    "total": float(m.grand_total),
                    "status": m.status.title(),
                }
                for m in movements
            ]
        except Exception as e:
            logger.warning("CentralDashboard Recent - Movements failed: %s", e)
            recent["movements"] = []

        # Recent Inventory Stock Moves
        try:
            from inventory.models import StockMove
            stock_moves = StockMove.objects.select_related("product").order_by("-date")[:5]
            recent["stock_moves"] = [
                {
                    "id": sm.id,
                    "product": sm.product.name if sm.product else "Unknown",
                    "move_type": sm.move_type,
                    "quantity": float(sm.quantity),
                    "date": sm.date.date().isoformat() if sm.date else "",
                }
                for sm in stock_moves
            ]
        except Exception as e:
            logger.warning("CentralDashboard Recent - Stock Moves failed: %s", e)
            recent["stock_moves"] = []

        return recent
