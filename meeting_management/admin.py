from django.contrib import admin
from .models import Meeting, MeetingAttachment


class MeetingAttachmentInline(admin.TabularInline):
    model = MeetingAttachment
    extra = 1


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ['meeting_id', 'title', 'date', 'start_time', 'end_time', 'created_by']
    search_fields = ['title', 'meeting_id']
    list_filter = ['date']
    inlines = [MeetingAttachmentInline]


@admin.register(MeetingAttachment)
class MeetingAttachmentAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'meeting', 'uploaded_at']
