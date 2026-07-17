from django.contrib import admin
from authentication.models import User
from employee.models import Employee
from .models import (
    CompensatoryLeaveBalance,
    CompensatoryLeaveEarned,
    LeaveApproval,
    LeaveGroup,
    LeavePolicy,
    LeaveRequest,
    LeaveReset,
    LeaveTransfer,
    SupervisorLevel,
    SpecialLeavePolicy,
)
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.contrib.filters.admin import (
    RelatedDropdownFilter,
    MultipleRelatedDropdownFilter,
)
import logging

logger = logging.getLogger(__name__)


class LeaveGroupResource(resources.ModelResource):
    """
    Resource class for importing/exporting LeaveGroup model data.
    Ensures consistency between export and import formats.
    """

    name = fields.Field(
        column_name="name", attribute="name", widget=widgets.CharWidget()
    )
    description = fields.Field(
        column_name="description", attribute="description", default=None
    )
    created_at = fields.Field(
        column_name="created_at",
        attribute="created_at",
        widget=widgets.DateTimeWidget(format="%Y-%m-%d %H:%M:%S"),
        default=None,
    )
    updated_at = fields.Field(
        column_name="updated_at",
        attribute="updated_at",
        widget=widgets.DateTimeWidget(format="%Y-%m-%d %H:%M:%S"),
        default=None,
    )

    class Meta:
        model = LeaveGroup
        fields = ("name", "description", "created_at", "updated_at")
        export_order = fields
        import_id_fields = ("name",)  # Use name as unique identifier
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        """
        Validate data before importing a row.
        Skip empty rows and handle missing created_at/updated_at columns.
        """
        # Skip empty rows
        if not any(row.values()):
            logger.warning("Skipping empty row during LeaveGroup import")
            return False

        # Validate name
        name = row.get("name")
        if not name:
            raise ValueError("name is required")
        if name not in dict(LeaveGroup.GROUP_TYPES).keys():
            raise ValueError(
                f"Invalid leave group name: {name}. Must be one of {dict(LeaveGroup.GROUP_TYPES).keys()}"
            )

        # Handle created_at and updated_at (allow missing or empty)
        for date_field in ["created_at", "updated_at"]:
            if row.get(date_field):
                try:
                    from datetime import datetime

                    datetime.strptime(row[date_field], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    raise ValueError(
                        f"Invalid date format for {date_field}: {row[date_field]}. Expected YYYY-MM-DD HH:MM:SS"
                    )
            else:
                logger.debug(
                    f"{date_field} is missing or empty for row with name {name}; will be set by model"
                )

    def after_save_instance(self, instance, row, dry_run, **kwargs):
        """
        Post-import processing for LeaveGroup.
        No custom save logic required, but included for compatibility.
        """
        pass


class LeavePolicyResource(resources.ModelResource):
    """
    Resource class for importing/exporting LeavePolicy model data.
    Ensures consistency between export and import formats.
    """

    leave_type_name = fields.Field(
        column_name="leave_type_name", attribute="leave_type_name"
    )
    leave_groups = fields.Field(
        column_name="leave_groups",
        attribute="leave_groups",
        widget=widgets.ManyToManyWidget(LeaveGroup, field="name", separator=","),
    )
    total_leave_days = fields.Field(
        column_name="total_leave_days", attribute="total_leave_days"
    )
    gender = fields.Field(
        column_name="gender", attribute="gender", widget=widgets.CharWidget()
    )
    apply_before_days = fields.Field(
        column_name="apply_before_days", attribute="apply_before_days"
    )
    effective_from = fields.Field(
        column_name="effective_from",
        attribute="effective_from",
        widget=widgets.CharWidget(),
    )
    max_days_per_request = fields.Field(
        column_name="max_days_per_request", attribute="max_days_per_request"
    )
    min_days_per_request = fields.Field(
        column_name="min_days_per_request", attribute="min_days_per_request"
    )
    allow_half_day = fields.Field(
        column_name="allow_half_day",
        attribute="allow_half_day",
        widget=widgets.BooleanWidget(),
    )
    count_holidays = fields.Field(
        column_name="count_holidays",
        attribute="count_holidays",
        widget=widgets.BooleanWidget(),
    )
    count_weekends = fields.Field(
        column_name="count_weekends",
        attribute="count_weekends",
        widget=widgets.BooleanWidget(),
    )
    is_active = fields.Field(
        column_name="is_active", attribute="is_active", widget=widgets.BooleanWidget()
    )
    validity = fields.Field(column_name="validity", attribute="validity")

    class Meta:
        model = LeavePolicy
        fields = (
            "leave_type_name",
            "leave_groups",
            "total_leave_days",
            "gender",
            "apply_before_days",
            "effective_from",
            "max_days_per_request",
            "min_days_per_request",
            "allow_half_day",
            "count_holidays",
            "count_weekends",
            "is_active",
            "validity",
        )
        export_order = fields
        import_id_fields = ("leave_type_name",)
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        """
        Validate data before importing a row.
        """
        if not any(row.values()):
            logger.warning("Skipping empty row during LeavePolicy import")
            return False

        if not row.get("leave_type_name"):
            raise ValueError("leave_type_name is required")

        # Simplify validation for numeric fields
        numeric_fields = [
            "total_leave_days",
            "apply_before_days",
            "max_days_per_request",
            "min_days_per_request",
            "validity",
        ]
        for field in numeric_fields:
            if row.get(field) is not None and row.get(field) != "":
                try:
                    value = int(row[field])
                    if value < 0:
                        raise ValueError(f"{field} must be a non-negative integer")
                except (ValueError, TypeError):
                    raise ValueError(
                        f"Invalid value for {field}: {row[field]}. Must be a non-negative integer"
                    )

    def after_save_instance(self, instance, row, dry_run, **kwargs):
        """
        Post-import processing for LeavePolicy.
        No custom save logic required.
        """
        pass


class SupervisorLevelResource(resources.ModelResource):
    """
    Resource class for SupervisorLevel import/export.
    Displays employee name and supervisor username instead of primary keys.
    """

    employee = fields.Field(
        column_name="employee",
        attribute="employee",
        widget=widgets.ForeignKeyWidget(Employee, "employee_name"),
    )

    supervisor = fields.Field(
        column_name="supervisor",
        attribute="supervisor",
        widget=widgets.ForeignKeyWidget(User, "username"),
    )

    level = fields.Field(column_name="level", attribute="level")

    class Meta:
        model = SupervisorLevel
        import_id_fields = ("employee", "supervisor")
        export_order = ("employee", "supervisor", "level")
        skip_unchanged = True
        report_skipped = True

    # def before_save_instance(self, instance, **kwargs):
    #     if instance.supervisor and SupervisorLevel.objects.filter(
    #         employee=instance.employee,
    #         supervisor=instance.supervisor
    #     ).exclude(pk=instance.pk).exists():
    #         raise ValidationError(
    #             f"{instance.supervisor} is already assigned as a supervisor for {instance.employee} at another level."
    #         )


class LeaveRequestResource(resources.ModelResource):
    """
    Resource class for importing/exporting LeaveRequest model data.
    Handles foreign key relationships and date formatting.
    """

    creator = fields.Field(
        column_name="creator",
        attribute="creator",
        widget=widgets.ForeignKeyWidget(User, "username"),
    )

    employee = fields.Field(
        column_name="employee",
        attribute="employee",
        widget=widgets.ForeignKeyWidget(Employee, "employee_id"),
    )

    leave_policy = fields.Field(
        column_name="leave_policy",
        attribute="leave_policy",
        widget=widgets.ForeignKeyWidget(LeavePolicy, "leave_type_name"),
    )

    start_date = fields.Field(
        column_name="start_date",
        attribute="start_date",
        widget=widgets.DateWidget(format="%Y-%m-%d"),
    )

    end_date = fields.Field(
        column_name="end_date",
        attribute="end_date",
        widget=widgets.DateWidget(format="%Y-%m-%d"),
    )

    is_half_day = fields.Field(
        column_name="is_half_day",
        attribute="is_half_day",
        widget=widgets.BooleanWidget(),
    )

    reason = fields.Field(
        column_name="reason", attribute="reason", widget=widgets.CharWidget()
    )

    status = fields.Field(
        column_name="status", attribute="status", widget=widgets.CharWidget()
    )

    updated_by = fields.Field(
        column_name="updated_by",
        attribute="updated_by",
        widget=widgets.ForeignKeyWidget(User, "username"),
    )

    created_at = fields.Field(
        column_name="created_at",
        attribute="created_at",
        widget=widgets.DateTimeWidget(format="%Y-%m-%d %H:%M:%S"),
    )

    updated_at = fields.Field(
        column_name="updated_at",
        attribute="updated_at",
        widget=widgets.DateTimeWidget(format="%Y-%m-%d %H:%M:%S"),
    )

    class Meta:
        model = LeaveRequest
        fields = (
            "creator",
            "employee",
            "leave_policy",
            "start_date",
            "end_date",
            "is_half_day",
            "reason",
            "status",
            "updated_by",
            "created_at",
            "updated_at",
        )
        export_order = fields
        import_id_fields = ("employee", "leave_policy", "start_date", "end_date")
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        """
        Validate data before importing a row.
        """
        # Skip empty rows
        if not any(row.values()):
            logger.warning("Skipping empty row during LeaveRequest import")
            return False

        # Validate required fields
        required_fields = [
            "employee",
            "leave_policy",
            "start_date",
            "end_date",
            "status",
        ]
        for field in required_fields:
            if not row.get(field):
                raise ValueError(f"{field} is required")

        # Validate status choices
        valid_statuses = ["pending", "approved", "rejected", "cancelled"]
        if row.get("status") and row["status"] not in valid_statuses:
            raise ValueError(
                f"Invalid status: {row['status']}. Must be one of {valid_statuses}"
            )

        # Validate date format
        for date_field in ["start_date", "end_date"]:
            if row.get(date_field):
                try:
                    from datetime import datetime

                    datetime.strptime(row[date_field], "%Y-%m-%d")
                except ValueError:
                    raise ValueError(
                        f"Invalid date format for {date_field}: {row[date_field]}. Expected YYYY-MM-DD"
                    )

        # Validate date range
        if row.get("start_date") and row.get("end_date"):
            start = datetime.strptime(row["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(row["end_date"], "%Y-%m-%d").date()
            if start > end:
                raise ValueError("start_date cannot be after end_date")

    def after_save_instance(self, instance, row, dry_run, **kwargs):
        """
        Post-import processing for LeaveRequest.
        """
        pass


@admin.register(LeaveGroup)
class LeaveGroupAdmin(ModelAdmin, ImportExportModelAdmin):
    list_display = ("id", "name", "description", "created_at", "updated_at")
    search_fields = ("name",)
    ordering = ("-created_at",)
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = LeaveGroupResource


@admin.register(LeavePolicy)
class LeavePolicyAdmin(ModelAdmin, ImportExportModelAdmin):
    list_display = (
        "id",
        "leave_type_name",
        "get_leave_groups",
        "total_leave_days",
        "is_active",
    )
    search_fields = ("leave_type_name",)
    list_filter_submit = True
    list_filter = [
        ("leave_groups", MultipleRelatedDropdownFilter),
        ("leave_type_name"),
        ("is_active"),
    ]
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = LeavePolicyResource

    def get_leave_groups(self, obj):
        return ", ".join([group.name for group in obj.leave_groups.all()])

    get_leave_groups.short_description = "Leave Groups"


@admin.register(SpecialLeavePolicy)
class SpecialLeavePolicyAdmin(ModelAdmin):
    list_display = ("leave_policy", "available_policies_list")
    filter_horizontal = ("available_policies",)
    search_fields = ("leave_policy__leave_type_name",)
    list_filter_submit = True
    list_filter = [("leave_policy__leave_groups", RelatedDropdownFilter)]
    ordering = ("-id",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("leave_policy")

    def available_policies_list(self, obj):
        policies = []
        for policy in obj.available_policies.all():
            groups = [group.name for group in policy.leave_groups.all()]
            groups_str = f"{', '.join(groups)}" if groups else ""
            policies.append(f"{groups_str} - {policy.leave_type_name}")
        return " | ".join(policies)

    available_policies_list.short_description = "Available Policies"


@admin.register(LeaveRequest)
class LeaveRequestAdmin(ModelAdmin, ImportExportModelAdmin):
    list_display = (
        "creator",
        "employee",
        "leave_policy",
        "status",
        "start_date",
        "end_date",
        "created_at",
        "updated_at",
        "updated_by",
    )
    search_fields = ("employee__employee_name", "leave_policy__leave_type_name")
    list_filter = ("status", "leave_policy__leave_groups")
    ordering = ("-created_at",)
    readonly_fields = ("creator", "updated_by")
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = LeaveRequestResource

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("employee", "leave_policy")


@admin.register(SupervisorLevel)
class SupervisorLevelAdmin(ModelAdmin, ImportExportModelAdmin):
    list_display = ("employee", "supervisor", "level", "created_at", "updated_at")
    search_fields = (
        "employee__employee_name",
        "supervisor__username",
        "employee__user__email",
        "supervisor__email",
    )
    list_filter = ("level",)
    ordering = ("-created_at",)
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = SupervisorLevelResource

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("employee", "supervisor")


@admin.register(LeaveApproval)
class LeaveApprovalAdmin(ModelAdmin):
    list_display = (
        "pk",
        "leave_request",
        "approver",
        "status",
        "level",
        "created_at",
        "updated_at",
    )
    search_fields = ("leave_request__employee__employee_name", "approver__username")
    list_filter = ("status", "level")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("leave_request", "approver")


@admin.register(LeaveReset)
class LeaveResetAdmin(ModelAdmin):
    list_display = (
        "start_month",
        "start_day",
        "end_month",
        "end_day",
        "created_at",
        "updated_at",
    )
    search_fields = ("employee__employee_name", "leave_policy__leave_type_name")
    list_filter = (
        "start_month",
        "end_month",
    )
    ordering = ("-created_at",)


@admin.register(LeaveTransfer)
class LeaveTransferAdmin(ModelAdmin):
    list_display = (
        "employee",
        "days_transferred",
        "transfer_date",
        "year",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "from_employee__employee_name",
        "to_employee__employee_name",
        "leave_policy__leave_type_name",
    )
    list_filter = ("employee",)
    ordering = ("-created_at",)


@admin.register(CompensatoryLeaveBalance)
class CompensatoryLeaveBalanceAdmin(ModelAdmin):
    list_display = [
        "employee",
        "total_earned",
        "total_used",
        "current_balance",
        "last_updated",
    ]
    list_filter = ["last_updated"]
    search_fields = ["employee__employee_name", "employee__employee_id"]
    readonly_fields = ["last_updated"]

    actions = ["clean_expired_leaves"]

    def clean_expired_leaves(self, request, queryset):
        total_cleaned = 0
        for balance in queryset:
            total_cleaned += balance.clean_expired_leaves()

        self.message_user(
            request,
            f"Successfully cleaned {total_cleaned} expired compensatory leaves.",
        )

    clean_expired_leaves.short_description = "Clean expired compensatory leaves"


@admin.register(CompensatoryLeaveEarned)
class CompensatoryLeaveEarnedAdmin(ModelAdmin):
    list_display = [
        "employee",
        "earned_date",
        "expires_on",
        "is_used",
        "used_date",
        "is_expired",
    ]
    list_filter = ["is_used", "is_expired", "earned_date", "expires_on"]
    search_fields = ["employee__employee_name", "employee__employee_id"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["related_attendance"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("employee")
