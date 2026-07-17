from django.contrib import admin
from .models import Lead, LeadFollowUp, LeadFollowUpAttachment


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('lead_id', 'name', 'phone', 'status', 'project_type', 'created_at')
    search_fields = ('lead_id', 'name', 'phone', 'email', 'project_name')
    list_filter = ('status', 'project_type', 'source', 'city')
    readonly_fields = ('lead_id', 'created_at', 'updated_at')


class LeadFollowUpAttachmentInline(admin.TabularInline):
    model = LeadFollowUpAttachment
    extra = 0
    readonly_fields = ('file_name', 'file_size', 'uploaded_at')


@admin.register(LeadFollowUp)
class LeadFollowUpAdmin(admin.ModelAdmin):
    list_display = ('title', 'lead', 'next_contact_date', 'created_by', 'created_at')
    list_filter = ('next_contact_date', 'created_at')
    search_fields = ('title', 'description', 'lead__name', 'lead__lead_id')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [LeadFollowUpAttachmentInline]
