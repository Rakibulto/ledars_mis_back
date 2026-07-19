from decimal import Decimal

from django.db.models import Q

from accounting.models import AccountingSettings, FiscalPeriod, LockDate
from accounting.services.exceptions import ValidationPostingError


def _as_decimal(value):
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def get_accounting_settings():
    settings_obj, _ = AccountingSettings.objects.get_or_create(pk=1)
    return settings_obj


def validate_lines_balanced(lines, precision=2):
    """Ensure sum(debit) == sum(credit) for line dicts or model instances."""
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for line in lines:
        if isinstance(line, dict):
            debit = _as_decimal(line.get("debit", 0))
            credit = _as_decimal(line.get("credit", 0))
        else:
            debit = _as_decimal(line.debit)
            credit = _as_decimal(line.credit)
        if debit and credit:
            raise ValidationPostingError(
                "A line cannot have both debit and credit amounts.",
                code="line_both_sides",
            )
        if debit < 0 or credit < 0:
            raise ValidationPostingError(
                "Debit and credit amounts must be non-negative.",
                code="negative_amount",
            )
        total_debit += debit
        total_credit += credit

    quant = Decimal("1").scaleb(-precision)
    total_debit = total_debit.quantize(quant)
    total_credit = total_credit.quantize(quant)

    if total_debit != total_credit:
        raise ValidationPostingError(
            f"Debit and Credit must be equal (Dr {total_debit} / Cr {total_credit}).",
            code="unbalanced",
        )
    if total_debit == 0:
        raise ValidationPostingError(
            "Voucher must have at least one non-zero line.",
            code="empty_lines",
        )
    return total_debit, total_credit


def validate_period_open(entry_date, settings_obj=None):
    """Reject posting when hard/soft lock or closed fiscal period applies."""
    settings_obj = settings_obj or get_accounting_settings()

    if settings_obj.lock_date and entry_date <= settings_obj.lock_date:
        raise ValidationPostingError(
            f"This period is locked (lock date {settings_obj.lock_date}).",
            code="settings_lock",
        )

    hard_or_soft = (
        LockDate.objects.filter(is_active=True, lock_date__gte=entry_date)
        .filter(Q(type="hard") | Q(type="soft"))
        .order_by("-lock_date")
        .first()
    )
    if hard_or_soft and entry_date <= hard_or_soft.lock_date:
        raise ValidationPostingError(
            f"This period is locked ({hard_or_soft.name} – {hard_or_soft.lock_date}).",
            code="lock_date",
        )

    closed_period = FiscalPeriod.objects.filter(
        start_date__lte=entry_date,
        end_date__gte=entry_date,
        status="closed",
    ).first()
    if closed_period:
        raise ValidationPostingError(
            f"Fiscal period '{closed_period.name}' is closed.",
            code="period_closed",
        )


def is_bank_cash_account(account):
    """Global bank/cash CoA ledgers (shared across projects)."""
    if not account:
        return False
    liquidity = getattr(getattr(account, "account_type", None), "liquidity_type", None)
    if liquidity == "bank_cash":
        return True
    # Fallback: linked bank master implies bank/cash
    if hasattr(account, "bank_accounts") and account.bank_accounts.exists():
        return True
    return False


def validate_voucher_account_scope(voucher, lines=None):
    """
    Project vouchers may only use:
    - accounts belonging to the same ngo_project, or
    - global bank/cash accounts (ngo_project null + bank_cash).
    """
    lines = lines if lines is not None else list(
        voucher.lines.select_related("account", "account__account_type").all()
    )
    voucher_project_id = voucher.ngo_project_id

    for line in lines:
        account = line.account
        if not account:
            continue
        if is_bank_cash_account(account):
            if account.ngo_project_id is not None:
                raise ValidationPostingError(
                    f"Bank/cash account {account.code} must be global, not project-scoped.",
                    code="bank_not_global",
                )
            continue
        if voucher_project_id and account.ngo_project_id != voucher_project_id:
            raise ValidationPostingError(
                f"Account {account.code} does not belong to this project's chart of accounts.",
                code="account_project_mismatch",
            )
        if not voucher_project_id and account.ngo_project_id is not None:
            raise ValidationPostingError(
                f"Account {account.code} is project-scoped but voucher has no NGO project.",
                code="account_project_mismatch",
            )


def validate_voucher_ready_to_post(voucher, settings_obj=None):
    """Status, project, lines, and period checks before posting."""
    settings_obj = settings_obj or get_accounting_settings()

    if voucher.status == "posted" or voucher.journal_entry_id:
        raise ValidationPostingError(
            "This voucher is already posted.",
            code="already_posted",
        )

    if voucher.status == "cancelled":
        raise ValidationPostingError(
            "Cancelled vouchers cannot be posted.",
            code="cancelled",
        )

    if voucher.status != "approved":
        raise ValidationPostingError(
            "Only approved vouchers can be posted.",
            code="not_approved",
        )

    if settings_obj.use_ngo_project_required and not voucher.ngo_project_id:
        raise ValidationPostingError(
            "Select an NGO project before posting.",
            code="ngo_project_required",
        )

    lines = list(
        voucher.lines.select_related("account", "account__account_type").all()
    )
    if not lines:
        raise ValidationPostingError(
            "Voucher has no lines.",
            code="no_lines",
        )
    for line in lines:
        if not line.account_id:
            raise ValidationPostingError(
                "Every voucher line must have an account.",
                code="missing_account",
            )

    validate_lines_balanced(lines, precision=settings_obj.decimal_precision or 2)
    validate_period_open(voucher.date, settings_obj=settings_obj)
    validate_voucher_account_scope(voucher, lines=lines)
    return lines
