from rest_framework import serializers
from accounting.models import CostCenter, AnalyticPlan, AnalyticAccount, AnalyticLine, AnalyticTag


class CostCenterSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(
        source="parent.name", read_only=True, default=""
    )
    department_name = serializers.CharField(
        source="department.name", read_only=True, default=""
    )
    children = serializers.SerializerMethodField()

    class Meta:
        model = CostCenter
        fields = "__all__"

    def get_children(self, obj):
        children = obj.children.filter(is_active=True)
        return CostCenterSerializer(children, many=True).data


class AnalyticPlanSerializer(serializers.ModelSerializer):
    parent_plan_name = serializers.CharField(
        source="parent_plan.name", read_only=True, default=""
    )
    account_count = serializers.SerializerMethodField()

    class Meta:
        model = AnalyticPlan
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "account_count", "parent_plan_name"]

    def get_account_count(self, obj):
        return obj.analytic_accounts.count()


class AnalyticTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticTag
        fields = "__all__"


class AnalyticAccountSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(
        source="project.name", read_only=True, default=""
    )
    plan_name = serializers.CharField(
        source="plan.name", read_only=True, default=""
    )
    plan_color = serializers.CharField(
        source="plan.color", read_only=True, default="#64748b"
    )

    class Meta:
        model = AnalyticAccount
        fields = "__all__"
        read_only_fields = ["id", "created_at", "plan_name", "plan_color", "project_name"]


class AnalyticLineSerializer(serializers.ModelSerializer):
    analytic_account_name = serializers.CharField(
        source="analytic_account.name", read_only=True
    )
    cost_center_name = serializers.CharField(
        source="cost_center.name", read_only=True, default=""
    )

    class Meta:
        model = AnalyticLine
        fields = "__all__"
