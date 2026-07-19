from decimal import Decimal

from django.db.models import F
from django.utils import timezone

from accounting.models import Account, JournalEntry, JournalItem
from accounting.services.exceptions import ValidationPostingError


def create_journal_entry_from_lines(
    *,
    journal,
    date,
    narration,
    lines,
    user=None,
    source_document="",
    ngo_project=None,
    currency=None,
    exchange_rate=None,
    is_auto_generated=True,
):
    """
    Create a posted JournalEntry with JournalItems and update Account.current_balance.

    `lines` is an iterable of dicts:
      {account, debit, credit, label?, analytic_account?, cost_center?, tax?}
    or objects with those attributes.
    Must be called inside transaction.atomic().
    """
    if not journal:
        raise ValidationPostingError("Journal is required.", code="missing_journal")

    entry = JournalEntry.objects.create(
        journal=journal,
        date=date,
        narration=narration or "",
        status="posted",
        is_auto_generated=is_auto_generated,
        source_document=source_document or "",
        ngo_project=ngo_project,
        currency=currency,
        exchange_rate=exchange_rate or Decimal("1"),
        created_by=user,
        posted_by=user,
        posted_at=timezone.now(),
    )

    total_debit = Decimal("0")
    total_credit = Decimal("0")
    created_items = []

    for line in lines:
        if isinstance(line, dict):
            account = line["account"]
            debit = Decimal(str(line.get("debit") or 0))
            credit = Decimal(str(line.get("credit") or 0))
            label = line.get("label") or line.get("description") or ""
            analytic_account = line.get("analytic_account")
            cost_center = line.get("cost_center")
            tax = line.get("tax")
        else:
            account = line.account
            debit = Decimal(str(line.debit or 0))
            credit = Decimal(str(line.credit or 0))
            label = getattr(line, "description", None) or getattr(line, "label", "") or ""
            analytic_account = getattr(line, "analytic_account", None)
            cost_center = getattr(line, "cost_center", None)
            tax = getattr(line, "tax", None)

        account_id = account.pk if hasattr(account, "pk") else account
        item = JournalItem.objects.create(
            journal_entry=entry,
            account_id=account_id,
            label=label,
            debit=debit,
            credit=credit,
            balance=debit - credit,
            analytic_account=analytic_account,
            cost_center=cost_center,
            tax=tax,
        )
        created_items.append(item)

        Account.objects.filter(pk=account_id).update(
            current_balance=F("current_balance") + debit - credit
        )
        total_debit += debit
        total_credit += credit

    entry.total_debit = total_debit
    entry.total_credit = total_credit
    entry.save(update_fields=["total_debit", "total_credit"])
    return entry, created_items


def reverse_journal_entry(entry, user=None, narration_prefix="Reversal of"):
    """
    Create a reversing posted JE and reverse GL balances.
    Marks original entry as cancelled. Must run inside atomic().
    """
    if entry.status != "posted":
        raise ValidationPostingError(
            "Only posted journal entries can be reversed.",
            code="not_posted",
        )

    reverse_lines = []
    for item in entry.items.select_related("account").all():
        reverse_lines.append(
            {
                "account": item.account,
                "debit": item.credit,
                "credit": item.debit,
                "label": f"Reversal: {item.label}",
                "analytic_account": item.analytic_account,
                "cost_center": item.cost_center,
                "tax": item.tax,
            }
        )

    reversal, items = create_journal_entry_from_lines(
        journal=entry.journal,
        date=timezone.now().date(),
        narration=f"{narration_prefix} {entry.reference}",
        lines=reverse_lines,
        user=user,
        source_document=f"REV-{entry.reference}",
        ngo_project=entry.ngo_project,
        currency=entry.currency,
        exchange_rate=entry.exchange_rate,
        is_auto_generated=True,
    )

    entry.status = "cancelled"
    entry.save(update_fields=["status", "updated_at"])
    return reversal, items
