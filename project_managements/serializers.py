import decimal
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from donor.models import Donor

from .models import (
    Advance,
    ProjectManagementExpense,
    ProjectManagementExpenseItem,
    ProjectManagementPlanAttachment,
    ProjectManagementPlanSubPlan,
    ProjectManagementPlanWorkItem,
    ProjectManagementProject,
    ProjectManagementProjectMaterial,
    ProjectManagementProjectPlan,
    ProjectManagementSubPlanUnitPeriod,
    ProjectManagementUnit,
)
from .services.plan_tables_service import sync_project_procurement_budget

User = get_user_model()


def serialize_assigned_users(users):
    result = []
    for user in users:
        designation = ""
        employee = getattr(user, "employee", None)
        if employee is not None:
            designation_obj = getattr(employee, "designation", None)
            if designation_obj is not None:
                designation = getattr(designation_obj, "name", None) or str(designation_obj)

        result.append(
            {
                "id": user.id,
                "username": user.username,
                "designation": designation or "",
            }
        )
    return result


class ProjectManagementUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectManagementUnit
        fields = [
            "id",
            "name",
            "description",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]


class ProjectOverviewSubPlanSerializer(serializers.ModelSerializer):
    assigned_users = serializers.SerializerMethodField()
    deliverable_date = serializers.DateField(source="end_date", read_only=True)
    row_status = serializers.SerializerMethodField()

    class Meta:
        model = ProjectManagementPlanSubPlan
        fields = [
            "id",
            "serial_code",
            "title",
            "unit_type",
            "unit_no",
            "start_date",
            "end_date",
            "deliverable_date",
            "assigned_users",
            "row_status",
            "sort_order",
        ]

    def get_assigned_users(self, obj):
        return serialize_assigned_users(obj.assigned_users.all().order_by("username"))

    def get_row_status(self, obj):
        from django.utils import timezone

        today = timezone.localdate()
        parent_status = getattr(obj.plan, "status", None)
        if parent_status == "Completed":
            return "completed"
        deliverable = obj.end_date
        if deliverable and deliverable < today:
            return "overdue"
        return "pending"


class ProjectOverviewPlanSerializer(serializers.ModelSerializer):
    sub_plans = ProjectOverviewSubPlanSerializer(many=True, read_only=True)
    assigned_users = serializers.SerializerMethodField()
    work_items = serializers.SerializerMethodField()
    deliverable_date = serializers.DateField(source="end_date", read_only=True)
    row_status = serializers.SerializerMethodField()

    class Meta:
        model = ProjectManagementProjectPlan
        fields = [
            "id",
            "serial_no",
            "serial_code",
            "title",
            "description",
            "duration_days",
            "status",
            "start_date",
            "end_date",
            "deliverable_date",
            "row_status",
            "assigned_users",
            "work_items",
            "sub_plans",
        ]

    def get_assigned_users(self, obj):
        return serialize_assigned_users(obj.assigned_users.all().order_by("username"))

    def get_work_items(self, obj):
        # Local import avoids circular ordering with WorkItem serializer definition
        return ProjectManagementPlanWorkItemSerializer(
            obj.work_items.all().order_by("sort_order", "id"),
            many=True,
        ).data

    def get_row_status(self, obj):
        from django.utils import timezone

        today = timezone.localdate()
        if obj.status == "Completed":
            return "completed"
        deliverable = obj.end_date
        if deliverable and deliverable < today:
            return "overdue"
        return "pending"


class ProjectOverviewSerializer(serializers.ModelSerializer):
    plans = ProjectOverviewPlanSerializer(many=True, read_only=True)
    assigned_users = serializers.SerializerMethodField()


    class Meta:
        model = ProjectManagementProject
        fields = [
            "id",
            "code",
            "title",
            "short_name",
            "status",
            "start_date",
            "end_date",
            "assigned_users",
            "plans",
        ]

    def get_assigned_users(self, obj):
        return serialize_assigned_users(obj.assigned_users.all().order_by("username"))


class ProjectManagementPlanWorkItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    assigned_to = serializers.SerializerMethodField()
    approved_by = serializers.SerializerMethodField()
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="assigned_to",
        write_only=True,
        required=False,
        allow_null=True,
    )
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = ProjectManagementPlanWorkItem
        fields = [
            "id",
            "title",
            "state",
            "notes",
            "issues",
            "sort_order",
            "scheduled_date",
            "scheduled_end_date",
            "approval_status",
            "approved_by",
            "approved_at",
            "assigned_to",
            "assigned_to_id",
            "attachments",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "approval_status",
            "approved_by",
            "approved_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        plan = self.context.get("plan") or getattr(self.instance, "plan", None)
        scheduled_date = attrs.get(
            "scheduled_date", getattr(self.instance, "scheduled_date", None)
        )
        scheduled_end_date = attrs.get(
            "scheduled_end_date", getattr(self.instance, "scheduled_end_date", None)
        )

        if (
            scheduled_date
            and scheduled_end_date
            and scheduled_end_date < scheduled_date
        ):
            raise serializers.ValidationError(
                {"scheduled_end_date": "End date cannot be before start date."}
            )

        if plan:
            if plan.start_date and scheduled_date and scheduled_date < plan.start_date:
                raise serializers.ValidationError(
                    {
                        "scheduled_date": "Task start date must stay within the parent task date range."
                    }
                )

            if plan.end_date and scheduled_date and scheduled_date > plan.end_date:
                raise serializers.ValidationError(
                    {
                        "scheduled_date": "Task start date must stay within the parent task date range."
                    }
                )

            if (
                plan.start_date
                and scheduled_end_date
                and scheduled_end_date < plan.start_date
            ):
                raise serializers.ValidationError(
                    {
                        "scheduled_end_date": "Task end date must stay within the parent task date range."
                    }
                )

            if (
                plan.end_date
                and scheduled_end_date
                and scheduled_end_date > plan.end_date
            ):
                raise serializers.ValidationError(
                    {
                        "scheduled_end_date": "Task end date must stay within the parent task date range."
                    }
                )

        return attrs

    def get_assigned_to(self, obj):
        if not obj.assigned_to:
            return None
        return {"id": obj.assigned_to.id, "username": obj.assigned_to.username}

    def get_approved_by(self, obj):
        if not obj.approved_by:
            return None
        return {"id": obj.approved_by.id, "username": obj.approved_by.username}

    def get_attachments(self, obj):
        return ProjectManagementPlanAttachmentSerializer(
            obj.attachments.all(),
            many=True,
            context=self.context,
        ).data


class ProjectManagementPlanAttachmentSerializer(serializers.ModelSerializer):
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=ProjectManagementProjectPlan.objects.all(),
        source="plan",
        write_only=True,
        required=False,
    )
    work_item_id = serializers.PrimaryKeyRelatedField(
        queryset=ProjectManagementPlanWorkItem.objects.all(),
        source="work_item",
        write_only=True,
        required=False,
        allow_null=True,
    )
    uploaded_by = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    file_name = serializers.CharField(source="display_name", read_only=True)
    file_size = serializers.SerializerMethodField()
    work_item = serializers.SerializerMethodField()

    class Meta:
        model = ProjectManagementPlanAttachment
        fields = [
            "id",
            "plan",
            "plan_id",
            "work_item",
            "work_item_id",
            "file",
            "file_url",
            "file_name",
            "file_size",
            "original_name",
            "uploaded_by",
            "created_at",
        ]
        read_only_fields = [
            "plan",
            "work_item",
            "file_url",
            "file_name",
            "file_size",
            "uploaded_by",
            "created_at",
        ]

    def get_uploaded_by(self, obj):
        if not obj.uploaded_by:
            return None
        return {"id": obj.uploaded_by.id, "username": obj.uploaded_by.username}

    def get_file_url(self, obj):
        if not obj.file:
            return ""
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url

    def get_file_size(self, obj):
        if not obj.file:
            return 0
        try:
            return getattr(obj.file, "size", 0) or 0
        except (FileNotFoundError, OSError):
            return 0

    def get_work_item(self, obj):
        if not obj.work_item:
            return None
        return {
            "id": obj.work_item.id,
            "title": obj.work_item.title,
        }

    def validate(self, attrs):
        plan = attrs.get("plan") or getattr(self.instance, "plan", None)
        work_item = attrs.get("work_item") or getattr(self.instance, "work_item", None)
        uploaded_file = attrs.get("file")

        if work_item:
            if plan and work_item.plan_id != plan.id:
                raise serializers.ValidationError(
                    {
                        "work_item_id": "Selected execution task does not belong to this plan."
                    }
                )
            attrs["plan"] = work_item.plan
            plan = work_item.plan

        if not self.instance and not plan:
            raise serializers.ValidationError({"plan_id": "Plan is required."})

        if uploaded_file and uploaded_file.size > 15 * 1024 * 1024:
            raise serializers.ValidationError(
                {"file": "Each file must be 15 MB or smaller."}
            )

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data.setdefault("uploaded_by", request.user)
        return super().create(validated_data)


class ProjectManagementSubPlanUnitPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectManagementSubPlanUnitPeriod
        fields = [
            "id",
            "period_type",
            "start_date",
            "end_date",
            "year",
            "month",
            "week",
            "unit_no",
        ]


class ProjectManagementPlanSubPlanSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    assigned_users = serializers.SerializerMethodField()
    assigned_user_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="assigned_users",
        many=True,
        write_only=True,
        required=False,
    )
    unit_periods = ProjectManagementSubPlanUnitPeriodSerializer(many=True, required=False)

    class Meta:
        model = ProjectManagementPlanSubPlan
        fields = [
            "id",
            "serial_code",
            "title",
            "start_date",
            "end_date",
            "unit_type",
            "unit_no",
            "unit_cost",
            "cost",
            "sort_order",
            "assigned_users",
            "assigned_user_ids",
            "unit_periods",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["cost", "created_at", "updated_at"]

    def get_assigned_users(self, obj):
        return [
            {"id": user.id, "username": user.username}
            for user in obj.assigned_users.all().order_by("username")
        ]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be before start date."}
            )

        unit_no = attrs.get("unit_no", getattr(self.instance, "unit_no", 0))
        unit_periods = attrs.get("unit_periods")
        if unit_periods is not None:
            distributed_total = Decimal("0")
            for period in unit_periods:
                distributed_total += Decimal(str(period.get("unit_no") or 0))
            if distributed_total and abs(distributed_total - Decimal(str(unit_no or 0))) > Decimal(
                "0.01"
            ):
                raise serializers.ValidationError(
                    {
                        "unit_periods": (
                            "Sum of distributed units must equal the activity Unit No."
                        )
                    }
                )
        return attrs


