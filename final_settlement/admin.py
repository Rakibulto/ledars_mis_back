from django.contrib import admin
from .models import FinalSettlement


@admin.register(FinalSettlement)
class FinalSettlementAdmin(admin.ModelAdmin):
    list_display = [
        'name_of_staff', 'project_name', 'designation',
        'date', 'status', 'total_amount', 'created_at',
    ]
    list_filter = ['status']
    search_fields = ['name_of_staff', 'project_name']
    readonly_fields = [
        'created_by', 'created_at', 'updated_at',
        'supervisor_signature', 'finance_signature', 'management_signature',
        'payment_completed_at', 'payment_completed_by',
    ]