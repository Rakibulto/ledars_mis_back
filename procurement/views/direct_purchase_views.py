from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Sum, Count, Q

from inventory.views import CreatedByMixin
from paginations import Pagination

from employee.models import Department
from project_managements.models import ProjectManagementProject
from ..models.direct_purchase_models import DirectPurchase, DirectPurchaseStatusLog, Shop
from ..models.account_models import Account
from ..models.budget_models import Budget
from ..models.office_models import OfficeManagement
from ..serializers.direct_purchase_serializers import (
    DirectPurchaseSerializer,
    DirectPurchaseItemSerializer,
    ShopSerializer,
)
from ..filters.direct_purchase_filters import DirectPurchaseFilter


class DirectPurchaseViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = DirectPurchaseSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DirectPurchaseFilter
    search_fields = [
        "dp_number",
        "status",
        "purpose",
        "contact_person",
        "shop__name",
        "created_by__username",
    ]
    ordering_fields = [
        "dp_number",
        "status",
        "priority",
        "total_amount",
        "purchase_date",
        "expected_delivery_date",
        "created_at",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            DirectPurchase.objects.select_related(
                "department",
                "project",
                "category",
                "shop",
                "budget_code",
                "account_code",
                "requesting_office",
                "delivery_location",
                "created_by",
            )
            .prefetch_related("dp_items", "status_logs")
            .all()
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data = self._parse_data(request)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            self.get_serializer(serializer.instance).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        prev_status = instance.status
        data = self._parse_data(request)
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        new_status = serializer.instance.status
        if new_status and new_status != prev_status:
            DirectPurchaseStatusLog.objects.create(
                direct_purchase=serializer.instance,
                from_status=prev_status,
                to_status=new_status,
                changed_by=request.user,
            )
        return Response(self.get_serializer(serializer.instance).data)

    def _parse_data(self, request):
        import json
        data = {}
        for key in request.data.keys():
            if key == "attachment":
                continue
            value = request.data.get(key)
            if key == "dp_items_data" and isinstance(value, str):
                try:
                    data[key] = json.loads(value)
                except (ValueError, TypeError):
                    data[key] = value
            else:
                data[key] = value
        if "dp_items_data" not in data:
            data["dp_items_data"] = request.data.get("dp_items_data", [])
        return data

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = DirectPurchase.objects.all()
        total_qs = qs.aggregate(total_amount=Sum("total_amount"))
        counts = qs.values("status").annotate(count=Count("id"))
        status_map = {item["status"]: item["count"] for item in counts}
        return Response(
            {
                "total": qs.count(),
                "draft": status_map.get("Draft", 0),
                "pending_approval": status_map.get("Pending Approval", 0),
                "approved": status_map.get("Approved", 0),
                "rejected": status_map.get("Rejected", 0),
                "converted_to_grn": status_map.get("Converted to GRN", 0),
                "total_amount": total_qs.get("total_amount") or 0,
            }
        )

    @action(detail=False, methods=["get"], url_path="form-options")
    def form_options(self, request):
        departments = list(Department.objects.order_by("name").values("id", "name"))
        projects = [
            {"id": p.id, "code": p.code, "name": p.title}
            for p in ProjectManagementProject.objects.filter(status="Active").order_by("title")
        ]
        budgets = list(
            Budget.objects.filter(is_active=True)
            .order_by("code")
            .values("id", "code", "name", "allocated_amount", "spent", "balance", "fiscal_year")
        )
        accounts = list(Account.objects.order_by("code").values("id", "code", "name"))
        shops = list(Shop.objects.order_by("name").values("id", "name", "phone", "email"))
        offices = list(OfficeManagement.objects.order_by("name").values("id", "name"))

        current_user = None
        if request.user.is_authenticated:
            try:
                emp = request.user.employee
                current_user = {
                    "id": request.user.id,
                    "username": request.user.username,
                    "employee_name": emp.employee_name,
                }
            except Exception:
                current_user = {
                    "id": request.user.id,
                    "username": request.user.username,
                    "employee_name": request.user.username,
                }

        return Response(
            {
                "departments": departments,
                "projects": projects,
                "budgets": budgets,
                "accounts": accounts,
                "shops": shops,
                "offices": offices,
                "current_user": current_user,
                "priorities": [
                    {"value": "Low", "label": "Low"},
                    {"value": "Medium", "label": "Medium"},
                    {"value": "High", "label": "High"},
                    {"value": "Urgent", "label": "Urgent"},
                ],
                "statuses": [
                    {"value": s, "label": s} for s, _ in DirectPurchase.STATUS_CHOICES
                ],
                "payment_terms": [
                    {"value": v, "label": l} for v, l in DirectPurchase.PAYMENT_TERMS_CHOICES
                ],
            }
        )

    @action(detail=True, methods=["post"], url_path="change-status")
    @transaction.atomic
    def change_status(self, request, pk=None):
        instance = self.get_object()
        new_status = request.data.get("status")
        comments = request.data.get("comments", "")

        if not new_status:
            return Response({"error": "status field is required."}, status=status.HTTP_400_BAD_REQUEST)

        allowed = [s for s, _ in DirectPurchase.STATUS_CHOICES]
        if new_status not in allowed:
            return Response(
                {"error": f"Invalid status. Choose from: {', '.join(allowed)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prev_status = instance.status
        instance.status = new_status
        instance.save(update_fields=["status"])
        DirectPurchaseStatusLog.objects.create(
            direct_purchase=instance,
            from_status=prev_status,
            to_status=new_status,
            changed_by=request.user,
            comments=comments,
        )
        return Response(self.get_serializer(instance).data)


class ShopViewSet(viewsets.ModelViewSet):
    """
    List, create, retrieve, update and destroy shops / sellers.
    GET  /api/procurement/shops/?search=<name>  — search by name
    POST /api/procurement/shops/                — create or get-or-create by name
    """

    serializer_class = ShopSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # return all shops for autocomplete

    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "phone", "email"]
    ordering = ["name"]

    def get_queryset(self):
        return Shop.objects.all()

    def create(self, request, *args, **kwargs):
        """Get-or-create by name when the client sends only a name string."""
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"error": "name is required."}, status=status.HTTP_400_BAD_REQUEST)
        shop, created = Shop.objects.get_or_create(
            name__iexact=name,
            defaults={
                "name": name,
                "phone": request.data.get("phone") or "",
                "email": request.data.get("email") or "",
                "address": request.data.get("address") or "",
            },
        )
        serializer = self.get_serializer(shop)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
