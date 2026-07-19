"""
Nightly / on-demand balance integrity check.
Compare Account.current_balance vs sum(JournalItem) and BankAccount vs bank-linked CoA.

Run: python manage.py check_balance_integrity
     python manage.py check_balance_integrity --fix
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum

from accounting.models import Account, BankAccount, JournalItem


class Command(BaseCommand):
    help = "Compare cached GL/bank balances against journal item sums"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Rebuild Account.current_balance and BankAccount.current_balance from source docs",
        )

    def handle(self, *args, **options):
        drift_accounts = []
        ji_totals = {
            row["account"]: (
                Decimal(str(row["d"] or 0)) - Decimal(str(row["c"] or 0))
            )
            for row in JournalItem.objects.filter(
                journal_entry__status="posted"
            )
            .values("account")
            .annotate(d=Sum("debit"), c=Sum("credit"))
        }

        for acc in Account.objects.filter(is_active=True):
            expected = Decimal(str(acc.opening_balance or 0)) + ji_totals.get(
                acc.id, Decimal("0")
            )
            cached = Decimal(str(acc.current_balance or 0))
            if expected != cached:
                drift_accounts.append((acc.code, acc.name, cached, expected))
                if options["fix"]:
                    Account.objects.filter(pk=acc.id).update(current_balance=expected)

        drift_banks = []
        for bank in BankAccount.objects.select_related("account").filter(
            account__isnull=False
        ):
            if not bank.account_id:
                continue
            # Prefer CoA balance as truth for linked bank ledger
            bank.account.refresh_from_db()
            expected = Decimal(str(bank.account.current_balance or 0))
            cached = Decimal(str(bank.current_balance or 0))
            if expected != cached:
                drift_banks.append(
                    (bank.account_number, bank.name, cached, expected)
                )
                if options["fix"]:
                    BankAccount.objects.filter(pk=bank.pk).update(
                        current_balance=expected
                    )

        if not drift_accounts and not drift_banks:
            self.stdout.write(self.style.SUCCESS("No balance drift detected."))
            return

        self.stdout.write(
            self.style.WARNING(
                f"Account drifts: {len(drift_accounts)}, Bank drifts: {len(drift_banks)}"
            )
        )
        for code, name, cached, expected in drift_accounts[:50]:
            self.stdout.write(
                f"  ACC {code} {name}: cached={cached} expected={expected}"
            )
        for number, name, cached, expected in drift_banks[:50]:
            self.stdout.write(
                f"  BANK {number} {name}: cached={cached} expected={expected}"
            )
        if options["fix"]:
            self.stdout.write(self.style.SUCCESS("Balances repaired."))
        else:
            self.stdout.write(
                self.style.NOTICE("Re-run with --fix to rebuild cached balances.")
            )
