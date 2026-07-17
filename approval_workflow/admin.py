from django.contrib import admin
from .models import ApprovalWorkflow, ApprovalLevel, ApprovalLevelUser


class ApprovalLevelUserInline(admin.TabularInline):
    model = ApprovalLevelUser
    extra = 0


class ApprovalLevelInline(admin.StackedInline):
    model = ApprovalLevel
    extra = 0
    inlines = [ApprovalLevelUserInline]


@admin.register(ApprovalWorkflow)
class ApprovalWorkflowAdmin(admin.ModelAdmin):
    list_display = ['id', 'module_type_name', 'menu_name', 'is_active', 'created_by', 'created_at']
    search_fields = ['menu_name', 'module_type_name']
    list_filter = ['is_active']
    inlines = [ApprovalLevelInline]
