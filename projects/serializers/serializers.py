from rest_framework import serializers
from donor.models import Donor
from procurement.models.budget_models import Budget
from projects.models import Project, ProjectActivity


class ProjectActivitySerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ProjectActivity
        fields = "__all__"
        read_only_fields = ["created_by", "created_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None


class ProjectSerializer(serializers.ModelSerializer):
    activities = ProjectActivitySerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()
    donor = serializers.SerializerMethodField()
    donor_id = serializers.PrimaryKeyRelatedField(
        queryset=Donor.objects.all(),
        source="donor",
        write_only=True,
        required=False,
        allow_null=True,
    )
    budget = serializers.SerializerMethodField()
    budget_id = serializers.PrimaryKeyRelatedField(
        queryset=Budget.objects.all(),
        source="budget",
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Project
        fields = [
            "id",
            "activities",
            "created_by_name",
            "code",
            "name",
            "donor",
            "donor_id",
            "budget",
            "budget_id",
            "start_date",
            "end_date",
            "status",
            "manager",
            "location",
            "objectives",
            "activity_list",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["code", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None

    def get_donor(self, obj):
        return obj.donor.name if obj.donor else None

    def get_budget(self, obj):
        return obj.budget.code if obj.budget else None


class SimpleProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "code", "name"]

