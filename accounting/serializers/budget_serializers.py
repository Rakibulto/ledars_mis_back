from rest_framework import serializers
from accounting.models import BudgetCategory, Budget, BudgetLine, BudgetTransfer, BudgetAmendment


class BudgetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetCategory
        fields = "__all__"


class BudgetAmendmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetAmendment
        fields = [
            "id",
            "budget",
            "target_line",
            "amount",
            "reason",
            "effective_period",
            "requested_by",
            "approved_by",
            "status",
            "created_at",
            "acted_at",
        ]
        extra_kwargs = {"budget": {"required": False}}


class BudgetLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    category_name = serializers.CharField(
        source="category.name", read_only=True, default=""
    )
    utilization_percent = serializers.SerializerMethodField()

    class Meta:
        model = BudgetLine
        fields = [
            "id",
            "budget",
            "account",
            "account_code",
            "account_name",
            "category",
            "category_name",
            "owner",
            "planned_amount",
            "actual_amount",
            "committed_amount",
            "encumbrance_amount",
            "available_amount",
            "notes",
            "utilization_percent",
        ]
        extra_kwargs = {"budget": {"required": False}}

    def get_utilization_percent(self, obj):
        if obj.planned_amount and obj.planned_amount > 0:
            return round((obj.actual_amount / obj.planned_amount) * 100, 2)
        return 0


class BudgetListSerializer(serializers.ModelSerializer):
    lines = BudgetLineSerializer(many=True, read_only=True)
    amendments = BudgetAmendmentSerializer(many=True, read_only=True)
    fiscal_year_name = serializers.CharField(source="fiscal_year.name", read_only=True)
    cost_center_name = serializers.CharField(
        source="cost_center.name", read_only=True, default=""
    )
    cost_center_code = serializers.CharField(
        source="cost_center.code", read_only=True, default=""
    )
    department_name = serializers.SerializerMethodField()
    utilization_percent = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = [
            "id",
            "name",
            "owner",
            "department_label",
            "fiscal_year",
            "fiscal_year_name",
            "cost_center",
            "cost_center_name",
            "cost_center_code",
            "department_name",
            "warning_threshold",
            "critical_threshold",
            "total_planned",
            "total_actual",
            "total_committed",
            "total_encumbrance",
            "total_available",
            "status",
            "utilization_percent",
            "created_at",
            "updated_at",
            "lines",
            "amendments",
        ]

    def get_department_name(self, obj):
        if obj.department:
            return obj.department.name
        return obj.department_label or ""

    def get_utilization_percent(self, obj):
        if obj.total_planned and obj.total_planned > 0:
            return round((obj.total_actual / obj.total_planned) * 100, 2)
        return 0


class BudgetDetailSerializer(serializers.ModelSerializer):
    lines = BudgetLineSerializer(many=True, read_only=True)
    amendments = BudgetAmendmentSerializer(many=True, read_only=True)
    fiscal_year_name = serializers.CharField(source="fiscal_year.name", read_only=True)
    cost_center_name = serializers.CharField(
        source="cost_center.name", read_only=True, default=""
    )
    cost_center_code = serializers.CharField(
        source="cost_center.code", read_only=True, default=""
    )
    department_name = serializers.SerializerMethodField()
    utilization_percent = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = [
            "id",
            "name",
            "owner",
            "department_label",
            "fiscal_year",
            "fiscal_year_name",
            "cost_center",
            "cost_center_name",
            "cost_center_code",
            "department_name",
            "warning_threshold",
            "critical_threshold",
            "total_planned",
            "total_actual",
            "total_committed",
            "total_encumbrance",
            "total_available",
            "status",
            "notes",
            "utilization_percent",
            "created_at",
            "updated_at",
            "lines",
            "amendments",
        ]

    def get_department_name(self, obj):
        if obj.department:
            return obj.department.name
        return obj.department_label or ""

    def get_utilization_percent(self, obj):
        if obj.total_planned and obj.total_planned > 0:
            return round((obj.total_actual / obj.total_planned) * 100, 2)
        return 0


class BudgetTransferSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(
        source="requested_by.get_full_name", read_only=True, default=""
    )
    approved_by_name = serializers.CharField(
        source="approved_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = BudgetTransfer
        fields = "__all__"
