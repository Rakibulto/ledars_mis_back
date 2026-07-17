from django.contrib import admin
from .models import ReturnHeader, ReturnLine, ReturnDamageHistory, ReturnSequence


class ReturnLineInline(admin.TabularInline):
    model = ReturnLine
    extra = 0


@admin.register(ReturnHeader)
class ReturnHeaderAdmin(admin.ModelAdmin):
    list_display = ['return_number', 'return_type', 'status', 'return_date', 'created_by', 'created_at']
    list_filter = ['status', 'return_type', 'source_document_type']
    search_fields = ['return_number', 'project', 'source_location']
    inlines = [ReturnLineInline]


@admin.register(ReturnDamageHistory)
class ReturnDamageHistoryAdmin(admin.ModelAdmin):
    list_display = ['return_header', 'item_name', 'damaged_quantity', 'recorded_at']


admin.site.register(ReturnSequence)

