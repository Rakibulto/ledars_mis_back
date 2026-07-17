from django.db import models
from authentication.models import User


class Todo(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('hold', 'Hold'),
        ('completed', 'Completed'),
    ]

    todo_title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    expected_date = models.DateField(blank=True, null=True)
    assign_users = models.ManyToManyField(User, related_name='assigned_todos', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_todos'
    )
    # Snapshot fields — saved once at creation, never updated
    creator_name = models.CharField(max_length=255, blank=True, null=True)
    creator_email = models.EmailField(blank=True, null=True)
    creator_user_id = models.IntegerField(blank=True, null=True)

    # Recurrence fields
    is_recurring = models.BooleanField(default=False)
    recurrence_type = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='none',
    )
    recurrence_weekdays = models.JSONField(
        blank=True, null=True,
        help_text="List of weekday numbers (0=Mon..6=Sun) for weekly recurrence"
    )
    recurrence_day_of_month = models.PositiveSmallIntegerField(
        blank=True, null=True,
        help_text="Day of month (1-31) for monthly recurrence"
    )
    parent_todo = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        blank=True, null=True, related_name='recurring_instances'
    )
    next_expected_date = models.DateField(
        blank=True, null=True,
        help_text="Expected date for the next auto-created recurring instance"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Todo'
        verbose_name_plural = 'Todos'

    def __str__(self):
        return self.todo_title


class TodoAttachment(models.Model):
    todo = models.ForeignKey(Todo, related_name='attachments', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='todo_attachments', on_delete=models.CASCADE)
    file = models.FileField(upload_to='todo/attachments/', blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)  # Tiptap HTML
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Todo Attachment'
        verbose_name_plural = 'Todo Attachments'

    def __str__(self):
        return f"Attachment #{self.id} for Todo #{self.todo_id}"