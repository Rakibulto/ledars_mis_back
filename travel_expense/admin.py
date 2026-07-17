from django.contrib import admin
from .models import TravelExpense, TravelExpenseAttachment


class TravelExpenseAttachmentInline(admin.TabularInline):
    model = TravelExpenseAttachment
    extra = 0
    readonly_fields = ['original_name', 'file_size', 'uploaded_by', 'uploaded_at']


@admin.register(TravelExpense)
class TravelExpenseAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'designation', 'project',
        'grand_total', 'status', 'created_at',
    ]
    list_filter = ['status']
    search_fields = ['name', 'project']
    inlines = [TravelExpenseAttachmentInline]
    readonly_fields = [
        'created_by', 'created_at', 'updated_at',
        'total_travel_fare', 'total_food', 'total_lodging', 'grand_total',
        'prepared_received_signature', 'checked_by_signature',
        'accountant_signature', 'approved_by_signature',
    ]
