from decimal import Decimal

from django.db.models import F

from accounting.models import BankAccount, BankTransaction
from accounting.services.exceptions import ValidationPostingError


def _bank_accounts_by_coa(account_ids):
    """Map CoA account_id -> BankAccount for linked bank/cash books."""
    banks = BankAccount.objects.select_for_update().filter(
        account_id__in=account_ids, status="active"
    )
    return {b.account_id: b for b in banks}


def adjust_banks_for_journal_items(
    *,
    journal_items,
    voucher=None,
    ngo_project=None,
    reference="",
    description="",
    date=None,
):
    """
    For each journal item whose account is linked to a BankAccount:
      - debit on bank ledger  -> bank withdrawal (transaction_type=debit), balance decreases
      - credit on bank ledger -> bank deposit (transaction_type=credit), balance increases

    Must be called inside transaction.atomic().
    Returns list of created BankTransaction rows.
    """
    account_ids = [item.account_id for item in journal_items if item.account_id]
    if not account_ids:
        return []

    bank_map = _bank_accounts_by_coa(account_ids)
    if not bank_map:
        return []

    created = []
    for item in journal_items:
        bank = bank_map.get(item.account_id)
        if not bank:
            continue
        if not bank.account_id:
            raise ValidationPostingError(
                f"Bank account '{bank.name}' is not linked to a CoA account.",
                code="bank_missing_coa",
            )

        debit = Decimal(str(item.debit or 0))
        credit = Decimal(str(item.credit or 0))
        if debit == 0 and credit == 0:
            continue

        # Asset bank ledger: debit = money in, credit = money out
        if debit > 0:
            txn_type = "credit"  # deposit
            amount = debit
            delta = debit
        else:
            txn_type = "debit"  # withdrawal
            amount = credit
            delta = -credit

        BankAccount.objects.filter(pk=bank.pk).update(
            current_balance=F("current_balance") + delta
        )
        bank.refresh_from_db(fields=["current_balance"])

        txn = BankTransaction.objects.create(
            bank_account_id=bank.pk,
            date=date or (voucher.date if voucher else None),
            description=description
            or (item.label if item.label else f"Auto from {reference}"),
            reference=reference or "",
            transaction_type=txn_type,
            amount=amount,
            running_balance=bank.current_balance,
            journal_item=item,
            ngo_project=ngo_project or (voucher.ngo_project if voucher else None),
            voucher=voucher,
            is_system_generated=True,
            status="unreconciled",
        )
        created.append(txn)

    return created


def reverse_bank_transactions_for_voucher(voucher, user=None):
    """
    Reverse system-generated bank txns for a voucher and restore balances.
    Must run inside atomic().
    """
    txns = list(
        BankTransaction.objects.select_for_update()
        .filter(voucher=voucher, is_system_generated=True)
        .select_related("bank_account")
    )
    reversed_txns = []
    for txn in txns:
        # Original GL credit (withdrawal) used BankTransaction type=debit → reverse by deposit
        if txn.transaction_type == "debit":
            rev_type = "credit"
            delta = txn.amount
        else:
            rev_type = "debit"
            delta = -txn.amount

        BankAccount.objects.filter(pk=txn.bank_account_id).update(
            current_balance=F("current_balance") + delta
        )
        txn.bank_account.refresh_from_db(fields=["current_balance"])

        rev = BankTransaction.objects.create(
            bank_account_id=txn.bank_account_id,
            date=timezone_today(),
            description=f"Reversal of {txn.reference or txn.pk}: {txn.description}",
            reference=f"REV-{txn.reference or txn.pk}",
            transaction_type=rev_type,
            amount=txn.amount,
            running_balance=txn.bank_account.current_balance,
            ngo_project=txn.ngo_project,
            voucher=voucher,
            is_system_generated=True,
            status="unreconciled",
        )
        reversed_txns.append(rev)
    return reversed_txns


def timezone_today():
    from django.utils import timezone

    return timezone.now().date()