class ProjectManagementPlanSerializer(serializers.ModelSerializer):
    assigned_users = serializers.SerializerMethodField()
    assigned_user_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="assigned_users",
        many=True,
        write_only=True,
        required=False,
    )
    project_id = serializers.IntegerField(source="project.id", read_only=True)
    work_items = ProjectManagementPlanWorkItemSerializer(many=True, required=False)
    sub_plans = ProjectManagementPlanSubPlanSerializer(many=True, required=False)
    attachments = ProjectManagementPlanAttachmentSerializer(many=True, read_only=True)
    approved_by = serializers.SerializerMethodField()

    class Meta:
        model = ProjectManagementProjectPlan
        fields = [
            "id",
            "serial_no",
            "serial_code",
            "title",
            "description",
            "duration_days",
            "start_date",
            "end_date",
            "status",
            "approval_status",
            "approved_by",
            "approved_at",
            "project_id",
            "assigned_users",
            "assigned_user_ids",
            "sub_plans",
            "work_items",
            "attachments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "approval_status",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        ]

    def get_assigned_users(self, obj):
        return [
            {"id": user.id, "username": user.username}
            for user in obj.assigned_users.all().order_by("username")
        ]

    def get_approved_by(self, obj):
        if not obj.approved_by:
            return None
        return {"id": obj.approved_by.id, "username": obj.approved_by.username}

    def create(self, validated_data):
        assigned_users = validated_data.pop("assigned_users", [])
        work_items_data = validated_data.pop("work_items", [])
        sub_plans_data = validated_data.pop("sub_plans", [])
        plan = ProjectManagementProjectPlan.objects.create(**validated_data)

        if assigned_users:
            plan.assigned_users.set(assigned_users)

        self._replace_sub_plans(plan, sub_plans_data)
        self._replace_work_items(plan, work_items_data)
        return plan

    def update(self, instance, validated_data):
        assigned_users = validated_data.pop("assigned_users", None)
        work_items_data = validated_data.pop("work_items", None)
        sub_plans_data = validated_data.pop("sub_plans", None)
        validated_data.pop("approval_status", None)
        validated_data.pop("approved_by", None)
        validated_data.pop("approved_at", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if assigned_users is not None:
            instance.assigned_users.set(assigned_users)

        if sub_plans_data is not None:
            self._replace_sub_plans(instance, sub_plans_data)

        if work_items_data is not None:
            self._replace_work_items(instance, work_items_data)

        return instance

    def _replace_sub_plans(self, plan, sub_plans_data):
        if sub_plans_data is None:
            return

        plan.sub_plans.all().delete()
        main_code = plan.serial_code or str(plan.serial_no)

        for index, sub_data in enumerate(sub_plans_data, start=1):
            sub_data = dict(sub_data)
            assigned_users = sub_data.pop("assigned_users", [])
            unit_periods = sub_data.pop("unit_periods", None)
            sub_data.pop("id", None)
            sub_data.pop("cost", None)  # always derived from unit_no * unit_cost
            serial_code = sub_data.pop("serial_code", None) or f"{main_code}.{index}"
            sort_order = sub_data.pop("sort_order", None) or index
            sub_plan = ProjectManagementPlanSubPlan.objects.create(
                plan=plan,
                serial_code=serial_code,
                sort_order=sort_order,
                **sub_data,
            )
            if assigned_users:
                sub_plan.assigned_users.set(assigned_users)
            self._replace_unit_periods(sub_plan, unit_periods)

    def _replace_unit_periods(self, sub_plan, unit_periods):
        if unit_periods is None:
            return

        sub_plan.unit_periods.all().delete()
        for period in unit_periods:
            period = dict(period)
            period.pop("id", None)
            period_type = period.get("period_type") or ProjectManagementSubPlanUnitPeriod.PERIOD_RANGE
            unit_no = Decimal(str(period.get("unit_no") or 0))
            if unit_no <= 0:
                continue

            start_date = period.get("start_date")
            end_date = period.get("end_date")
            year = int(period.get("year") or 0)
            month = int(period.get("month") or 0)
            week = int(period.get("week") or 0)

            if period_type == ProjectManagementSubPlanUnitPeriod.PERIOD_RANGE:
                if not start_date or not end_date:
                    continue
                year = year or int(str(start_date)[:4])
            elif period_type == ProjectManagementSubPlanUnitPeriod.PERIOD_MONTHLY and month:
                from calendar import monthrange as _monthrange
                from datetime import date as _date

                last_day = _monthrange(year, month)[1]
                start_date = _date(year, month, 1)
                end_date = _date(year, month, last_day)
                period_type = ProjectManagementSubPlanUnitPeriod.PERIOD_RANGE

            ProjectManagementSubPlanUnitPeriod.objects.create(
                sub_plan=sub_plan,
                period_type=period_type,
                start_date=start_date,
                end_date=end_date,
                year=year,
                month=month,
                week=week,
                unit_no=unit_no,
            )

    def _replace_work_items(self, plan, work_items_data):
        if work_items_data is None:
            return

        existing_items = {item.id: item for item in plan.work_items.all()}
        seen_ids = set()

        for index, item_data in enumerate(work_items_data, start=1):
            item_data = dict(item_data)
            item_id = item_data.pop("id", None)
            sort_order = item_data.pop("sort_order", None) or index
            self._validate_work_item_schedule_window(
                plan,
                item_data.get("scheduled_date"),
                item_data.get("scheduled_end_date"),
            )

            if item_id and item_id in existing_items:
                work_item = existing_items[item_id]
                work_item.title = item_data.get("title", work_item.title)
                work_item.state = item_data.get("state", work_item.state)
                work_item.notes = item_data.get("notes", work_item.notes)
                work_item.issues = item_data.get("issues", work_item.issues)
                work_item.assigned_to = item_data.get(
                    "assigned_to", work_item.assigned_to
                )
                work_item.scheduled_date = item_data.get(
                    "scheduled_date", work_item.scheduled_date
                )
                work_item.scheduled_end_date = item_data.get(
                    "scheduled_end_date", work_item.scheduled_end_date
                )
                work_item.sort_order = sort_order
                work_item.save()
                seen_ids.add(item_id)
                continue

            work_item = ProjectManagementPlanWorkItem.objects.create(
                plan=plan,
                sort_order=sort_order,
                **item_data,
            )
            seen_ids.add(work_item.id)

        for item_id, work_item in existing_items.items():
            if item_id not in seen_ids:
                work_item.delete()

        plan.refresh_from_db()
        plan.sync_status_from_work_items()

    def _validate_work_item_schedule_window(
        self, plan, scheduled_date, scheduled_end_date
    ):
        if (
            scheduled_date
            and scheduled_end_date
            and scheduled_end_date < scheduled_date
        ):
            raise serializers.ValidationError(
                {"scheduled_end_date": "End date cannot be before start date."}
            )

        if plan.start_date and scheduled_date and scheduled_date < plan.start_date:
            raise serializers.ValidationError(
                {
                    "scheduled_date": "Task start date must stay within the parent task date range."
                }
            )

        if plan.end_date and scheduled_date and scheduled_date > plan.end_date:
            raise serializers.ValidationError(
                {
                    "scheduled_date": "Task start date must stay within the parent task date range."
                }
            )

        if (
            plan.start_date
            and scheduled_end_date
            and scheduled_end_date < plan.start_date
        ):
            raise serializers.ValidationError(
                {
                    "scheduled_end_date": "Task end date must stay within the parent task date range."
                }
            )

        if plan.end_date and scheduled_end_date and scheduled_end_date > plan.end_date:
            raise serializers.ValidationError(
                {
                    "scheduled_end_date": "Task end date must stay within the parent task date range."
                }
            )


class ProjectManagementProjectMaterialSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    plan = serializers.SerializerMethodField()
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=ProjectManagementProjectPlan.objects.all(),
        source="plan",
        required=False,
        allow_null=True,
        write_only=True,
    )
    plan_serial_no = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = ProjectManagementProjectMaterial
        fields = [
            "id",
            "title",
            "category",
            "description",
            "unit",
            "quantity",
            "estimated_unit_cost",
            "estimated_total_cost",
            "preferred_vendor",
            "required_by",
            "notes",
            "sort_order",
            "plan",
            "plan_id",
            "plan_serial_no",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["estimated_total_cost", "created_at", "updated_at"]

    def get_plan(self, obj):
        if not obj.plan:
            return None
        return {
            "id": obj.plan.id,
            "serial_no": obj.plan.serial_no,
            "title": obj.plan.title,
        }

    def validate(self, attrs):
        plan = attrs.get("plan", getattr(self.instance, "plan", None))
        project = self.context.get("project") or getattr(self.instance, "project", None)
        required_by = attrs.get(
            "required_by", getattr(self.instance, "required_by", None)
        )

        if plan and project and plan.project_id != project.id:
            raise serializers.ValidationError(
                {"plan_id": "Selected roadmap step does not belong to this project."}
            )

        if project and required_by:
            if project.start_date and required_by < project.start_date:
                raise serializers.ValidationError(
                    {
                        "required_by": "Required by date must stay within the project timeline."
                    }
                )
            if project.end_date and required_by > project.end_date:
                raise serializers.ValidationError(
                    {
                        "required_by": "Required by date must stay within the project timeline."
                    }
                )

        return attrs


class ProjectManagementProjectSerializer(serializers.ModelSerializer):
    donor_name = serializers.CharField(source="donor.name", read_only=True)
    donor_id = serializers.PrimaryKeyRelatedField(
        queryset=Donor.objects.all(),
        source="donor",
        required=False,
        allow_null=True,
    )
    project_manager_name = serializers.CharField(
        source="project_manager.username", read_only=True
    )
    project_manager_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="project_manager",
        required=False,
        allow_null=True,
    )
    assigned_users = serializers.SerializerMethodField()
    assigned_user_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="assigned_users",
        many=True,
        write_only=True,
        required=False,
    )
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )
    plans = ProjectManagementPlanSerializer(many=True, required=False)
    materials = ProjectManagementProjectMaterialSerializer(many=True, required=False)
    materials_expense_id = serializers.IntegerField(
        source="materials_expense.id", read_only=True
    )
    materials_expense_invoice_number = serializers.CharField(
        source="materials_expense.invoice_number",
        read_only=True,
    )
    budget_code = serializers.CharField(source="budget.code", read_only=True)

    class Meta:
        model = ProjectManagementProject
        fields = [
            "id",
            "code",
            "title",
            "short_name",
            "donor_name",
            "donor_id",
            "project_type",
            "implementation_type",
            "status",
            "start_date",
            "end_date",
            "duration_months",
            "budget_amount",
            "budget",
            "budget_code",
            "currency",
            "project_manager_name",
            "project_manager_id",
            "assigned_users",
            "assigned_user_ids",
            "sector",
            "location",
            "target_beneficiaries",
            "background",
            "objectives",
            "expected_outcomes",
            "monitoring_plan",
            "reporting_frequency",
            "risk_level",
            "notes",
            "created_by_name",
            "created_at",
            "updated_at",
            "plans",
            "materials",
            "materials_expense_id",
            "materials_expense_invoice_number",
        ]
        read_only_fields = [
            "code",
            "duration_months",
            "budget",
            "budget_code",
            "created_at",
            "updated_at",
        ]

    def get_assigned_users(self, obj):
        return [
            {"id": user.id, "username": user.username}
            for user in obj.assigned_users.all().order_by("username")
        ]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be before start date."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        plans_data = validated_data.pop("plans", [])
        materials_data = validated_data.pop("materials", [])
        assigned_users = validated_data.pop("assigned_users", [])
        project = ProjectManagementProject.objects.create(**validated_data)
        if assigned_users:
            project.assigned_users.set(assigned_users)
        self._replace_plans(project, plans_data)
        self._replace_materials(project, materials_data)
        self._sync_materials_expense(project)
        request = self.context.get("request")
        sync_project_procurement_budget(
            project, user=getattr(request, "user", None) if request else None
        )
        return project

    @transaction.atomic
    def update(self, instance, validated_data):
        plans_data = validated_data.pop("plans", None)
        materials_data = validated_data.pop("materials", None)
        assigned_users = validated_data.pop("assigned_users", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if assigned_users is not None:
            instance.assigned_users.set(assigned_users)

        if plans_data is not None:
            self._replace_plans(instance, plans_data)

        if materials_data is not None:
            self._replace_materials(instance, materials_data)

        if materials_data is not None or plans_data is not None:
            self._sync_materials_expense(instance)

        if plans_data is not None:
            request = self.context.get("request")
            sync_project_procurement_budget(
                instance, user=getattr(request, "user", None) if request else None
            )

        return instance

    def _replace_plans(self, project, plans_data):
        if plans_data is None:
            return

        project.plans.all().delete()
        plan_serializer = ProjectManagementPlanSerializer()

        for index, plan_data in enumerate(plans_data, start=1):
            plan_data = dict(plan_data)
            assigned_users = plan_data.pop("assigned_users", [])
            work_items_data = plan_data.pop("work_items", [])
            sub_plans_data = plan_data.pop("sub_plans", [])
            serial_no = plan_data.pop("serial_no", None) or index
            serial_code = plan_data.pop("serial_code", None) or str(serial_no)

            # Derive main plan dates from sub plans when present
            if sub_plans_data:
                starts = [s.get("start_date") for s in sub_plans_data if s.get("start_date")]
                ends = [s.get("end_date") for s in sub_plans_data if s.get("end_date")]
                if starts and not plan_data.get("start_date"):
                    plan_data["start_date"] = min(starts)
                if ends and not plan_data.get("end_date"):
                    plan_data["end_date"] = max(ends)

            plan = ProjectManagementProjectPlan.objects.create(
                project=project,
                serial_no=serial_no,
                serial_code=serial_code,
                **plan_data,
            )
            if assigned_users:
                plan.assigned_users.set(assigned_users)

            plan_serializer._replace_sub_plans(plan, sub_plans_data)
            if work_items_data:
                plan_serializer._replace_work_items(plan, work_items_data)

    def _replace_materials(self, project, materials_data):
        if materials_data is None:
            return

        project.materials.all().delete()
        plan_lookup = {plan.serial_no: plan for plan in project.plans.all()}

        for index, material_data in enumerate(materials_data, start=1):
            material_data = dict(material_data)
            material_data.pop("id", None)
            plan_serial_no = material_data.pop("plan_serial_no", None)
            linked_plan = material_data.pop("plan", None)
            sort_order = material_data.pop("sort_order", None) or index

            if linked_plan and linked_plan.project_id == project.id:
                material_plan = linked_plan
            elif plan_serial_no:
                material_plan = plan_lookup.get(int(plan_serial_no))
            else:
                material_plan = None

            ProjectManagementProjectMaterial.objects.create(
                project=project,
                plan=material_plan,
                sort_order=sort_order,
                **material_data,
            )

    def _sync_materials_expense(self, project):
        materials = list(project.materials.select_related("plan").all())
        expense = project.materials_expense

        if not materials:
            if expense and expense.status == "Draft":
                expense.delete()
                project.materials_expense = None
                project.save(update_fields=["materials_expense", "updated_at"])
            return

        if expense and expense.status != "Draft":
            return

        if expense is None:
            expense = ProjectManagementExpense.objects.create(
                project=project,
                title=f"{project.title} Materials",
                description="Auto-generated draft from the Project Materials tab.",
                expense_date=project.start_date,
                currency=project.currency or "BDT",
                status="Draft",
            )
            project.materials_expense = expense
            project.save(update_fields=["materials_expense", "updated_at"])

        expense.title = f"{project.title} Materials"
        expense.description = "Auto-generated draft from the Project Materials tab. Update the project materials or continue in Expense Management while the expense remains in draft."
        expense.expense_date = project.start_date or expense.expense_date
        expense.currency = project.currency or expense.currency or "BDT"
        expense.project = project
        expense.plan = None
        expense.save()

        expense.items.all().delete()
        for index, material in enumerate(materials, start=1):
            line_description_parts = [
                segment for segment in [material.description, material.notes] if segment
            ]
            ProjectManagementExpenseItem.objects.create(
                expense=expense,
                title=material.title,
                description=" | ".join(line_description_parts)[:255],
                quantity=material.quantity,
                unit_price=material.estimated_unit_cost,
                sort_order=index,
            )

        expense.recalculate_total(save=True)


class ProjectManagementExpenseItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    unit_price = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        rounding=decimal.ROUND_HALF_UP,
    )
    quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        rounding=decimal.ROUND_HALF_UP,
    )

    class Meta:
        model = ProjectManagementExpenseItem
        fields = [
            "id",
            "title",
            "description",
            "quantity",
            "unit_price",
            "line_total",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["line_total", "created_at", "updated_at"]


class ProjectManagementExpenseSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source="project.title", read_only=True)
    plan_title = serializers.CharField(source="plan.title", read_only=True)
    project_id = serializers.PrimaryKeyRelatedField(
        queryset=ProjectManagementProject.objects.all(),
        source="project",
    )
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=ProjectManagementProjectPlan.objects.all(),
        source="plan",
        required=False,
        allow_null=True,
    )
    created_by = serializers.SerializerMethodField()
    approved_by = serializers.SerializerMethodField()
    items = ProjectManagementExpenseItemSerializer(many=True, required=False)

    class Meta:
        model = ProjectManagementExpense
        fields = [
            "id",
            "invoice_number",
            "title",
            "description",
            "vendor_name",
            "expense_date",
            "currency",
            "status",
            "total_amount",
            "project_id",
            "project_title",
            "plan_id",
            "plan_title",
            "items",
            "submitted_at",
            "approved_at",
            "paid_at",
            "approved_by",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "invoice_number",
            "total_amount",
            "submitted_at",
            "approved_at",
            "paid_at",
            "approved_by",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_created_by(self, obj):
        if not obj.created_by:
            return None
        return {"id": obj.created_by.id, "username": obj.created_by.username}

    def get_approved_by(self, obj):
        if not obj.approved_by:
            return None
        return {"id": obj.approved_by.id, "username": obj.approved_by.username}

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        plan = attrs.get("plan", getattr(self.instance, "plan", None))
        status_value = attrs.get("status", getattr(self.instance, "status", "Draft"))

        if plan and project and plan.project_id != project.id:
            raise serializers.ValidationError(
                {"plan_id": "Selected task does not belong to the selected project."}
            )

        if status_value == "Paid" and (
            self.instance is None and not attrs.get("approved_at")
        ):
            raise serializers.ValidationError(
                {"status": "New expenses cannot be created directly as paid."}
            )

        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data.setdefault("created_by", request.user)

        expense = ProjectManagementExpense.objects.create(**validated_data)
        self._replace_items(expense, items_data)
        expense.recalculate_total(save=True)
        return expense

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            self._replace_items(instance, items_data)

        instance.recalculate_total(save=True)
        return instance

    def _replace_items(self, expense, items_data):
        if items_data is None:
            return

        existing_items = {item.id: item for item in expense.items.all()}
        seen_ids = set()

        for index, item_data in enumerate(items_data, start=1):
            item_data = dict(item_data)
            item_id = item_data.pop("id", None)
            sort_order = item_data.pop("sort_order", None) or index

            if item_id and item_id in existing_items:
                item = existing_items[item_id]
                item.title = item_data.get("title", item.title)
                item.description = item_data.get("description", item.description)
                item.quantity = item_data.get("quantity", item.quantity)
                item.unit_price = item_data.get("unit_price", item.unit_price)
                item.sort_order = sort_order
                item.save()
                seen_ids.add(item_id)
                continue

            item = ProjectManagementExpenseItem.objects.create(
                expense=expense,
                sort_order=sort_order,
                **item_data,
            )
            seen_ids.add(item.id)

        for item_id, item in existing_items.items():
            if item_id not in seen_ids:
                item.delete()


class AdvanceSerializer(serializers.ModelSerializer):
    from_employee_name = serializers.CharField(
        source="from_employee.username", read_only=True
    )
    from_employee_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="from_employee",
        required=False,
        allow_null=True,
    )
    project_title = serializers.CharField(source="project.title", read_only=True)
    project_id_field = serializers.PrimaryKeyRelatedField(
        queryset=ProjectManagementProject.objects.all(),
        source="project",
        # write_only=True,
    )
    signature_recipient = serializers.ImageField(required=False, allow_null=True)
    signature_accountant = serializers.ImageField(required=False, allow_null=True)
    signature_recommender = serializers.ImageField(required=False, allow_null=True)
    signature_approver = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Advance
        fields = [
            "id",
            "from_employee_name",
            "from_employee_id",
            "from_text",
            "to_text",
            "project_title",
            "project_id_field",
            "cause_of_advance",
            "advance_receivable_date",
            "advance_receivable_amount",
            "amount_in_words",
            "expected_date",
            "receive_medium",
            "bank_name",
            "cheque_no",
            "accountant_remarks",
            "check_outstanding",
            "check_adjusted",
            "check_completed",
            "signature_recipient",
            "signature_accountant",
            "signature_recommender",
            "signature_approver",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "amount_in_words",
            "created_at",
            "from_employee_name",
            "project_title",
        ]

    def validate(self, attrs):
        receive_medium = attrs.get(
            "receive_medium", getattr(self.instance, "receive_medium", None)
        )

        if receive_medium == "cheque":
            bank_name = attrs.get("bank_name", getattr(self.instance, "bank_name", ""))
            cheque_no = attrs.get("cheque_no", getattr(self.instance, "cheque_no", ""))

            if not bank_name or not bank_name.strip():
                raise serializers.ValidationError(
                    {"bank_name": "Bank name is required when receive medium is Cheque."}
                )
            if not cheque_no or not cheque_no.strip():
                raise serializers.ValidationError(
                    {"cheque_no": "Cheque number is required when receive medium is Cheque."}
                )

        return attrs

    # def create(self, validated_data):
    #     validated_data.pop("project_id_field", None)
    #     request = self.context.get("request")
    #     if request and request.user and request.user.is_authenticated:
    #         validated_data.setdefault("from_employee", request.user)
    #     return super().create(validated_data)
