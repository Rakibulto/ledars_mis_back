from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models.voucher_models import Voucher, VoucherApproval
from .models.journal_models import JournalEntry
from .models.payable_models import Bill
from .models.receivable_models import Invoice
from .models.settings_models import AuditLog


# ── Audit logging ──────────────────────────────────────────
def _log_audit(instance, action, user=None, changes=None):
    """Create an audit log entry."""
    AuditLog.objects.create(
        model_name=instance.__class__.__name__,
        object_id=instance.pk,
        description=str(instance)[:200],
        action=action,
        user=user,
        changes=changes or {},
    )


# ── Voucher signals ───────────────────────────────────────
@receiver(post_save, sender=Voucher)
def voucher_post_save(sender, instance, created, **kwargs):
    if created:
        _log_audit(instance, "create", user=instance.created_by)


@receiver(post_save, sender=VoucherApproval)
def voucher_approval_post_save(sender, instance, created, **kwargs):
    if created and instance.status == "approved":
        _log_audit(
            instance.voucher,
            "update",
            user=instance.approver,
            changes={"status": "approved", "approved_by": str(instance.approver)},
        )


# ── Journal Entry signals ─────────────────────────────────
@receiver(post_save, sender=JournalEntry)
def journal_entry_post_save(sender, instance, created, **kwargs):
    if created:
        _log_audit(instance, "create")
    elif instance.status == "posted":
        _log_audit(
            instance,
            "update",
            user=instance.posted_by,
            changes={"status": "posted"},
        )


# ── Bill overdue check ────────────────────────────────────
@receiver(pre_save, sender=Bill)
def bill_overdue_check(sender, instance, **kwargs):
    import datetime
    due = instance.due_date
    if isinstance(due, str):
        try:
            due = datetime.date.fromisoformat(due)
        except (ValueError, TypeError):
            due = None
    if not due or due >= timezone.now().date():
        return
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            if old.status != instance.status:
                return
        except sender.DoesNotExist:
            pass
    if instance.status in ("approved", "partial"):
        instance.status = "overdue"


# ── Invoice overdue check ─────────────────────────────────
@receiver(pre_save, sender=Invoice)
def invoice_overdue_check(sender, instance, **kwargs):
    import datetime
    due = instance.due_date
    if isinstance(due, str):
        try:
            due = datetime.date.fromisoformat(due)
        except (ValueError, TypeError):
            due = None
    if (
        due
        and due < timezone.now().date()
        and instance.status in ("sent", "partial")
    ):
        instance.status = "overdue"
