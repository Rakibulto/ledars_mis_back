from django.contrib import admin
from .models import Notification
from unfold.admin import ModelAdmin



@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ('title', 'type', 'status', 'employee', 'receiver','created_at', 'updated_at')
    list_filter = ('type', 'status')
    search_fields = ('employee__email', 'receiver__email', 'type', 'status__iexact')