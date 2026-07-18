from django.contrib import admin

from .models import (
    ProjectManagementExpense,
    ProjectManagementExpenseItem,
    ProjectManagementPlanAttachment,
    ProjectManagementPlanSubPlan,
    ProjectManagementProject,
    ProjectManagementProjectMaterial,
    ProjectManagementProjectPlan,
    ProjectManagementUnit,
)


@admin.register(ProjectManagementUnit)
class ProjectManagementUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")


class ProjectManagementProjectPlanInline(admin.TabularInline):
    model = ProjectManagementProjectPlan
    extra = 0
    filter_horizontal = ("assigned_users",)


class ProjectManagementPlanAttachmentInline(admin.TabularInline):
    model = ProjectManagementPlanAttachment
    extra = 0
    fields = ("file", "original_name", "uploaded_by", "created_at")
    readonly_fields = ("created_at",)


class ProjectManagementExpenseItemInline(admin.TabularInline):
    model = ProjectManagementExpenseItem
    extra = 0
    fields = ("title", "description", "quantity", "unit_price", "line_total", "sort_order")
    readonly_fields = ("line_total",)


class ProjectManagementProjectMaterialInline(admin.TabularInline):
    model = ProjectManagementProjectMaterial
    extra = 0
    fields = (
        "title",
        "category",
        "plan",
        "unit",
        "quantity",
        "estimated_unit_cost",
        "estimated_total_cost",
        "preferred_vendor",
        "required_by",
        "sort_order",
    )
    readonly_fields = ("estimated_total_cost",)


@admin.register(ProjectManagementProject)
class ProjectManagementProjectAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "project_type",
        "status",
        "donor",
        "project_manager",
        "materials_expense",
        "start_date",
        "end_date",
    )
    list_filter = ("project_type", "status", "implementation_type", "reporting_frequency")
    search_fields = ("code", "title", "short_name", "location", "sector")
    filter_horizontal = ("assigned_users",)
    inlines = [ProjectManagementProjectPlanInline, ProjectManagementProjectMaterialInline]


class ProjectManagementPlanSubPlanInline(admin.TabularInline):
    model = ProjectManagementPlanSubPlan
    extra = 0
    filter_horizontal = ("assigned_users",)


@admin.register(ProjectManagementProjectPlan)
class ProjectManagementProjectPlanAdmin(admin.ModelAdmin):
    list_display = ("project", "serial_no", "serial_code", "title", "status", "duration_days")
    list_filter = ("status",)
    search_fields = ("project__title", "title", "description", "serial_code")
    filter_horizontal = ("assigned_users",)
    inlines = [ProjectManagementPlanSubPlanInline, ProjectManagementPlanAttachmentInline]


@admin.register(ProjectManagementPlanSubPlan)
class ProjectManagementPlanSubPlanAdmin(admin.ModelAdmin):
    list_display = (
        "serial_code",
        "title",
        "plan",
        "unit_type",
        "unit_no",
        "unit_cost",
        "cost",
        "start_date",
        "end_date",
    )
    search_fields = ("serial_code", "title", "plan__title", "plan__project__title", "unit_type")
    filter_horizontal = ("assigned_users",)


@admin.register(ProjectManagementPlanAttachment)
class ProjectManagementPlanAttachmentAdmin(admin.ModelAdmin):
    list_display = ("display_name", "plan", "uploaded_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("original_name", "plan__title", "plan__project__title")


@admin.register(ProjectManagementExpense)
class ProjectManagementExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "title",
        "project",
        "plan",
        "expense_date",
        "status",
        "currency",
        "total_amount",
    )
    list_filter = ("status", "currency", "expense_date")
    search_fields = ("invoice_number", "title", "description", "vendor_name", "project__title", "plan__title")
    inlines = [ProjectManagementExpenseItemInline]
