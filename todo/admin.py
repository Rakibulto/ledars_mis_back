from django.contrib import admin
from .models import Todo, TodoAttachment


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'todo_title', 'status', 'creator_name',
        'is_recurring', 'recurrence_type', 'expected_date', 'next_expected_date', 'created_at',
    ]
    list_filter = ['status', 'is_recurring', 'recurrence_type']
    search_fields = ['todo_title', 'creator_name', 'creator_email']
    raw_id_fields = ['creator', 'parent_todo']
    filter_horizontal = ['assign_users']


@admin.register(TodoAttachment)
class TodoAttachmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'todo', 'user', 'created_at']
    raw_id_fields = ['todo', 'user']
