from django.db import models
from django.conf import settings


MEETING_STATUS_CHOICES = [
    ('scheduled', 'Scheduled'),
    ('in_progress', 'In Progress'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
    ('postponed', 'Postponed'),
]


class Meeting(models.Model):
    meeting_id = models.CharField(max_length=20, unique=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=50, default='scheduled', choices=MEETING_STATUS_CHOICES)
    location = models.CharField(max_length=255, blank=True, null=True)
    meeting_link = models.CharField(max_length=500, blank=True, null=True)
    agenda = models.TextField(blank=True, null=True)
    minutes = models.TextField(blank=True, null=True)

    assigned_to = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='assigned_meetings'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_meetings'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-start_time']

    def __str__(self):
        assigned_names = ', '.join(
            u.get_full_name() or u.username for u in self.assigned_to.all()
        ) or 'Unassigned'
        return f"{self.meeting_id} — {self.title} ({assigned_names})"

    def save(self, *args, **kwargs):
        if not self.meeting_id:
            last = Meeting.objects.order_by('-id').first()
            next_num = (last.id + 1) if last else 1
            self.meeting_id = f'MTG-{next_num:04d}'
        super().save(*args, **kwargs)


class MeetingAttachment(models.Model):
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name='attachments'
    )
    file = models.FileField(upload_to='meetings/%Y/%m/')
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.IntegerField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name or self.file.name
