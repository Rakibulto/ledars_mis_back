from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from authentication.models import User
from .models.office_models import OfficeStaff
from .models.quotation_models import VendorQuotation
from .models.comparative_models import (
    ComparativeStatement,
    ComparativeVendorEvaluation,
    ComparativeVendorFinancial,
    ComparativeLineItem,
    ComparativeNotificationLog,
)
from .models.rfq_models import RFQ
from .models.award_models import Award, AwardNotification
from .models.work_order_models import WorkOrder
from .models.grn_models import GoodsReceiptNote
from .models.payment_requisition_models import PaymentRequisition
from .models.treasury_models import TreasuryProcessing, PaymentRecord, PaymentTimeline
from .models.notification_models import ProcurementNotification
from .models.settings_models import UserManagement


def _create_notification(
    recipient,
    title,
    message,
    notification_type,
    priority="Medium",
    reference_type=None,
    reference_id=None,
):
    """Helper to create procurement notifications."""
    if recipient is None:
        return

    ProcurementNotification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        priority=priority,
        reference_type=reference_type,
        reference_id=reference_id,
    )


# ── Quotation signals ──────────────────────────────────
@receiver(post_save, sender=VendorQuotation)
def quotation_status_changed(sender, instance, created, **kwargs):
    if created:
        return
    if instance.status == "Accepted":
        _create_notification(
            recipient=instance.created_by,
            title=f"Quotation {instance.quotation_number} Accepted",
            message=f"Your quotation for RFQ {instance.rfq.rfq_number} has been accepted.",
            notification_type="Quotation",
            reference_type="VendorQuotation",
            reference_id=instance.id,
        )


# ── Award signals ───────────────────────────────────────
@receiver(post_save, sender=Award)
def award_created_signal(sender, instance, created, **kwargs):
    if not created or not instance.vendor_profile:
        return

    AwardNotification.objects.get_or_create(
        award=instance,
        notification_type="Award",
        vendor_profile=instance.vendor_profile,
        defaults={
            "message": f"You have been awarded for RFQ {instance.rfq.rfq_number}.",
        },
    )


# ── Work Order signals ─────────────────────────────────
@receiver(post_save, sender=WorkOrder)
def work_order_status_changed(sender, instance, created, **kwargs):
    if not created and instance.status == "Completed":
        _create_notification(
            recipient=instance.created_by,
            title=f"Work Order {instance.wo_number} Completed",
            message=f"Work order {instance.wo_number} has been marked as completed.",
            notification_type="Work Order",
            priority="High",
            reference_type="WorkOrder",
            reference_id=instance.id,
        )


# ── GRN signals ─────────────────────────────────────────
@receiver(post_save, sender=GoodsReceiptNote)
def grn_verified_signal(sender, instance, created, **kwargs):
    if not created and instance.status == "Verified":
        _create_notification(
            recipient=instance.created_by,
            title=f"GRN {instance.grn_number} Verified",
            message=f"GRN {instance.grn_number} has been verified.",
            notification_type="GRN",
            reference_type="GoodsReceiptNote",
            reference_id=instance.id,
        )


# ── Payment Requisition signals ─────────────────────────
@receiver(post_save, sender=PaymentRequisition)
def payment_requisition_status_changed(sender, instance, created, **kwargs):
    if not created and instance.status == "Approved":
        _create_notification(
            recipient=instance.created_by,
            title=f"PRF {instance.prf_number} Approved",
            message=f"Payment requisition {instance.prf_number} has been approved.",
            notification_type="Payment",
            priority="High",
            reference_type="PaymentRequisition",
            reference_id=instance.id,
        )


# ── Treasury / Payment signals ─────────────────────────
@receiver(post_save, sender=PaymentRecord)
def payment_record_completed(sender, instance, created, **kwargs):
    if instance.status == "Completed":
        treasury = instance.treasury_processing
        prf = treasury.payment_requisition
        remarks = (
            f"Payment {instance.reference_number} completed via {instance.payment_method}."
        )

        # Create a single completion entry when a record reaches the completed state.
        PaymentTimeline.objects.get_or_create(
            payment_requisition=prf,
            stage="Payment Completed",
            remarks=remarks,
            defaults={"performed_by": instance.processed_by},
        )

        _create_notification(
            recipient=prf.created_by,
            title=f"Payment Completed for {prf.prf_number}",
            message=f"Payment of {instance.amount} has been processed.",
            notification_type="Payment",
            priority="High",
            reference_type="PaymentRecord",
            reference_id=instance.id,
        )


@receiver(post_save, sender=User)
def sync_user_management_profile(sender, instance, created, **kwargs):
    try:
        profile = instance.user_management_profile
    except UserManagement.DoesNotExist:
        return

    changed_fields = []
    desired_status = "active" if instance.is_active else "inactive"
    if profile.status != desired_status:
        profile.status = desired_status
        changed_fields.append("status")

    if profile.role_id != instance.role_id:
        profile.role = instance.role
        changed_fields.append("role")

    if profile.department_id != getattr(instance, "department_id", None):
        profile.department = getattr(instance, "department", None)
        changed_fields.append("department")

    if profile.username != instance.username:
        profile.username = instance.username
        changed_fields.append("username")

    if profile.email != instance.email:
        profile.email = instance.email
        changed_fields.append("email")

    if changed_fields:
        profile.save(update_fields=changed_fields)


