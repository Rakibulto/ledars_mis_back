# procurement_dashboard/serializers/budget_serializer.py
from rest_framework import serializers
from ..models.budget_models import Budget


class BudgetSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = Budget
        fields = [
            'id', 'code', 'name', 'department',
            'allocated_amount', 'spent', 'balance',
            'fiscal_year', 'is_active',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'code', 'balance', 'created_by', 'created_by_name', 'created_at', 'updated_at']


