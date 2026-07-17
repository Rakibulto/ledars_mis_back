from django.db import models
from django.utils import timezone


class CaseFile(models.Model):
    PRIORITY_CHOICES = [
        ("Critical", "Critical"),
        ("High", "High"),
        ("Medium", "Medium"),
        ("Low", "Low"),
    ]
    
    STATUS_CHOICES = [
        ("Open", "Open"),
        ("In Progress", "In Progress"),
        ("Resolved", "Resolved"),
        ("Closed", "Closed"),
    ]
    beneficiary = models.ForeignKey(
        "beneficiary.Beneficiary",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="case_files",
    )
    case_type = models.CharField(max_length=255, null=True, blank=True)
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="Medium"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Open")
    case_worker = models.ForeignKey(
        "employee.Employee", on_delete=models.SET_NULL, null=True, blank=True
    )
    opened_date = models.DateField(null=True, blank=True)
    last_update = models.DateTimeField(auto_now=True)
    description = models.TextField(null=True, blank=True)
    interventions = models.IntegerField(default=0)
    next_follow_up = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Case #{self.id} - {self.case_type}"


class ProtectionCase(models.Model):
    TYPE_CHOICES = [
        ("GBV", "GBV"),
        ("Child Protection", "Child Protection"),
        ("Trafficking Risk", "Trafficking Risk"),
        ("Other", "Other"),
    ]
    RISK_LEVEL_CHOICES = [
        ("Critical", "Critical"),
        ("High", "High"),
        ("Medium", "Medium"),
        ("Low", "Low"),
    ]
    STATUS_CHOICES = [
        ("Open", "Open"),
        ("Under Investigation", "Under Investigation"),
        ("Resolved", "Resolved"),
        ("Closed", "Closed"),
    ]
    reference = models.CharField(max_length=50, unique=True, blank=True)
    beneficiary = models.ForeignKey(
        "beneficiary.Beneficiary", on_delete=models.SET_NULL, null=True, blank=True
    )
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, null=True, blank=True)
    risk_level = models.CharField(
        max_length=20, choices=RISK_LEVEL_CHOICES, null=True, blank=True
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Open")
    case_worker = models.ForeignKey(
        "employee.Employee", on_delete=models.SET_NULL, null=True, blank=True
    )
    opened_date = models.DateField(null=True, blank=True)
    safe_space_referred = models.BooleanField(default=False)
    legal_action = models.CharField(max_length=100, null=True, blank=True)
    psychosocial_sessions = models.PositiveIntegerField(default=0)
    last_update = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().year
            last = (
                ProtectionCase.objects.filter(reference__startswith=f"PC-{year}")
                .order_by("-id")
                .first()
            )
            seq = int(last.reference.split("-")[-1]) + 1 if last else 1
            self.reference = f"PC-{year}-{str(seq).zfill(4)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.reference


class ConsentRecord(models.Model):
    CONSENT_TYPE_CHOICES = [
        ("Data Collection", "Data Collection"),
        ("Photo/Video", "Photo/Video"),
        ("Data Sharing", "Data Sharing"),
        ("Program Participation", "Program Participation"),
    ]
    DATA_SHARING_CHOICES = [
        ("Full", "Full"),
        ("Partial", "Partial"),
        ("Anonymized Only", "Anonymized Only"),
        ("None", "None"),
    ]
    beneficiary = models.ForeignKey(
        "beneficiary.Beneficiary", on_delete=models.SET_NULL, null=True, blank=True
    )
    consent_type = models.CharField(
        max_length=50, choices=CONSENT_TYPE_CHOICES, null=True, blank=True
    )
    granted = models.BooleanField(default=True)
    date = models.DateField(null=True, blank=True)
    expiry = models.DateField(null=True, blank=True)
    collected_by = models.CharField(max_length=255, null=True, blank=True)
    photo_consent = models.BooleanField(default=False)
    data_sharing = models.CharField(
        max_length=30, choices=DATA_SHARING_CHOICES, default="None"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"Consent - {self.beneficiary} - {self.consent_type}"


class SafeguardingIncident(models.Model):
    SEVERITY_CHOICES = [
        ("Critical", "Critical"),
        ("High", "High"),
        ("Medium", "Medium"),
        ("Low", "Low"),
    ]
    STATUS_CHOICES = [
        ("Reported", "Reported"),
        ("Under Investigation", "Under Investigation"),
        ("Action Taken", "Action Taken"),
        ("Resolved", "Resolved"),
        ("Closed", "Closed"),
    ]
    reference = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField(null=True, blank=True)
    type = models.CharField(max_length=100, null=True, blank=True)
    severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, null=True, blank=True
    )
    location = models.CharField(max_length=255, null=True, blank=True)
    reporter = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Reported")
    action_taken = models.TextField(null=True, blank=True)
    investigation_lead = models.CharField(max_length=255, null=True, blank=True)
    resolution_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().year
            last = (
                SafeguardingIncident.objects.filter(reference__startswith=f"SG-{year}")
                .order_by("-id")
                .first()
            )
            seq = int(last.reference.split("-")[-1]) + 1 if last else 1
            self.reference = f"SG-{year}-{str(seq).zfill(4)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.reference