@receiver(post_save, sender=UserManagement)
def sync_auth_user_fields(sender, instance, created, **kwargs):
    if not instance.user:
        return

    auth_user = instance.user
    changed_fields = []

    desired_is_active = instance.status == "active"
    if auth_user.is_active != desired_is_active:
        auth_user.is_active = desired_is_active
        changed_fields.append("is_active")

    if auth_user.role_id != getattr(instance, "role_id", None):
        auth_user.role = instance.role
        changed_fields.append("role")

    if auth_user.department_id != getattr(instance, "department_id", None):
        auth_user.department = instance.department
        changed_fields.append("department")

    if changed_fields:
        auth_user.save(update_fields=changed_fields)


@receiver(m2m_changed, sender=OfficeStaff.user.through)
def update_office_staff_count(
    sender, instance, action, reverse, model, pk_set, **kwargs
):
    if action not in ["post_add", "post_remove", "post_clear"]:
        return

    if reverse:
        if not pk_set:
            return
        for office_staff in OfficeStaff.objects.filter(pk__in=pk_set):
            if office_staff.office:
                office_staff.office.update_staff_count()
    else:
        if instance.office:
            instance.office.update_staff_count()


def _rfq_is_ready_for_automatic_comparative(rfq):
    # Only hard-block truly incomplete or cancelled RFQs.
    # "Open" and "Published" are intentionally allowed: when the submission_deadline
    # has passed the RFQ is still in "Open" status (nothing auto-transitions it),
    # so excluding "Open" here would silently suppress all auto-CS creation.
    if rfq.status in ("Draft", "Cancelled"):
        return False
    if not rfq.submission_deadline:
        return False
    # Deadline has not passed yet — too early to create CS.
    if rfq.submission_deadline > timezone.now():
        return False
    if rfq.comparative_statements.exists():
        return False
    return True


def _collect_submissions_and_profiles(rfq):
    submissions = list(
        rfq.vendor_submissions.filter(status="submitted")
        .select_related("financial_proposal")
        .prefetch_related("financial_proposal__items")
    )
    if not submissions:
        return submissions, {}

    try:
        from vendorportal.models.models import VendorProfile

        vendor_ids = [s.vendor_id for s in submissions if s.vendor_id]
        profiles = {vp.id: vp for vp in VendorProfile.objects.filter(id__in=vendor_ids)}
    except Exception:
        profiles = {}

    return submissions, profiles


def _create_comparative_statement(rfq, submissions, profiles):
    from django.db import transaction as _tx

    submission_count = len(submissions)
    with _tx.atomic():
        cs = ComparativeStatement.objects.create(
            rfq=rfq,
            title=rfq.rfq_title,
            auto_extracted=True,
            extraction_date=timezone.now(),
            extraction_source=(
                f"{rfq.rfq_number} Vendor Financial Proposals "
                f"({submission_count} submission{'s' if submission_count != 1 else ''})"
            ),
        )

        for submission in submissions:
            vp = profiles.get(submission.vendor_id)
            if not vp:
                continue

            fp = getattr(submission, "financial_proposal", None)

            ComparativeVendorFinancial.objects.get_or_create(
                comparative=cs,
                vendor=vp,
                defaults=dict(
                    subtotal=fp.sub_total if fp else 0,
                    vat=fp.vat if fp else 0,
                    ait=0,
                    delivery=fp.delivery_charge if fp else 0,
                    grand_total=fp.grand_total if fp else 0,
                ),
            )

            ComparativeVendorEvaluation.objects.get_or_create(
                comparative=cs,
                vendor=vp,
                defaults={"total_score": 0, "is_recommended": False},
            )

            if fp:
                for fi in fp.items.all():
                    rfq_line = rfq.line_items.filter(id=fi.line_item_id).first()
                    ComparativeLineItem.objects.create(
                        comparative=cs,
                        item=rfq_line.item if rfq_line else None,
                        vendor=vp,
                        quoted_price=fi.unit_price,
                        quantity=fi.qty,
                        total_price=fi.total,
                    )

        ComparativeNotificationLog.objects.create(
            comparative=cs,
            event="CS Auto-Generated",
            recipients="System",
            channel="System",
        )

    return cs


def ensure_comparative_statement_for_rfq(rfq):
    if not _rfq_is_ready_for_automatic_comparative(rfq):
        return None

    submissions, profiles = _collect_submissions_and_profiles(rfq)
    if not submissions:
        return None

    return _create_comparative_statement(rfq, submissions, profiles)


def auto_close_expired_rfqs(as_of=None):
    """Transition any RFQ whose deadline has passed from published/open → closed."""
    as_of = as_of or timezone.now()
    updated = RFQ.objects.filter(
        submission_deadline__lte=as_of,
        status__in=("published", "open"),
    ).update(status="closed")
    return updated


def create_comparative_statements_for_expired_rfqs(as_of=None):
    from django.db.models import Q

    as_of = as_of or timezone.now()
    auto_close_expired_rfqs(as_of)
    # Only exclude Draft and Cancelled — "Open"/"Published" are valid because
    # status is not auto-transitioned when the deadline passes.
    rfqs = RFQ.objects.filter(submission_deadline__lte=as_of).exclude(
        status__in=("draft", "cancelled")
    )

    created_count = 0
    for rfq in rfqs:
        if ensure_comparative_statement_for_rfq(rfq):
            created_count += 1
    return created_count


# ── RFQ → Auto-create Comparative Statement ────────────────────────────────
@receiver(post_save, sender=RFQ)
def auto_create_comparative_statement(sender, instance, created, **kwargs):
    ensure_comparative_statement_for_rfq(instance)
