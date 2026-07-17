
from django.db import models
from django.core.validators import FileExtensionValidator
from django.conf import settings
from procurement.models.rfq_models import RFQ



class Invitation_rfq(models.Model):
    rfq_number = models.OneToOneField(
        RFQ, on_delete=models.CASCADE, related_name="invitation_rfq"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    # notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Submitted RFQ: {self.rfq_number.rfq_number}"
    

