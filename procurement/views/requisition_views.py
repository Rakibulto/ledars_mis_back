import json
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from paginations import Pagination
from employee.models import Department, Employee
from inventory.models import Item
from inventory.views import CreatedByMixin
from project_managements.models import ProjectManagementProject
from donor.models import Donor
from ..models.account_models import Account
from ..models.budget_models import Budget
from ..models.requisition_models import (
    MaterialRequisition,
    MaterialItem,
    MaterialRequisitionApprovalStep,
    DonorCode,
)
from ..models.settings_models import ApprovalMatrix
from procurement.models.office_models import OfficeManagement
from ..serializers.requisition_serializers import (
    MaterialRequisitionSerializer,
    MaterialItemSerializer,
    DonorCodeSerializer,
)
from ..filters.requisition_filters import MaterialRequisitionFilter


class DonorCodeViewSet(CreatedByMixin, viewsets.ModelViewSet):
    queryset = DonorCode.objects.filter(is_active=True)
    serializer_class = DonorCodeSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # small reference data, no pagination needed

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]


class MaterialRequisitionViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = MaterialRequisitionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    LEVEL_STATUS_MAP = {
        1: "Pending Approval",
        2: "Finance Review",
        3: "Final Approval",
    }
    STATUS_TO_LEVEL = {status: level for level, status in LEVEL_STATUS_MAP.items()}

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = MaterialRequisitionFilter
    search_fields = [
        "requisition_no",
        "status",
        "purpose",
        "contact_person",
        "created_by__username",
    ]
    ordering_fields = [
        "requisition_no",
        "status",
        "priority",
        "total_amount",
        "delivery_date",
        "created_at",
    ]
    ordering = ["-created_at"]

    def _parse_bool_query_param(self, value):
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    # ── Matrix helpers ────────────────────────────────────────────────────────

    def _get_employee_for_user(self, user):
        try:
            return user.employee
        except Exception:
            return None

    def _ensure_matrix_approvers(self, requisition):
        """
        Assign matrix approvers only if the requisition has no approval_steps yet.
        Used for lazy auto-assignment of legacy/existing MRs in workflow statuses.
        Returns True if steps were newly created.
        """
        if not requisition.approval_steps.exists():
            return self._assign_matrix_approvers(requisition)
        return False

    def _assign_matrix_approvers(self, requisition):
        """
        Create MaterialRequisitionApprovalStep records from the ApprovalMatrix
        for 'Material Requisition' module, matching department and amount range.
        Existing steps are cleared first.
        Returns True if any steps were created.
        """
        requisition.approval_steps.all().delete()

        amount = requisition.total_amount or 0
        dept_id = requisition.department_id

        entries = (
            ApprovalMatrix.objects.filter(
                module="Material Requisition",
                is_active=True,
                min_amount__lte=amount,
            )
            .filter(Q(max_amount__isnull=True) | Q(max_amount__gte=amount))
            .filter(Q(department__isnull=True) | Q(department_id=dept_id))
            .prefetch_related("approvers")
            .order_by("approval_level")
        )

        created = 0
        for entry in entries:
            for approver in entry.approvers.all():
                MaterialRequisitionApprovalStep.objects.get_or_create(
                    material_requisition=requisition,
                    approval_level=entry.approval_level,
                    approver=approver,
                    defaults={"approval_mode": entry.approval_mode},
                )
                created += 1

        return created > 0

    def _current_approval_level(self, requisition):
        """Return the integer approval level that maps to the current status."""
        return self.STATUS_TO_LEVEL.get(requisition.status)

    def _get_action_required_queryset(self, queryset, user):
        """Return requisitions where the authenticated user has a Pending step
        at the level matching the current requisition status.
        Falls back to legacy approver1/approver2 if no matrix steps exist."""
        if not user or not user.is_authenticated:
            return queryset.none()

        employee = self._get_employee_for_user(user)

        # Matrix-driven filter: pending step at the right level
        # plus independent approval mode approvers at any pending level.
        matrix_q = Q(pk__in=[])
        approver_filter = Q()
        if employee:
            approver_filter = Q(approval_steps__approver=employee)
        else:
            approver_filter = Q(approval_steps__approver__user=user) | Q(
                approval_steps__approver__employee_name__iexact=user.username
            )

        for level, status in self.LEVEL_STATUS_MAP.items():
            matrix_q |= (
                Q(
                    status=status,
                    approval_steps__approval_level=level,
                    approval_steps__status="Pending",
                )
                & approver_filter
            )

        matrix_q |= (
            Q(
                approval_steps__approval_mode="any_approver",
                approval_steps__status="Pending",
            )
            & approver_filter
        )

        # Legacy fallback for requisitions without matrix steps
        legacy_q = Q(approver1__user=user, status="Pending Approval") | Q(
            approver2__user=user, status="Finance Review"
        )

        return queryset.filter(matrix_q | legacy_q).distinct()

    def get_queryset(self):
        qs = (
            MaterialRequisition.objects.select_related(
                "department",
                "project",
                "donor_code",
                "category",
                "budget_code",
                "account_code",
                "delivery_location",
                "approver1",
                "approver2",
                "created_by",
            )
            .prefetch_related(
                "material_items__item",
                "attachments",
                "status_logs",
                "approval_steps__approver__designation",
                "approval_steps__acted_by",
            )
            .all()
        )

        user = self.request.user

        # workflow_view=true: show ALL requisitions in workflow statuses to any
        # authenticated user. Visibility is unrestricted; action authority is
        # enforced separately at the change-status endpoint (only assigned
        # approvers may approve/reject/return).
        if self._parse_bool_query_param(
            self.request.query_params.get("workflow_view")
        ):
            return qs.filter(
                status__in=[
                    "Pending Approval",
                    "Finance Review",
                    "Final Approval",
                    "Rejected",
                ]
            )

        # action_required=true: show only items where THIS user is an assigned
        # pending approver (personal to-do / notification badge use-case).
        if self._parse_bool_query_param(
            self.request.query_params.get("action_required")
        ):
            return self._get_action_required_queryset(qs, user)

        if user.is_authenticated and not (user.is_staff or user.is_superuser):
            qs = self._get_action_required_queryset(qs, user)
        return qs

    def _build_serializer_data(self, request):
        data = {}

        for key in request.data.keys():
            if key == "attachment_files":
                continue

            value = request.data.get(key)

            if key == "mr_items" and isinstance(value, str):
                try:
                    data[key] = json.loads(value)
                except json.JSONDecodeError:
                    data[key] = value
            else:
                data[key] = value

        if "mr_items" not in data and isinstance(request.data, dict):
            data["mr_items"] = request.data.get("mr_items", [])

        return data

    WORKFLOW_STATUSES = ["Pending Approval", "Finance Review", "Final Approval"]

    @transaction.atomic
    def list(self, request, *args, **kwargs):
        # Lazy auto-assignment: any MR currently in a workflow status but
        # with no approval_steps gets assigned from the Approval Matrix now.
        unassigned_ids = list(
            MaterialRequisition.objects.filter(
                status__in=self.WORKFLOW_STATUSES
            )
            .annotate(step_count=Count("approval_steps"))
            .filter(step_count=0)
            .values_list("id", flat=True)
        )
        if unassigned_ids:
            for mr in MaterialRequisition.objects.filter(id__in=unassigned_ids):
                self._assign_matrix_approvers(mr)
        return super().list(request, *args, **kwargs)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=self._build_serializer_data(request))
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        requisition = serializer.instance
        # Auto-assign matrix approvers for any non-Draft workflow status
        if requisition.status in self.WORKFLOW_STATUSES:
            self._assign_matrix_approvers(requisition)
        headers = self.get_success_headers(serializer.data)
        # Re-serialize to include freshly created approval_steps
        return Response(
            self.get_serializer(requisition).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def _is_approver(self, requisition, user):
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        employee = self._get_employee_for_user(user)
        current_level = self._current_approval_level(requisition)

        # Matrix-driven check
        if employee and current_level is not None:
            if requisition.approval_steps.filter(
                approval_level=current_level,
                approver=employee,
                status="Pending",
            ).exists():
                return True

        # Legacy fallback
        return (requisition.approver1 and requisition.approver1.user_id == user.id) or (
            requisition.approver2 and requisition.approver2.user_id == user.id
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        data = self._build_serializer_data(request)
        previous_status = instance.status
        if "status" in data and not self._is_approver(instance, request.user):
            return Response(
                {
                    "error": "You are not an assigned approver for this requisition at its current stage."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        # Assign matrix approvers if status just moved to Pending Approval
        if (
            "status" in data
            and data["status"] == "Pending Approval"
            and previous_status != "Pending Approval"
        ):
            self._assign_matrix_approvers(serializer.instance)
        return Response(self.get_serializer(serializer.instance).data)

    @action(detail=False, methods=["get"], url_path="form-options")
    def form_options(self, request):
        # Departments
        departments = list(Department.objects.order_by("name").values("id", "name"))

        # Projects (active only)
        projects = list(
            ProjectManagementProject.objects.filter(status="Active")
            .order_by("title")
            .values("id", "code", "title")
        )
        projects = [
            {"id": p["id"], "code": p["code"], "name": p["title"]} for p in projects
        ]

        # Donor codes (from Donor Management)
        donor_codes_qs = list(
            Donor.objects.filter(status="active")
            .order_by("donor_code")
            .values("id", "donor_code", "name")
        )
        donor_codes = [
            {"id": d["id"], "code": d["donor_code"], "name": d["name"]}
            for d in donor_codes_qs
        ]

        # Categories (distinct from inventory items)
        categories = list(
            Item.objects.exclude(category__isnull=True)
            .order_by("category__name")
            .values("category__id", "category__name")
            .distinct()
        )

        budgets = list(
            Budget.objects.filter(is_active=True)
            .order_by("code")
            .values(
                "id",
                "code",
                "name",
                "allocated_amount",
                "spent",
                "balance",
                "fiscal_year",
            )
        )

        # Account codes
        accounts = list(Account.objects.order_by("code").values("id", "code", "name"))

        # Inventory items (for mr_items BOQ)
        items = list(
            Item.objects.select_related("category", "subcategory", "uom", "supplier")
            .order_by("name")
            .values(
                "id",
                "code",
                "name",
                "description",
                "product_type",
                "category__id",
                "category__name",
                "subcategory__id",
                "subcategory__name",
                "uom__id",
                "uom__name",
                "cost",
                "sale_price",
                "on_hand",
                "reserved",
                "available",
                "reorder_level",
                "max_stock",
                "stock_status",
                "status",
                "barcode",
                "specifications",
                "location",
                "supplier__id",
                "supplier__name",
            )
        )

        # Requesting offices and delivery locations both use OfficeManagement now
        requesting_offices = list(
            OfficeManagement.objects.order_by("name").values("id", "name")
        )
        delivery_offices = list(
            OfficeManagement.objects.order_by("district", "name").values(
                "id", "name", "district", "address"
            )
        )

        # Approvers (employees)
        approvers = list(
            Employee.objects.select_related("designation", "user")
            .order_by("employee_name")
            .values(
                "pk",
                "employee_name",
                "designation__name",
            )
        )

        # Current user (pre-fill requester)
        current_user = None
        try:
            emp = request.user.employee
            current_user = {
                "id": request.user.id,
                "username": request.user.username,
                "employee_name": emp.employee_name,
                "designation": emp.designation.name if emp.designation else "",
                "department_id": emp.department_id,
                "department_name": emp.department.name if emp.department else "",
            }
        except Exception:
            current_user = {
                "id": request.user.id,
                "username": request.user.username,
            }

        return Response(
            {
                "departments": departments,
                "projects": projects,
                "donor_codes": donor_codes,
                "categories": [
                    {"id": c["category__id"], "name": c["category__name"]}
                    for c in categories
                ],
                "priorities": [
                    {"value": v, "label": l}
                    for v, l in MaterialRequisition.PRIORITY_CHOICES
                ],
                "statuses": [
                    {"value": v, "label": l}
                    for v, l in MaterialRequisition.STATUS_CHOICES
                ],
                "budgets": budgets,
                "accounts": accounts,
                "approvers": [
                    {
                        "id": a["pk"],
                        "name": a["employee_name"],
                        "designation": a["designation__name"],
                    }
                    for a in approvers
                ],
                "items": [
                    {
                        "id": i["id"],
                        "code": i["code"],
                        "name": i["name"],
                        "description": i["description"],
                        "product_type": i["product_type"],
                        "category_id": i["category__id"],
                        "category_name": i["category__name"],
                        "subcategory_id": i["subcategory__id"],
                        "subcategory_name": i["subcategory__name"],
                        "uom_id": i["uom__id"],
                        "unit": i["uom__name"],
                        "unit_code": i["uom__name"],
                        "unit_price": i["cost"],
                        "sale_price": i["sale_price"],
                        "on_hand": i["on_hand"],
                        "reserved": i["reserved"],
                        "available": i["available"],
                        "reorder_level": i["reorder_level"],
                        "max_stock": i["max_stock"],
                        "stock_status": i["stock_status"],
                        "status": i["status"],
                        "barcode": i["barcode"],
                        "specifications": i["specifications"],
                        "location": i["location"],
                        "supplier_id": i["supplier__id"],
                        "supplier_name": i["supplier__name"],
                    }
                    for i in items
                ],
                "requesting_offices": requesting_offices,
                "delivery_offices": delivery_offices,
                "current_user": current_user,
            }
        )

    @action(detail=True, methods=["patch"], url_path="change-status")
    @transaction.atomic
    def change_status(self, request, pk=None):
        requisition = self.get_object()
        if not self._is_approver(requisition, request.user):
            return Response(
                {
                    "error": "You are not an assigned approver for this requisition at its current stage."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user = request.user
        employee = self._get_employee_for_user(user)
        current_status = requisition.status
        current_level = self._current_approval_level(requisition)

        new_status = request.data.get("status")
        comments = request.data.get("comments")
        action_label = request.data.get("action")
        valid_statuses = [s[0] for s in MaterialRequisition.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {"error": f"Invalid status. Must be one of: {valid_statuses}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_status = current_status

        # ── Ensure matrix steps exist for legacy MRs (assigned on first action) ──
        if requisition.status in self.WORKFLOW_STATUSES:
            self._ensure_matrix_approvers(requisition)
            # Refresh current_level after potential assignment
            current_level = self._current_approval_level(requisition)

        # ── Record the user's matrix approval step ────────────────────────
        step_status_map = {
            "Approved": "Approved",
            "Returned": "Returned",
            "Rejected": "Rejected",
        }
        step_status = step_status_map.get(action_label, "Approved")

        if employee and current_level is not None:
            requisition.approval_steps.filter(
                approval_level=current_level,
                approver=employee,
                status="Pending",
            ).update(
                status=step_status,
                comments=comments,
                acted_at=timezone.now(),
                acted_by=user,
            )

        # ── Determine approval mode for the whole rule ────────────────────
        # Look up the mode from any matrix entry for this requisition's module.
        approval_mode = "all_approvers"  # safe default (Unanimous)
        matrix_entry = ApprovalMatrix.objects.filter(
            module="Material Requisition",
            is_active=True,
        ).first()
        if matrix_entry:
            approval_mode = matrix_entry.approval_mode

        # ── Determine final status ────────────────────────────────────────
        if new_status in ("Rejected", "Draft"):
            # Reject/Return: accept the caller's requested status as-is
            final_status = new_status
        elif new_status == "Approved" or action_label == "Approved":
            if approval_mode == "any_approver":
                # Independent Approval: one approval from any approver at any
                # level immediately finalises the entire requisition.
                final_status = "Approved"
            elif current_level is not None:
                # Unanimous Approval: all approvers at every level must approve
                # sequentially before the requisition can advance.
                pending_at_level = requisition.approval_steps.filter(
                    approval_level=current_level, status="Pending"
                ).count()
                if pending_at_level > 0:
                    # Other approvers at this level are still pending — hold
                    serializer = self.get_serializer(requisition)
                    return Response(serializer.data)

                # All approved at this level; advance to next
                next_level = current_level + 1
                has_next_level = requisition.approval_steps.filter(
                    approval_level=next_level
                ).exists()
                final_status = (
                    self.LEVEL_STATUS_MAP.get(next_level, "Approved")
                    if has_next_level
                    else "Approved"
                )
            else:
                final_status = new_status
        else:
            final_status = new_status

        requisition.status = final_status
        requisition.updated_by = user
        requisition.save(update_fields=["status", "updated_by", "updated_at"])
        requisition.status_logs.create(
            from_status=previous_status,
            to_status=final_status,
            action=action_label or "Status changed",
            comments=comments,
            acted_by=user,
        )

        # Re-assign matrix approvers whenever advancing to Pending Approval.
        if final_status == "Pending Approval":
            self._assign_matrix_approvers(requisition)

        serializer = self.get_serializer(requisition)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        qs = self.get_queryset()
        total = qs.count()
        by_status = qs.values("status").annotate(count=Count("id"))
        status_map = {item["status"]: item["count"] for item in by_status}
        total_amount = qs.aggregate(total=Sum("total_amount"))["total"] or 0
        return Response(
            {
                "total": total,
                "draft": status_map.get("Draft", 0),
                "pending_approval": status_map.get("Pending Approval", 0),
                "finance_review": status_map.get("Finance Review", 0),
                "approved": status_map.get("Approved", 0),
                "rejected": status_map.get("Rejected", 0),
                "converted_to_rfq": status_map.get("Converted to RFQ", 0),
                "total_amount": float(total_amount),
            }
        )


class MaterialItemViewSet(CreatedByMixin, viewsets.ModelViewSet):
    queryset = MaterialItem.objects.select_related("item", "material_requisition").all()
    serializer_class = MaterialItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["item__item_name", "item__item_code"]
    ordering_fields = ["quantity", "created_at"]
    ordering = ["-id"]
