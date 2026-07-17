# procurement_dashboard/views/budget_view.py
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from ..models.budget_models import Budget
from ..serializers.budget_serializers import BudgetSerializer
from paginations import Pagination


class BudgetViewSet(viewsets.ModelViewSet):
    """
    API endpoint for CRUD operations on Budget.
    'balance' is auto-calculated as allocated_amount - spent on every save.
    """

    queryset = Budget.objects.all().order_by("-created_at")
    serializer_class = BudgetSerializer
    pagination_class = Pagination
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'name', 'department']
    ordering_fields = ['created_at', 'allocated_amount', 'balance']

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()
