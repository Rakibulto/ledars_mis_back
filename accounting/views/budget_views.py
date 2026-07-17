from decimal import Decimal

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounting.models import (
    BudgetCategory,
    Budget,
    BudgetLine,
    BudgetTransfer,
    BudgetAmendment,
)
from accounting.serializers.budget_serializers import (
    BudgetAmendmentSerializer,
    BudgetCategorySerializer,
    BudgetDetailSerializer,
    BudgetLineSerializer,
    BudgetListSerializer,
    BudgetTransferSerializer,
)


def _recalculate_budget_totals(budget):
    """Recompute denormalised totals on the Budget header from its lines."""
    lines = budget.lines.all()
    budget.total_planned = sum(line.planned_amount for line in lines)
    budget.total_actual = sum(line.actual_amount for line in lines)
    budget.total_committed = sum(line.committed_amount for line in lines)
    budget.total_encumbrance = sum(line.encumbrance_amount for line in lines)
    budget.total_available = (
        budget.total_planned
        - budget.total_actual
        - budget.total_committed
        - budget.total_encumbrance
    )
    budget.save(
        update_fields=[
            "total_planned",
            "total_actual",
            "total_committed",
            "total_encumbrance",
            "total_available",
        ]
    )


class BudgetCategoryViewSet(viewsets.ModelViewSet):
    queryset = BudgetCategory.objects.all()
    serializer_class = BudgetCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["name", "code"]


