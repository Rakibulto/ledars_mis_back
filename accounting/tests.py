"""
Unit tests for voucher posting validators and bank auto-adjustment.
Run: python manage.py test accounting.tests
"""

from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.contrib.auth import get_user_model

from accounting.models import (
    Account,
    AccountType,
    AccountingSettings,
    BankAccount,
    BankTransaction,
    Journal,
    LockDate,
    Voucher,
    VoucherLine,
)
from accounting.services.exceptions import ValidationPostingError
from accounting.services.validators import (
    validate_lines_balanced,
    validate_period_open,
    validate_voucher_ready_to_post,
)
from accounting.services.voucher_posting import post_voucher, reverse_voucher
from project_managements.models import ProjectManagementProject

User = get_user_model()


class ValidatorTests(TestCase):
    def test_balanced_lines_ok(self):
        total_d, total_c = validate_lines_balanced(
            [
                {"debit": "100.00", "credit": "0"},
                {"debit": "0", "credit": "100.00"},
            ]
        )
        self.assertEqual(total_d, Decimal("100.00"))
        self.assertEqual(total_c, Decimal("100.00"))

    def test_unbalanced_raises(self):
        with self.assertRaises(ValidationPostingError) as ctx:
            validate_lines_balanced(
                [
                    {"debit": "100", "credit": "0"},
                    {"debit": "0", "credit": "50"},
                ]
            )
        self.assertEqual(ctx.exception.code, "unbalanced")

    def test_lock_date_blocks(self):
        AccountingSettings.objects.get_or_create(pk=1)
        LockDate.objects.create(
            name="Hard close",
            type="hard",
            lock_date=date(2026, 6, 30),
            is_active=True,
        )
        with self.assertRaises(ValidationPostingError) as ctx:
            validate_period_open(date(2026, 6, 15))
        self.assertEqual(ctx.exception.code, "lock_date")


class VoucherPostingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="acct_tester@example.com",
            username="acct_tester",
            password="pass12345",
        )
        AccountingSettings.objects.get_or_create(pk=1)
        self.asset_type = AccountType.objects.create(
            name="Assets", classification="asset", liquidity_type="current"
        )
        self.bank_type, _ = AccountType.objects.get_or_create(
            name="Bank and Cash",
            defaults={
                "classification": "asset",
                "liquidity_type": "bank_cash",
                "is_active": True,
            },
        )
        if self.bank_type.liquidity_type != "bank_cash":
            self.bank_type.liquidity_type = "bank_cash"
            self.bank_type.classification = "asset"
            self.bank_type.save(update_fields=["liquidity_type", "classification"])
        self.expense_type = AccountType.objects.create(
            name="Expenses", classification="expense", liquidity_type="na"
        )
        self.bank_coa = Account.objects.create(
            code="1103",
            name="Cash at Bank",
            account_type=self.bank_type,
            current_balance=Decimal("1000.00"),
            opening_balance=Decimal("1000.00"),
        )
        self.expense_coa = Account.objects.create(
            code="5001",
            name="Office Expense",
            account_type=self.expense_type,
            current_balance=Decimal("0"),
        )
        self.bank = BankAccount.objects.create(
            name="Main Bank",
            bank_name="Test Bank",
            account_number="TB-001",
            account=self.bank_coa,
            opening_balance=Decimal("1000.00"),
            current_balance=Decimal("1000.00"),
            status="active",
            account_type="bank",
        )
        self.journal = Journal.objects.create(
            name="Bank Journal",
            code="BANK",
            journal_type="bank",
        )

    def _make_payment_voucher(self, amount="200.00", status="approved"):
        voucher = Voucher.objects.create(
            voucher_type="payment",
            journal=self.journal,
            date=date(2026, 7, 10),
            narration="Test payment",
            status=status,
            total_amount=Decimal(amount),
            created_by=self.user,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.expense_coa,
            description="Expense",
            debit=Decimal(amount),
            credit=Decimal("0"),
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.bank_coa,
            description="Bank",
            debit=Decimal("0"),
            credit=Decimal(amount),
        )
        return voucher

    def test_post_payment_adjusts_bank_and_gl(self):
        voucher = self._make_payment_voucher()
        locked, entry, bank_txns = post_voucher(voucher, user=self.user)

        self.assertEqual(locked.status, "posted")
        self.assertIsNotNone(locked.journal_entry_id)
        self.assertEqual(entry.status, "posted")
        self.assertEqual(len(bank_txns), 1)
        self.assertEqual(bank_txns[0].transaction_type, "debit")  # withdrawal

        self.bank.refresh_from_db()
        self.bank_coa.refresh_from_db()
        self.expense_coa.refresh_from_db()

        # Credit on bank asset → bank book decreases
        self.assertEqual(self.bank.current_balance, Decimal("800.00"))
        self.assertEqual(self.bank_coa.current_balance, Decimal("800.00"))
        self.assertEqual(self.expense_coa.current_balance, Decimal("200.00"))

    def test_unbalanced_cannot_post(self):
        voucher = Voucher.objects.create(
            voucher_type="payment",
            journal=self.journal,
            date=date(2026, 7, 10),
            status="approved",
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.expense_coa,
            debit=Decimal("100"),
            credit=Decimal("0"),
        )
        with self.assertRaises(ValidationPostingError) as ctx:
            validate_voucher_ready_to_post(voucher)
        self.assertEqual(ctx.exception.code, "unbalanced")

    def test_double_post_rejected(self):
        voucher = self._make_payment_voucher()
        post_voucher(voucher, user=self.user)
        with self.assertRaises(ValidationPostingError) as ctx:
            post_voucher(voucher, user=self.user)
        self.assertEqual(ctx.exception.code, "already_posted")

    def test_reverse_restores_bank(self):
        voucher = self._make_payment_voucher()
        post_voucher(voucher, user=self.user)
        reverse_voucher(voucher, user=self.user, remarks="test reverse")

        voucher.refresh_from_db()
        self.bank.refresh_from_db()
        self.assertEqual(voucher.status, "cancelled")
        self.assertEqual(self.bank.current_balance, Decimal("1000.00"))
        self.assertTrue(
            BankTransaction.objects.filter(
                voucher=voucher, reference__startswith="REV-"
            ).exists()
        )

    def test_ngo_project_required_flag(self):
        settings_obj, _ = AccountingSettings.objects.get_or_create(pk=1)
        settings_obj.use_ngo_project_required = True
        settings_obj.save(update_fields=["use_ngo_project_required"])
        voucher = self._make_payment_voucher()
        with self.assertRaises(ValidationPostingError) as ctx:
            validate_voucher_ready_to_post(voucher)
        self.assertEqual(ctx.exception.code, "ngo_project_required")


class ProjectScopedCoaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="coa_proj@example.com",
            username="coa_proj",
            password="pass12345",
        )
        AccountingSettings.objects.get_or_create(pk=1)
        self.project_a = ProjectManagementProject.objects.create(
            title="Project A", code="PA-001", status="Active"
        )
        self.project_b = ProjectManagementProject.objects.create(
            title="Project B", code="PB-001", status="Active"
        )
        self.bank_type, _ = AccountType.objects.get_or_create(
            name="Bank and Cash",
            defaults={
                "classification": "asset",
                "liquidity_type": "bank_cash",
                "is_active": True,
            },
        )
        if self.bank_type.liquidity_type != "bank_cash":
            self.bank_type.liquidity_type = "bank_cash"
            self.bank_type.classification = "asset"
            self.bank_type.save(update_fields=["liquidity_type", "classification"])
        self.expense_type, _ = AccountType.objects.get_or_create(
            name="Expenses",
            defaults={
                "classification": "expense",
                "liquidity_type": "na",
                "is_active": True,
            },
        )
        self.bank_coa = Account.objects.create(
            code="1103",
            name="Cash at Bank",
            account_type=self.bank_type,
            ngo_project=None,
            current_balance=Decimal("5000.00"),
            opening_balance=Decimal("5000.00"),
        )
        self.expense_a = Account.objects.create(
            code="6101",
            name="Salary A",
            account_type=self.expense_type,
            ngo_project=self.project_a,
        )
        self.expense_b = Account.objects.create(
            code="6101",
            name="Salary B",
            account_type=self.expense_type,
            ngo_project=self.project_b,
        )
        self.bank = BankAccount.objects.create(
            name="Shared Bank",
            bank_name="Test Bank",
            account_number="TB-SHARED",
            account=self.bank_coa,
            opening_balance=Decimal("5000.00"),
            current_balance=Decimal("5000.00"),
            status="active",
            account_type="bank",
        )
        self.journal = Journal.objects.create(
            name="Bank Journal",
            code="BNK2",
            journal_type="bank",
        )

    def test_same_code_allowed_per_project(self):
        self.assertEqual(self.expense_a.code, self.expense_b.code)
        self.assertNotEqual(self.expense_a.id, self.expense_b.id)

    def test_bank_rejects_project_scoped_coa(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            BankAccount(
                name="Bad Bank",
                bank_name="X",
                account_number="BAD-1",
                account=self.expense_a,
                status="active",
                account_type="bank",
            ).save()

    def test_voucher_rejects_other_project_account(self):
        voucher = Voucher.objects.create(
            voucher_type="payment",
            journal=self.journal,
            date=date(2026, 7, 10),
            status="approved",
            ngo_project=self.project_a,
            total_amount=Decimal("100.00"),
            created_by=self.user,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.expense_b,
            debit=Decimal("100.00"),
            credit=Decimal("0"),
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.bank_coa,
            debit=Decimal("0"),
            credit=Decimal("100.00"),
        )
        with self.assertRaises(ValidationPostingError) as ctx:
            validate_voucher_ready_to_post(voucher)
        self.assertEqual(ctx.exception.code, "account_project_mismatch")

    def test_voucher_allows_global_bank_with_project_expense(self):
        voucher = Voucher.objects.create(
            voucher_type="payment",
            journal=self.journal,
            date=date(2026, 7, 10),
            status="approved",
            ngo_project=self.project_a,
            total_amount=Decimal("100.00"),
            created_by=self.user,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.expense_a,
            debit=Decimal("100.00"),
            credit=Decimal("0"),
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.bank_coa,
            debit=Decimal("0"),
            credit=Decimal("100.00"),
        )
        lines = validate_voucher_ready_to_post(voucher)
        self.assertEqual(len(lines), 2)
        locked, entry, bank_txns = post_voucher(voucher, user=self.user)
        self.assertEqual(locked.status, "posted")
        self.assertEqual(len(bank_txns), 1)
