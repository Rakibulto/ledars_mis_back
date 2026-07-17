from django.db import models
from django.conf import settings


SOURCE_CHOICES = [
    ('social_media', 'Social Media'),
    ('youtube', 'YouTube'),
    ('friends', 'Friends'),
    ('referral', 'Referral'),
    ('website', 'Website'),
    ('cold_call', 'Cold Call'),
    ('email_campaign', 'Email Campaign'),
    ('other', 'Other'),
]

PROJECT_TYPE_CHOICES = [
    ('residential', 'Residential'),
    ('commercial', 'Commercial'),
    ('industrial', 'Industrial'),
    ('renovation', 'Renovation'),
    ('interior', 'Interior'),
    ('other', 'Other'),
]

STATUS_CHOICES = [
    ('new', 'New'),
    ('contacted', 'Contacted'),
    ('qualified', 'Qualified'),
    ('proposal_sent', 'Proposal Sent'),
    ('negotiation', 'Negotiation'),
    ('won', 'Won'),
    ('lost', 'Lost'),
    ('on_hold', 'On Hold'),
]


class Lead(models.Model):
    lead_id = models.CharField(max_length=20, unique=True, blank=True)

    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True, null=True)
    country = models.CharField(max_length=100, default='Bangladesh')
    city = models.CharField(max_length=100, default='Dhaka')
    area = models.CharField(max_length=100, default='Uttara')
    address = models.TextField()
    source = models.CharField(max_length=100, blank=True, null=True, choices=SOURCE_CHOICES)
    link = models.CharField(max_length=500, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    project_name = models.CharField(max_length=255, blank=True, null=True)
    project_type = models.CharField(max_length=100, blank=True, null=True, choices=PROJECT_TYPE_CHOICES)
    customization = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, default='new', choices=STATUS_CHOICES)

    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_leads'
    )
    assigned_to = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_leads'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.lead_id} — {self.name}"

    def save(self, *args, **kwargs):
        if not self.lead_id:
            count = Lead.objects.count() + 1
            self.lead_id = f'LD-{count:04d}'
        super().save(*args, **kwargs)


class LeadProject(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='lead_projects')
    name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.lead.lead_id} - {self.name or 'N/A'}"


class LeadFollowUp(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='follow_ups')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    next_contact_date = models.DateField(blank=True, null=True)
    assigned_to = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='lead_follow_ups'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_follow_ups'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        assigned_names = ', '.join(
            u.get_full_name() or u.username for u in self.assigned_to.all()
        ) or 'Unassigned'
        return f"{self.title} — {assigned_names}"


class LeadFollowUpAttachment(models.Model):
    follow_up = models.ForeignKey(
        LeadFollowUp, on_delete=models.CASCADE, related_name='attachments'
    )
    file = models.FileField(upload_to='crm/followups/%Y/%m/')
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.IntegerField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name or self.file.name
