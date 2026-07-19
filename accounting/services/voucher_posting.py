from django.db import transaction
from django.utils import timezone

from accounting.models import AuditLog, Voucher
from accounting.services.bank_adjustment_service import (
    adjust_banks_for_journal_items,
    reverse_bank_transactions_for_voucher,
)
from accounting.services.exceptions import ValidationPostingError
from accounting.services.posting_service import (
    create_journal_entry_from_lines,
    reverse_journal_entry,
)
from accounting.services.validators import (
    get_accounting_settings,
    validate_voucher_ready_to_post,
)


def _write_audit(*, voucher, user, action, description, changes=None):
    AuditLog.objects.create(
        model_name="Voucher",
        object_id=voucher.pk,
        action=action,
        description=description,
        changes=changes or {},
        user=user,
    )


def post_voucher(voucher, user=None):
    """
    Atomically post a voucher:
      validate → JE + GL → bank adjustment → mark posted → audit
    """
    settings_obj = get_accounting_settings()

    with transaction.atomic():
        locked = (
            Voucher.objects.select_for_update()
            .select_related("journal", "ngo_project", "currency")
            .prefetch_related("lines__account")
            .get(pk=voucher.pk)
        )

        # Relaxed status when auto_post_vouchers is on
        if settings_obj.auto_post_vouchers and locked.status in ("draft", "pending"):
            locked.status = "approved"
            locked.approved_by = user
            locked.approved_at = timezone.now()
            locked.save(update_fields=["status", "approved_by", "approved_at"])

        lines = validate_voucher_ready_to_post(locked, settings_obj=settings_obj)

        entry, items = create_journal_entry_from_lines(
            journal=locked.journal,
            date=locked.date,
            narration=locked.narration,
            lines=lines,
            user=user,
            source_document=locked.voucher_number,
            ngo_project=locked.ngo_project,
            currency=locked.currency,
            exchange_rate=locked.exchange_rate,
            is_auto_generated=True,
        )

        bank_txns = adjust_banks_for_journal_items(
            journal_items=items,
            voucher=locked,
            ngo_project=locked.ngo_project,
            reference=locked.voucher_number,
            description=locked.narration or locked.voucher_number,
            date=locked.date,
        )

        locked.journal_entry = entry
        locked.status = "posted"
        locked.save(update_fields=["journal_entry", "status", "updated_at"])

        _write_audit(
            voucher=locked,
            user=user,
            action="post",
            description=f"Posted voucher {locked.voucher_number} → {entry.reference}",
            changes={
                "journal_entry": entry.reference,
                "bank_transactions": [t.pk for t in bank_txns],
            },
        )

        return locked, entry, bank_txns


def reverse_voucher(voucher, user=None, remarks=""):
    """
    Reverse a posted voucher: reverse bank txns + reverse JE; mark cancelled.
    Never deletes posted history.
    """
    with transaction.atomic():
        locked = (
            Voucher.objects.select_for_update()
            .select_related("journal_entry")
            .get(pk=voucher.pk)
        )
        if locked.status != "posted" or not locked.journal_entry_id:
            raise ValidationPostingError(
                "Only posted vouchers can be reversed.",
                code="not_posted",
            )

        reverse_bank_transactions_for_voucher(locked, user=user)
        reversal_entry, _ = reverse_journal_entry(
            locked.journal_entry,
            user=user,
            narration_prefix=f"Reversal of voucher {locked.voucher_number}",
        )

        locked.status = "cancelled"
        locked.save(update_fields=["status", "updated_at"])

        _write_audit(
            voucher=locked,
            user=user,
            action="cancel",
            description=(
                f"Reversed voucher {locked.voucher_number} "
                f"→ {reversal_entry.reference}. {remarks}"
            ).strip(),
            changes={"reversal_entry": reversal_entry.reference},
        )
        return locked, reversal_entry
