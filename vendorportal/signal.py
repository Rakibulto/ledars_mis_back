from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from procurement.models.rfq_models import RFQ
from .models.invitation_rfq_models import Invitation_rfq
from .models.apply_rfq_models import VendorRFQSubmission


@receiver(post_save, sender=RFQ)
def create_submit_rfq(sender, instance, created, **kwargs):
    # শুধু তখনই submit_rfq তৈরি করো যদি RFQ নতুন হয় এবং status Published/ Open/ Awarded হয়
    if instance.status in {"Published", "Open", "Awarded"}:
        Invitation_rfq.objects.get_or_create(rfq_number=instance)


@receiver(post_save, sender=VendorRFQSubmission)
def auto_create_vendor_quotation(sender, instance, **kwargs):
    """Auto-create a VendorQuotation (and its quotation_number) when a vendor submits."""
    if instance.status != "submitted":
        return

    from vendorportal.models.models import VendorProfile
    from procurement.models.quotation_models import VendorQuotation

    try:
        profile = VendorProfile.objects.get(id=instance.vendor_id)
    except VendorProfile.DoesNotExist:
        return

    # Get or create VendorQuotation — quotation_number is auto-generated in save()
    VendorQuotation.objects.get_or_create(
        rfq=instance.rfq,
        vendor=profile,
        defaults={
            "submission_date": instance.submitted_at or timezone.now(),
            "status": "Submitted",
        },
    )


