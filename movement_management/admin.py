from django.contrib import admin
from .models import MovementManagement


@admin.register(MovementManagement)
class MovementManagementAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'designation', 'project_name',
        'grand_total', 'status', 'created_at',
    ]
    list_filter = ['status']
    search_fields = ['name', 'project_name']
    readonly_fields = [
        'created_by', 'created_at', 'updated_at',
        'submitted_by_signature', 'checked_supervised_signature',
        'approved_by_signature',
    ]