class BudgetViewSet(viewsets.ModelViewSet):
    queryset = Budget.objects.select_related(
        "fiscal_year", "department", "project", "cost_center"
    ).prefetch_related("lines__account", "amendments").order_by("-created_at")
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["fiscal_year", "status", "project", "department"]
    search_fields = ["name", "owner", "department_label"]
    ordering_fields = ["created_at", "name", "total_planned"]

    def get_serializer_class(self):
        if self.action == "list":
            return BudgetListSerializer
        return BudgetDetailSerializer

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a budget — moves status to active."""
        budget = self.get_object()
        budget.status = "active"
        budget.save(update_fields=["status"])
        # Approve all pending amendments
        budget.amendments.filter(status="pending_approval").update(
            status="approved", approved_by=request.user.get_full_name() or "Finance Director"
        )
        return Response(BudgetDetailSerializer(budget, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def amend(self, request, pk=None):
        """Submit a budget amendment for a specific line."""
        budget = self.get_object()
        target_line_id = request.data.get("target_line_id")
        amount = Decimal(str(request.data.get("amount", 0)))
        reason = request.data.get("reason", "")
        effective_period = request.data.get("effective_period", "")
        requested_by = request.data.get("requested_by", "Budget Controller")

        if not reason:
            return Response({"detail": "reason is required."}, status=400)
        if amount == 0:
            return Response({"detail": "amount cannot be zero."}, status=400)

        target_line = None
        if target_line_id:
            try:
                target_line = budget.lines.get(id=target_line_id)
            except BudgetLine.DoesNotExist:
                return Response({"detail": "Target line not found."}, status=404)

        amendment = BudgetAmendment.objects.create(
            budget=budget,
            target_line=target_line,
            amount=amount,
            reason=reason,
            effective_period=effective_period,
            requested_by=requested_by,
            status="pending_approval",
        )

        # Apply the delta to the target line's planned amount
        if target_line:
            target_line.planned_amount += amount
            target_line.save()

        budget.status = "pending_approval"
        budget.save(update_fields=["status"])
        _recalculate_budget_totals(budget)

        return Response(BudgetAmendmentSerializer(amendment).data, status=201)

    @action(detail=True, methods=["post"], url_path="add-line")
    def add_line(self, request, pk=None):
        """Add a new budget line to an existing budget."""
        budget = self.get_object()
        account_id = request.data.get("account_id") or request.data.get("accountId")
        planned = Decimal(str(request.data.get("planned", 0)))
        actual = Decimal(str(request.data.get("actual", 0)))
        commitments = Decimal(str(request.data.get("commitments", 0)))
        encumbrance = Decimal(str(request.data.get("encumbrance", 0)))
        owner = request.data.get("owner", "Budget Controller")
        note = request.data.get("note", "")

        if not account_id:
            return Response({"detail": "account_id is required."}, status=400)
        if planned <= 0:
            return Response({"detail": "planned must be greater than zero."}, status=400)

        # Check for duplicate
        if budget.lines.filter(account_id=account_id).exists():
            return Response(
                {"detail": "A line for this account already exists in this budget."},
                status=400,
            )

        line = BudgetLine.objects.create(
            budget=budget,
            account_id=account_id,
            owner=owner,
            planned_amount=planned,
            actual_amount=actual,
            committed_amount=commitments,
            encumbrance_amount=encumbrance,
            notes=note,
        )
        _recalculate_budget_totals(budget)
        return Response(BudgetLineSerializer(line).data, status=201)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        budget = self.get_object()
        if budget.status not in ("draft",):
            return Response({"detail": "Budget is not in draft."}, status=400)
        budget.status = "confirmed"
        budget.save(update_fields=["status"])
        return Response({"detail": "Budget confirmed."})

    @action(detail=True, methods=["post"])
    def validate_budget(self, request, pk=None):
        budget = self.get_object()
        if budget.status != "confirmed":
            return Response({"detail": "Budget must be confirmed first."}, status=400)
        budget.status = "validated"
        budget.save(update_fields=["status"])
        return Response({"detail": "Budget validated."})

    @action(detail=True)
    def utilization(self, request, pk=None):
        """Get budget utilization summary."""
        budget = self.get_object()
        lines = budget.lines.select_related("account", "category").all()
        data = [
            {
                "id": line.id,
                "account": str(line.account) if line.account else None,
                "category": str(line.category) if line.category else None,
                "planned_amount": line.planned_amount,
                "actual_amount": line.actual_amount,
                "committed_amount": line.committed_amount,
                "encumbrance_amount": line.encumbrance_amount,
                "available_amount": line.available_amount,
                "utilization_pct": (
                    round(
                        float(line.actual_amount) / float(line.planned_amount) * 100,
                        1,
                    )
                    if line.planned_amount
                    else 0
                ),
            }
            for line in lines
        ]
        return Response(data)

    @action(detail=True, methods=["post"])
    def check_availability(self, request, pk=None):
        """Check if budget has availability for a given account and amount."""
        budget = self.get_object()
        account_id = request.data.get("account_id")
        amount = request.data.get("amount")
        if not account_id or not amount:
            return Response({"detail": "account_id and amount required."}, status=400)
        try:
            line = budget.lines.get(account_id=account_id)
            available = float(line.available_amount)
            return Response(
                {
                    "available": available >= float(amount),
                    "available_amount": available,
                    "requested": float(amount),
                }
            )
        except BudgetLine.DoesNotExist:
            return Response({"detail": "No budget line for this account."}, status=404)


class BudgetLineViewSet(viewsets.ModelViewSet):
    queryset = BudgetLine.objects.select_related("budget", "account", "category").order_by("budget__id", "id")
    serializer_class = BudgetLineSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["budget"]
    search_fields = ["account__code", "account__name", "owner"]

    def perform_update(self, serializer):
        line = serializer.save()
        _recalculate_budget_totals(line.budget)


class BudgetTransferViewSet(viewsets.ModelViewSet):
    queryset = BudgetTransfer.objects.select_related(
        "from_line", "to_line", "requested_by", "approved_by"
    ).all()
    serializer_class = BudgetTransferSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["status"]
    ordering_fields = ["created_at"]

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        transfer = self.get_object()
        if transfer.status != "pending":
            return Response({"detail": "Not pending."}, status=400)
        transfer.status = "approved"
        transfer.approved_by = request.user
        transfer.save(update_fields=["status", "approved_by"])
        return Response({"detail": "Transfer approved."})


class BudgetAmendmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BudgetAmendment.objects.select_related("budget", "target_line").order_by("-created_at")
    serializer_class = BudgetAmendmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["budget", "status"]
