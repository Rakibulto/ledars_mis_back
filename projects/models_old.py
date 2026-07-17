from django.db import models
from authentication.models import User
from employee.models import Employee

class Project(models.Model):

    STATUS_CHOICES = (
        ('Planning', 'Planning'),
        ('Active', 'Active'),
        ('On Hold', 'On Hold'),
        ('Completed', 'Completed'),
    )

    code = models.CharField(max_length=100)
    name = models.CharField(max_length=255, null=True, blank=True)
    donor = models.CharField(max_length=255, null=True, blank=True)
    budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    manager = models.CharField(max_length=255, null=True, blank=True)

    location = models.JSONField(default=list, blank=True)   # string[]
    objectives = models.JSONField(default=list, blank=True) # string[]
    activity_list = models.JSONField(default=list, null=True, blank=True)
    # beneficiaries = models.IntegerField(null=True, blank=True)
    # target_beneficiaries = models.IntegerField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    

class ProjectActivity(models.Model):
    TYPE_CHOICES = (
        ('Monthly', 'Monthly'),
        ('Quarterly', 'Quarterly'),
        ('Annual', 'Annual'),
        ('One-time', 'One-time'),
    )
    STATUS_CHOICES = (
        ('Not Started', 'Not Started'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Overdue', 'Overdue'),
        ('Cancelled', 'Cancelled'),
    )
    PRIORITY_CHOICES = (
        ('High', 'High'),
        ('Medium', 'Medium'),
        ('Low', 'Low'),
    )
    project = models.ForeignKey(
        Project,
        related_name='activities',
        on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='Monthly')
    responsible_person = models.CharField(max_length=255, null=True, blank=True)
    department = models.ForeignKey('employee.Employee', on_delete=models.SET_NULL, null=True, blank=True)

    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Not Started')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    progress = models.PositiveIntegerField(default=0)
    budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.project.name} - {self.title}"
    

class Notification(models.Model):

    TYPE_CHOICES = (
        ('reminder', 'Reminder'),
        ('completion', 'Completion'),
        ('overdue', 'Overdue'),
        ('approval', 'Approval'),
    )


    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE
    )

    activity = models.ForeignKey(
        ProjectActivity,
        on_delete=models.CASCADE
    )

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    message = models.TextField()
    date = models.DateTimeField()
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.type} - {self.project.name}"