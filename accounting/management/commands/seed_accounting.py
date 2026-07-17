"""
Seed accounting module with realistic NGO finance data for LEDARS.
Run: python manage.py seed_accounting [--count=50]
"""

import random
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from faker import Faker
from accounting.models import (
    # Basic
    Currency, ExchangeRate, AccountingSettings, NumberSequence, ApprovalRule,
    # Accounts
    AccountType, AccountGroup, Account, AccountTag,
    # Fiscal
    FiscalYear, FiscalPeriod,
    # Journals
    Journal, JournalEntry, JournalItem, RecurringJournalTemplate, RecurringJournalLine,
    # Taxes
    TaxGroup, Tax, TaxRule, WithholdingTax,
    # Payment Terms
    PaymentTerm,
    # Analytics
    CostCenter, AnalyticAccount, AnalyticTag,
    # Customers/Vendors
    Customer, Vendor,
    # Invoices/Bills
    Invoice, InvoiceLine, InvoicePayment, Bill, BillLine, BillPayment,
    CreditNote, CreditNoteLine, DebitNote, DebitNoteLine,
    # Payments
    PaymentMethod, Payment, PaymentAllocation,
    # Bank/Cash
    BankAccount, BankTransaction, BankReconciliation, BankReconciliationLine,
    CashRegister, CashTransaction,
    # Budgets
    BudgetCategory, Budget, BudgetLine,
    # Assets
    AssetCategory, Asset, AssetDepreciation, AssetDisposal,
    # Reports
    FinancialReportTemplate, ReportLine, GeneratedReport, GeneratedReportData,
    # Vouchers
    VoucherSequence, Voucher, VoucherLine, VoucherApproval, VoucherAttachment,
    # Extended
    FiscalPosition, FiscalPositionTaxMapping, FiscalPositionAccountMapping,
    Incoterm, ReconciliationModel, BankStatement, BankStatementLine,
    Check, BankTransfer, DeferredRevenue, DeferredExpense,
    # Audit
    AuditLog,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the accounting module with realistic LEDARS NGO data"

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=50,
            help='Number of dummy records to create for each model (default: 50)',
        )

    def handle(self, *args, **options):
        count = options['count']
        fake = Faker()
        fake.add_provider('faker.providers.company')
        fake.add_provider('faker.providers.address')
        fake.add_provider('faker.providers.phone_number')

        try:
            with transaction.atomic():
                self.seed_data(fake, count)
            self.stdout.write(
                self.style.SUCCESS("Successfully seeded accounting data!")
            )
        except Exception as e:
            raise CommandError(f"Seeding failed: {e}")

    def seed_data(self, fake, count):
        user = User.objects.first()
        if not user:
            raise CommandError("No user found. Please create a user first.")

        self.stdout.write(f"Seeding accounting data with {count} records per model...")

        # ── 1. Basic Settings ──────────────────────────────────────────────────
        self.stdout.write("  Seeding basic settings...")
        currencies = self.seed_currencies(fake, count)
        exchange_rates = self.seed_exchange_rates(fake, currencies, count)
        settings = self.seed_accounting_settings(fake)
        sequences = self.seed_number_sequences(fake, count)
        approval_rules = self.seed_approval_rules(fake, count)

        # ── 2. Account Structure ───────────────────────────────────────────────
        self.stdout.write("  Seeding account structure...")
        account_types = self.seed_account_types(fake)
        account_groups = self.seed_account_groups(fake, account_types)
        accounts = self.seed_accounts(fake, account_types, account_groups, count)
        account_tags = self.seed_account_tags(fake, count)

        # ── 3. Fiscal Periods ──────────────────────────────────────────────────
        self.stdout.write("  Seeding fiscal periods...")
        fiscal_years = self.seed_fiscal_years(fake, count)
        fiscal_periods = self.seed_fiscal_periods(fake, fiscal_years, count)

        # ── 4. Journals ────────────────────────────────────────────────────────
        self.stdout.write("  Seeding journals...")
        journals = self.seed_journals(fake, accounts, count)
        journal_entries = self.seed_journal_entries(fake, journals, accounts, fiscal_periods, user, count)
        journal_items = self.seed_journal_items(fake, journal_entries, accounts, count)
        recurring_templates = self.seed_recurring_journal_templates(fake, journals, count)
        recurring_lines = self.seed_recurring_journal_lines(fake, recurring_templates, accounts, count)

        # ── 5. Taxes ───────────────────────────────────────────────────────────
        self.stdout.write("  Seeding taxes...")
        tax_groups = self.seed_tax_groups(fake, count)
        taxes = self.seed_taxes(fake, tax_groups, count)
        tax_rules = self.seed_tax_rules(fake, taxes, count)
        withholding_taxes = self.seed_withholding_taxes(fake, count)

        # ── 6. Payment Terms ───────────────────────────────────────────────────
        self.stdout.write("  Seeding payment terms...")
        payment_terms = self.seed_payment_terms(fake, count)

        # ── 7. Analytics ───────────────────────────────────────────────────────
        self.stdout.write("  Seeding analytics...")
        cost_centers = self.seed_cost_centers(fake, count)
        analytic_accounts = self.seed_analytic_accounts(fake, cost_centers, count)
        analytic_tags = self.seed_analytic_tags(fake, count)

        # ── 8. Customers & Vendors ─────────────────────────────────────────────
        self.stdout.write("  Seeding customers and vendors...")
        customers = self.seed_customers(fake, count)
        vendors = self.seed_vendors(fake, count)

        # ── 9. Invoices & Bills ────────────────────────────────────────────────
        self.stdout.write("  Seeding invoices and bills...")
        invoices = self.seed_invoices(fake, customers, journals, fiscal_periods, user, count)
        invoice_lines = self.seed_invoice_lines(fake, invoices, accounts, taxes, analytic_accounts, count)
        # invoice_payments = self.seed_invoice_payments(fake, invoices, count)  # Moved to payment allocations
        bills = self.seed_bills(fake, vendors, journals, fiscal_periods, user, count)
        bill_lines = self.seed_bill_lines(fake, bills, accounts, taxes, analytic_accounts, count)
        # bill_payments = self.seed_bill_payments(fake, bills, count)  # Moved to payment allocations
        credit_notes = self.seed_credit_notes(fake, customers, journals, user, count)
        credit_note_lines = self.seed_credit_note_lines(fake, credit_notes, accounts, taxes, count)
        debit_notes = self.seed_debit_notes(fake, vendors, journals, user, count)
        debit_note_lines = self.seed_debit_note_lines(fake, debit_notes, accounts, count)

        # ── 10. Payments ───────────────────────────────────────────────────────
        self.stdout.write("  Seeding payments...")
        payment_methods = self.seed_payment_methods(fake)
        payments = self.seed_payments(fake, payment_methods, journals, user, count)
        payment_allocations = self.seed_payment_allocations(fake, payments, invoices, bills, count)

        # ── 11. Bank & Cash ────────────────────────────────────────────────────
        self.stdout.write("  Seeding bank and cash...")
        bank_accounts = self.seed_bank_accounts(fake, accounts, currencies, count)
        bank_transactions = self.seed_bank_transactions(fake, bank_accounts, count)
        bank_reconciliations = self.seed_bank_reconciliations(fake, bank_accounts, user, count)
        bank_reconciliation_lines = self.seed_bank_reconciliation_lines(fake, bank_reconciliations, bank_transactions, count)
        cash_registers = self.seed_cash_registers(fake, accounts, count)
        cash_transactions = self.seed_cash_transactions(fake, cash_registers, user, count)

        # ── 12. Budgets ────────────────────────────────────────────────────────
        self.stdout.write("  Seeding budgets...")
        budget_categories = self.seed_budget_categories(fake, count)
        budgets = self.seed_budgets(fake, fiscal_years, budget_categories, user, count)
        budget_lines = self.seed_budget_lines(fake, budgets, accounts, count)

        # ── 13. Assets ─────────────────────────────────────────────────────────
        self.stdout.write("  Seeding assets...")
        asset_categories = self.seed_asset_categories(fake, count)
        assets = self.seed_assets(fake, asset_categories, user, count)
        asset_depreciations = self.seed_asset_depreciations(fake, assets, count)
        asset_disposals = self.seed_asset_disposals(fake, assets, user, count)

        # ── 14. Reports ────────────────────────────────────────────────────────
        self.stdout.write("  Seeding reports...")
        report_templates = self.seed_financial_report_templates(fake, count)
        report_lines = self.seed_report_lines(fake, report_templates, count)
        generated_reports = self.seed_generated_reports(fake, report_templates, user, count)
        generated_report_data = self.seed_generated_report_data(fake, generated_reports, count)

        # ── 15. Vouchers ───────────────────────────────────────────────────────
        self.stdout.write("  Seeding vouchers...")
        voucher_sequences = self.seed_voucher_sequences(fake)
        vouchers = self.seed_vouchers(fake, journals, user, count)
        voucher_lines = self.seed_voucher_lines(fake, vouchers, accounts, analytic_accounts, count)
        voucher_approvals = self.seed_voucher_approvals(fake, vouchers, user, count)
        voucher_attachments = self.seed_voucher_attachments(fake, vouchers, user, count)

        # ── 16. Extended Models ────────────────────────────────────────────────
        self.stdout.write("  Seeding extended models...")
        fiscal_positions = self.seed_fiscal_positions(fake, count)
        fiscal_position_tax_mappings = self.seed_fiscal_position_tax_mappings(fake, fiscal_positions, taxes, count)
        fiscal_position_account_mappings = self.seed_fiscal_position_account_mappings(fake, fiscal_positions, accounts, count)
        incoterms = self.seed_incoterms(fake)
        reconciliation_models = self.seed_reconciliation_models(fake, accounts, count)
        bank_statements = self.seed_bank_statements(fake, bank_accounts, count)
        bank_statement_lines = self.seed_bank_statement_lines(fake, bank_statements, count)
        checks = self.seed_checks(fake, bank_accounts, vendors, count)
        bank_transfers = self.seed_bank_transfers(fake, bank_accounts, count)
        deferred_revenues = self.seed_deferred_revenues(fake, count)
        deferred_expenses = self.seed_deferred_expenses(fake, count)

        # ── 17. Audit Logs ─────────────────────────────────────────────────────
        self.stdout.write("  Seeding audit logs...")
        audit_logs = self.seed_audit_logs(fake, user, count)

        self.stdout.write("  Seeding complete!")

    # ── Helper Methods ────────────────────────────────────────────────────────

    def seed_currencies(self, fake, count):
        currencies = []
        currency_data = [
            ("BDT", "Bangladeshi Taka", "৳", True),
            ("USD", "US Dollar", "$", False),
            ("EUR", "Euro", "€", False),
            ("GBP", "British Pound", "£", False),
        ]
        for code, name, symbol, is_base in currency_data:
            curr, _ = Currency.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "symbol": symbol,
                    "decimal_places": 2,
                    "is_base": is_base,
                },
            )
            currencies.append(curr)
        return currencies

    def seed_exchange_rates(self, fake, currencies, count):
        rates = []
        for curr in currencies[1:]:  # Skip base currency
            for _ in range(min(count, 10)):
                d = fake.date_between(start_date='-1y', end_date='today')
                rate = Decimal(str(fake.pydecimal(left_digits=3, right_digits=2, positive=True)))
                er, _ = ExchangeRate.objects.get_or_create(
                    currency=curr,
                    date=d,
                    defaults={
                        "rate": rate,
                        "inverse_rate": Decimal('1') / rate,
                        "source": fake.company(),
                    },
                )
                rates.append(er)
        return rates

    def seed_accounting_settings(self, fake):
        settings, _ = AccountingSettings.objects.get_or_create(
            defaults={
                "company_name": fake.company(),
                "enable_multi_currency": True,
                "auto_post_vouchers": False,
                "require_voucher_approval": True,
                "enable_budget_control": True,
                "enable_analytic_accounting": True,
            }
        )
        return [settings]

    def seed_number_sequences(self, fake, count):
        sequences = []
        sequence_types = ['journal', 'invoice', 'bill', 'payment', 'voucher']
        for i in range(min(count, len(sequence_types))):
            seq, _ = NumberSequence.objects.get_or_create(
                document_type=sequence_types[i],
                defaults={
                    "prefix": fake.word()[:3].upper(),
                    "next_number": fake.random_int(min=1, max=1000),
                    "padding": 4,
                    "reset_yearly": True,
                    "current_year": 2024,
                },
            )
            sequences.append(seq)
        return sequences

    def seed_approval_rules(self, fake, count):
        rules = []
        doc_types = ['voucher', 'bill', 'invoice', 'payment', 'journal_entry']
        user = User.objects.first()
        for i in range(min(count, len(doc_types))):
            rule, _ = ApprovalRule.objects.get_or_create(
                document_type=doc_types[i],
                level=1,
                defaults={
                    "min_amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "max_amount": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                    "approver": user,
                    "is_active": True,
                },
            )
            rules.append(rule)
        return rules

    def seed_account_types(self, fake):
        types = []
        type_data = [
            ("Current Assets", "asset", "current"),
            ("Fixed Assets", "asset", "non_current"),
            ("Bank and Cash", "asset", "bank_cash"),
            ("Accounts Receivable", "asset", "receivable"),
            ("Current Liabilities", "liability", "current"),
            ("Long-term Liabilities", "liability", "non_current"),
            ("Accounts Payable", "liability", "payable"),
            ("Equity", "equity", "na"),
            ("Grant Income", "income", "na"),
            ("Service Income", "income", "na"),
            ("Program Expenses", "expense", "na"),
            ("Administrative Expenses", "expense", "na"),
            ("Depreciation", "expense", "na"),
        ]
        for name, cls, liq in type_data:
            at, _ = AccountType.objects.get_or_create(
                name=name,
                defaults={"classification": cls, "liquidity_type": liq, "is_active": True}
            )
            types.append(at)
        return types

    def seed_account_groups(self, fake, account_types):
        groups = []
        group_data = [
            ("Cash & Equivalents", "1000", "1099", account_types[2]),  # Bank and Cash
            ("Receivables", "1100", "1199", account_types[3]),  # Accounts Receivable
            ("Fixed Assets", "1500", "1599", account_types[1]),  # Fixed Assets
            ("Payables", "2000", "2099", account_types[6]),  # Accounts Payable
            ("Grant Revenue", "4000", "4099", account_types[8]),  # Grant Income
            ("Program Costs", "5000", "5999", account_types[10]),  # Program Expenses
            ("Admin Costs", "6000", "6999", account_types[11]),  # Administrative Expenses
        ]
        for name, start, end, at in group_data:
            ag, _ = AccountGroup.objects.get_or_create(
                name=name,
                defaults={
                    "code_prefix_start": start,
                    "code_prefix_end": end,
                    "account_type": at,
                },
            )
            groups.append(ag)
        return groups

    def seed_accounts(self, fake, account_types, account_groups, count):
        accounts = []
        for _ in range(count):
            at = random.choice(account_types)
            ag = random.choice(account_groups) if account_groups else None
            acc, _ = Account.objects.get_or_create(
                code=fake.unique.bothify(text='????-####'),
                defaults={
                    "name": fake.company() + " Account",
                    "account_type": at,
                    "account_group": ag,
                    "is_active": True,
                    "is_reconcilable": fake.boolean(),
                },
            )
            accounts.append(acc)
        return accounts

    def seed_account_tags(self, fake, count):
        tags = []
        for _ in range(min(count, 10)):
            tag, _ = AccountTag.objects.get_or_create(
                name=fake.word().capitalize(),
                defaults={
                    "color": fake.hex_color(),
                },
            )
            tags.append(tag)
        return tags

    def seed_fiscal_years(self, fake, count):
        years = []
        for _ in range(min(count, 5)):
            start = fake.date_between(start_date='-5y', end_date='today')
            end = start.replace(year=start.year + 1) - timedelta(days=1)
            fy, _ = FiscalYear.objects.get_or_create(
                name=f"FY {start.year}-{end.year}",
                defaults={
                    "code": f"FY{start.year}",
                    "start_date": start,
                    "end_date": end,
                    "status": random.choice(['draft', 'open', 'closed']),
                    "is_active": True,
                },
            )
            years.append(fy)
        return years

    def seed_fiscal_periods(self, fake, fiscal_years, count):
        periods = []
        for fy in fiscal_years:
            for month in range(1, 13):
                start = date(fy.start_date.year, month, 1)
                if month == 12:
                    end = fy.end_date
                else:
                    end = date(fy.start_date.year, month + 1, 1) - timedelta(days=1)
                fp, _ = FiscalPeriod.objects.get_or_create(
                    fiscal_year=fy,
                    name=f"{fy.name} - {start.strftime('%B')}",
                    defaults={
                        "number": month,
                        "start_date": start,
                        "end_date": end,
                        "status": random.choice(['draft', 'open', 'closed']),
                    },
                )
                periods.append(fp)
        return periods

    def seed_journals(self, fake, accounts, count):
        journals = []
        journal_types = ['sale', 'purchase', 'cash', 'bank', 'general', 'adjustment']
        for _ in range(min(count, len(journal_types))):
            jt = random.choice(journal_types)
            debit_acc = random.choice(accounts) if accounts else None
            credit_acc = random.choice(accounts) if accounts else None
            j, _ = Journal.objects.get_or_create(
                name=fake.company() + " Journal",
                defaults={
                    "code": fake.unique.bothify(text='JRN-####'),
                    "journal_type": jt,
                    "default_debit_account": debit_acc,
                    "default_credit_account": credit_acc,
                    "sequence_prefix": fake.word()[:3].upper(),
                    "is_active": True,
                },
            )
            journals.append(j)
        return journals

    def seed_journal_entries(self, fake, journals, accounts, fiscal_periods, user, count):
        entries = []
        for _ in range(count):
            j = random.choice(journals)
            fp = random.choice(fiscal_periods) if fiscal_periods else None
            je, _ = JournalEntry.objects.get_or_create(
                reference=fake.unique.bothify(text='JE-######'),
                defaults={
                    "journal": j,
                    "date": fake.date_between(start_date='-1y', end_date='today'),
                    "fiscal_period": fp,
                    "narration": fake.sentence(),
                    "created_by": user,
                    "total_debit": Decimal('0'),
                    "total_credit": Decimal('0'),
                    "status": random.choice(['draft', 'posted', 'cancelled']),
                },
            )
            entries.append(je)
        return entries

    def seed_journal_items(self, fake, journal_entries, accounts, count):
        items = []
        for je in journal_entries:
            num_lines = random.randint(2, 5)
            for _ in range(num_lines):
                acc = random.choice(accounts)
                is_debit = fake.boolean()
                amount = Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True)))
                ji, _ = JournalItem.objects.get_or_create(
                    journal_entry=je,
                    account=acc,
                    defaults={
                        "debit": amount if is_debit else Decimal('0'),
                        "credit": amount if not is_debit else Decimal('0'),
                        "label": fake.sentence(),
                    },
                )
                items.append(ji)
        return items

    def seed_recurring_journal_templates(self, fake, journals, count):
        templates = []
        for _ in range(min(count, 5)):
            j = random.choice(journals)
            rjt, _ = RecurringJournalTemplate.objects.get_or_create(
                name=fake.sentence(nb_words=3),
                defaults={
                    "journal": j,
                    "frequency": random.choice(['monthly', 'quarterly', 'yearly']),
                    "next_run_date": fake.future_date(),
                    "is_active": True,
                },
            )
            templates.append(rjt)
        return templates

    def seed_recurring_journal_lines(self, fake, templates, accounts, count):
        lines = []
        for template in templates:
            for _ in range(random.randint(1, 3)):
                acc = random.choice(accounts)
                rjl, _ = RecurringJournalLine.objects.get_or_create(
                    template=template,
                    account=acc,
                    defaults={
                        "debit": Decimal(str(fake.pydecimal(left_digits=3, right_digits=2, positive=True))),
                        "credit": Decimal('0'),
                        "label": fake.sentence(),
                    },
                )
                lines.append(rjl)
        return lines

    def seed_tax_groups(self, fake, count):
        groups = []
        for _ in range(min(count, 5)):
            tg, _ = TaxGroup.objects.get_or_create(
                name=fake.word().capitalize() + " Tax Group",
                defaults={
                    "country": fake.country(),
                },
            )
            groups.append(tg)
        return groups

    def seed_taxes(self, fake, tax_groups, count):
        taxes = []
        scopes = ['sales', 'purchase', 'both']
        types = ['percentage', 'fixed']
        for _ in range(count):
            tg = random.choice(tax_groups) if tax_groups else None
            t, _ = Tax.objects.get_or_create(
                name=fake.word().capitalize() + " Tax",
                defaults={
                    "code": fake.unique.bothify(text='TAX-####'),
                    "tax_type": random.choice(types),
                    "scope": random.choice(scopes),
                    "rate": Decimal(str(fake.pydecimal(left_digits=2, right_digits=2, positive=True))),
                    "tax_group": tg,
                    "is_active": True,
                },
            )
            taxes.append(t)
        return taxes

    def seed_tax_rules(self, fake, taxes, count):
        rules = []
        for _ in range(min(count, 10)):
            t = random.choice(taxes)
            tr, _ = TaxRule.objects.get_or_create(
                name=fake.sentence(nb_words=3),
                defaults={
                    "tax": t,
                    "min_amount": Decimal(str(fake.pydecimal(left_digits=3, right_digits=2, positive=True))),
                    "max_amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "is_active": True,
                },
            )
            rules.append(tr)
        return rules

    def seed_withholding_taxes(self, fake, count):
        wts = []
        for _ in range(min(count, 5)):
            wt, _ = WithholdingTax.objects.get_or_create(
                name=fake.word().capitalize() + " WHT",
                defaults={
                    "code": fake.unique.bothify(text='WHT-####'),
                    "rate": Decimal(str(fake.pydecimal(left_digits=2, right_digits=2, positive=True))),
                    "threshold_amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "is_active": True,
                },
            )
            wts.append(wt)
        return wts

    def seed_payment_terms(self, fake, count):
        terms = []
        for _ in range(min(count, 10)):
            pt, _ = PaymentTerm.objects.get_or_create(
                name=fake.sentence(nb_words=2),
                defaults={
                    "code": fake.unique.bothify(text='PT-####'),
                    "due_days": fake.random_int(min=0, max=90),
                    "discount_days": fake.random_int(min=0, max=30),
                    "discount_percent": Decimal(str(fake.pydecimal(left_digits=1, right_digits=2, positive=True))),
                    "description": fake.sentence(),
                    "is_active": True,
                },
            )
            terms.append(pt)
        return terms

    def seed_cost_centers(self, fake, count):
        centers = []
        for _ in range(count):
            cc, _ = CostCenter.objects.get_or_create(
                name=fake.company() + " Center",
                defaults={
                    "code": fake.unique.bothify(text='CC-####'),
                    "is_active": True,
                },
            )
            centers.append(cc)
        return centers

    def seed_analytic_accounts(self, fake, cost_centers, count):
        accounts = []
        for _ in range(count):
            cc = random.choice(cost_centers) if cost_centers else None
            aa, _ = AnalyticAccount.objects.get_or_create(
                name=fake.company() + " Project",
                defaults={
                    "code": fake.unique.bothify(text='AA-####'),
                    "is_active": True,
                },
            )
            accounts.append(aa)
        return accounts

    def seed_analytic_tags(self, fake, count):
        tags = []
        for _ in range(min(count, 10)):
            at, _ = AnalyticTag.objects.get_or_create(
                name=fake.word().capitalize(),
                defaults={
                    "color": fake.hex_color(),
                },
            )
            tags.append(at)
        return tags

    def seed_customers(self, fake, count):
        customers = []
        for _ in range(count):
            c, _ = Customer.objects.get_or_create(
                name=fake.company(),
                defaults={
                    "email": fake.email(),
                    "phone": fake.phone_number(),
                    "address": fake.address(),
                    "tax_id": fake.unique.bothify(text='TAX-########'),
                    "credit_limit": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                    "status": "active",
                },
            )
            customers.append(c)
        return customers

    def seed_vendors(self, fake, count):
        vendors = []
        for _ in range(count):
            v, _ = Vendor.objects.get_or_create(
                name=fake.company(),
                defaults={
                    "email": fake.email(),
                    "phone": fake.phone_number(),
                    "address": fake.address(),
                    "tax_id": fake.unique.bothify(text='TAX-########'),
                    "status": "active",
                },
            )
            vendors.append(v)
        return vendors

    def seed_invoices(self, fake, customers, journals, fiscal_periods, user, count):
        invoices = []
        for _ in range(count):
            c = random.choice(customers)
            j = random.choice(journals)
            fp = random.choice(fiscal_periods) if fiscal_periods else None
            inv, _ = Invoice.objects.get_or_create(
                invoice_number=fake.unique.bothify(text='INV-######'),
                defaults={
                    "customer": c,
                    "journal": j,
                    "invoice_date": fake.date_between(start_date='-1y', end_date='today'),
                    "due_date": fake.date_between(start_date='today', end_date='+90d'),
                    "fiscal_period": fp,
                    "subtotal": Decimal('0'),
                    "tax_amount": Decimal('0'),
                    "total_amount": Decimal('0'),
                    "status": random.choice(['draft', 'sent', 'paid', 'overdue']),
                    "created_by": user,
                },
            )
            invoices.append(inv)
        return invoices

    def seed_invoice_lines(self, fake, invoices, accounts, taxes, analytic_accounts, count):
        lines = []
        for inv in invoices:
            for _ in range(random.randint(1, 5)):
                acc = random.choice(accounts) if accounts else None
                tax = random.choice(taxes) if taxes else None
                aa = random.choice(analytic_accounts) if analytic_accounts else None
                il, _ = InvoiceLine.objects.get_or_create(
                    invoice=inv,
                    description=fake.sentence(),
                    defaults={
                        "account": acc,
                        "quantity": Decimal(str(fake.random_int(min=1, max=10))),
                        "unit_price": Decimal(str(fake.pydecimal(left_digits=3, right_digits=2, positive=True))),
                        "discount_percent": Decimal('0'),
                        "tax": tax,
                        "analytic_account": aa,
                        "total": Decimal('0'),  # Will be calculated
                    },
                )
                lines.append(il)
        return lines

    def seed_invoice_payments(self, fake, invoices, count):
        payments = []
        for inv in random.sample(invoices, min(count, len(invoices))):
            ip, _ = InvoicePayment.objects.get_or_create(
                invoice=inv,
                payment_date=fake.date_between(start_date='-1y', end_date='today'),
                defaults={
                    "amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "payment_method": fake.word(),
                    "reference": fake.unique.bothify(text='PAY-######'),
                },
            )
            payments.append(ip)
        return payments

    def seed_bills(self, fake, vendors, journals, fiscal_periods, user, count):
        bills = []
        for _ in range(count):
            v = random.choice(vendors)
            j = random.choice(journals)
            fp = random.choice(fiscal_periods) if fiscal_periods else None
            b, _ = Bill.objects.get_or_create(
                bill_number=fake.unique.bothify(text='BILL-######'),
                defaults={
                    "vendor": v,
                    "journal": j,
                    "bill_date": fake.date_between(start_date='-1y', end_date='today'),
                    "due_date": fake.date_between(start_date='today', end_date='+90d'),
                    "fiscal_period": fp,
                    "subtotal": Decimal('0'),
                    "tax_amount": Decimal('0'),
                    "total_amount": Decimal('0'),
                    "status": random.choice(['draft', 'pending', 'approved', 'paid', 'overdue']),
                    "created_by": user,
                },
            )
            bills.append(b)
        return bills

    def seed_bill_lines(self, fake, bills, accounts, taxes, analytic_accounts, count):
        lines = []
        for bill in bills:
            for _ in range(random.randint(1, 5)):
                acc = random.choice(accounts) if accounts else None
                tax = random.choice(taxes) if taxes else None
                aa = random.choice(analytic_accounts) if analytic_accounts else None
                bl, _ = BillLine.objects.get_or_create(
                    bill=bill,
                    description=fake.sentence(),
                    defaults={
                        "account": acc,
                        "quantity": Decimal(str(fake.random_int(min=1, max=10))),
                        "unit_price": Decimal(str(fake.pydecimal(left_digits=3, right_digits=2, positive=True))),
                        "tax": tax,
                        "analytic_account": aa,
                        "total": Decimal('0'),
                    },
                )
                lines.append(bl)
        return lines

    def seed_bill_payments(self, fake, bills, count):
        payments = []
        for bill in random.sample(bills, min(count, len(bills))):
            bp, _ = BillPayment.objects.get_or_create(
                bill=bill,
                payment_date=fake.date_between(start_date='-1y', end_date='today'),
                defaults={
                    "amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "payment_method": fake.word(),
                    "reference": fake.unique.bothify(text='PAY-######'),
                },
            )
            payments.append(bp)
        return payments

    def seed_credit_notes(self, fake, customers, journals, user, count):
        notes = []
        for _ in range(min(count, len(customers))):
            c = random.choice(customers)
            j = random.choice(journals)
            cn, _ = CreditNote.objects.get_or_create(
                credit_note_number=fake.unique.bothify(text='CN-######'),
                defaults={
                    "customer": c,
                    "journal": j,
                    "date": fake.date_between(start_date='-1y', end_date='today'),
                    "total_amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "reason": fake.sentence(),
                    "created_by": user,
                },
            )
            notes.append(cn)
        return notes

    def seed_credit_note_lines(self, fake, credit_notes, accounts, taxes, count):
        lines = []
        for cn in credit_notes:
            for _ in range(random.randint(1, 3)):
                acc = random.choice(accounts) if accounts else None
                tax = random.choice(taxes) if taxes else None
                cnl, _ = CreditNoteLine.objects.get_or_create(
                    credit_note=cn,
                    description=fake.sentence(),
                    defaults={
                        "account": acc,
                        "quantity": Decimal(str(fake.random_int(min=1, max=5))),
                        "unit_price": Decimal(str(fake.pydecimal(left_digits=3, right_digits=2, positive=True))),
                        "total": Decimal('0'),
                    },
                )
                lines.append(cnl)
        return lines

    def seed_debit_notes(self, fake, vendors, journals, user, count):
        notes = []
        for _ in range(min(count, len(vendors))):
            v = random.choice(vendors)
            j = random.choice(journals)
            dn, _ = DebitNote.objects.get_or_create(
                debit_note_number=fake.unique.bothify(text='DN-######'),
                defaults={
                    "vendor": v,
                    "journal": j,
                    "date": fake.date_between(start_date='-1y', end_date='today'),
                    "total_amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "reason": fake.sentence(),
                    "created_by": user,
                },
            )
            notes.append(dn)
        return notes

    def seed_debit_note_lines(self, fake, debit_notes, accounts, count):
        lines = []
        for dn in debit_notes:
            for _ in range(random.randint(1, 3)):
                acc = random.choice(accounts) if accounts else None
                dnl, _ = DebitNoteLine.objects.get_or_create(
                    debit_note=dn,
                    description=fake.sentence(),
                    defaults={
                        "account": acc,
                        "quantity": Decimal(str(fake.random_int(min=1, max=5))),
                        "unit_price": Decimal(str(fake.pydecimal(left_digits=3, right_digits=2, positive=True))),
                        "total": Decimal('0'),
                    },
                )
                lines.append(dnl)
        return lines

    def seed_payment_methods(self, fake):
        methods = []
        method_data = [
            ("Cash", "cash"),
            ("Bank Transfer", "bank_transfer"),
            ("Check", "check"),
            ("Credit Card", "credit_card"),
            ("Wire Transfer", "wire_transfer"),
        ]
        for name, code in method_data:
            pm, _ = PaymentMethod.objects.get_or_create(
                name=name,
                defaults={
                    "code": code,
                    "is_active": True,
                },
            )
            methods.append(pm)
        return methods

    def seed_payments(self, fake, payment_methods, journals, user, count):
        payments = []
        for _ in range(count):
            pm = random.choice(payment_methods)
            j = random.choice(journals)
            p, _ = Payment.objects.get_or_create(
                reference=fake.unique.bothify(text='PAY-######'),
                defaults={
                    "payment_method": pm,
                    "journal": j,
                    "direction": random.choice(['inbound', 'outbound']),
                    "date": fake.date_between(start_date='-1y', end_date='today'),
                    "amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "memo": fake.sentence(),
                    "created_by": user,
                    "status": random.choice(['draft', 'posted', 'cancelled']),
                },
            )
            payments.append(p)
        return payments

    def seed_payment_allocations(self, fake, payments, invoices, bills, count):
        allocations = []
        for payment in random.sample(payments, min(count, len(payments))):
            if fake.boolean() and invoices:
                inv = random.choice(invoices)
                doc_type = 'invoice'
                doc_id = inv.id
            elif bills:
                bill = random.choice(bills)
                doc_type = 'bill'
                doc_id = bill.id
            else:
                continue
            pa, _ = PaymentAllocation.objects.get_or_create(
                payment=payment,
                document_type=doc_type,
                document_id=doc_id,
                defaults={
                    "allocated_amount": Decimal(str(fake.pydecimal(left_digits=3, right_digits=2, positive=True))),
                },
            )
            allocations.append(pa)
        return allocations

    def seed_bank_accounts(self, fake, accounts, currencies, count):
        bank_accounts = []
        for _ in range(min(count, 5)):
            acc = random.choice(accounts) if accounts else None
            curr = random.choice(currencies) if currencies else None
            ba, _ = BankAccount.objects.get_or_create(
                account_number=fake.unique.bothify(text='############'),
                defaults={
                    "name": fake.company() + ' Account',
                    "bank_name": fake.company(),
                    "branch": fake.city(),
                    "account": acc,
                    "currency": curr,
                    "opening_balance": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                    "current_balance": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                    "status": 'active',
                },
            )
            bank_accounts.append(ba)
        return bank_accounts

    def seed_bank_transactions(self, fake, bank_accounts, count):
        transactions = []
        for _ in range(count):
            ba = random.choice(bank_accounts)
            is_credit = fake.boolean()
            bt, _ = BankTransaction.objects.get_or_create(
                bank_account=ba,
                date=fake.date_between(start_date='-1y', end_date='today'),
                reference=fake.unique.bothify(text='BT-######'),
                defaults={
                    "description": fake.sentence(),
                    "transaction_type": 'credit' if is_credit else 'debit',
                    "amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "status": random.choice(['unreconciled', 'reconciled', 'excluded']),
                },
            )
            transactions.append(bt)
        return transactions

    def seed_bank_reconciliations(self, fake, bank_accounts, user, count):
        reconciliations = []
        for _ in range(min(count, len(bank_accounts))):
            ba = random.choice(bank_accounts)
            br, _ = BankReconciliation.objects.get_or_create(
                bank_account=ba,
                statement_date=fake.date_between(start_date='-1y', end_date='today'),
                defaults={
                    "statement_balance": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                    "book_balance": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                    "reconciled_by": user,
                    "status": random.choice(['in_progress', 'completed', 'cancelled']),
                },
            )
            reconciliations.append(br)
        return reconciliations

    def seed_bank_reconciliation_lines(self, fake, reconciliations, bank_transactions, count):
        lines = []
        used_pairs = set()
        for br in reconciliations:
            for _ in range(random.randint(1, 5)):
                bt = random.choice(bank_transactions) if bank_transactions else None
                if bt is None:
                    continue
                pair = (br.id, bt.id)
                if pair in used_pairs:
                    continue
                used_pairs.add(pair)
                brl, _ = BankReconciliationLine.objects.get_or_create(
                    reconciliation=br,
                    bank_transaction=bt,
                    defaults={
                        "is_matched": fake.boolean(),
                        "difference": Decimal('0'),
                    },
                )
                lines.append(brl)
        return lines

    def seed_cash_registers(self, fake, accounts, count):
        registers = []
        for _ in range(min(count, 3)):
            acc = random.choice(accounts) if accounts else None
            cr, _ = CashRegister.objects.get_or_create(
                name=fake.word().capitalize() + " Register",
                defaults={
                    "account": acc,
                    "opening_balance": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "current_balance": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "is_active": True,
                },
            )
            registers.append(cr)
        return registers

    def seed_cash_transactions(self, fake, cash_registers, user, count):
        transactions = []
        for _ in range(count):
            cr = random.choice(cash_registers)
            ct, _ = CashTransaction.objects.get_or_create(
                cash_register=cr,
                date=fake.date_between(start_date='-1y', end_date='today'),
                description=fake.unique.sentence(),
                defaults={
                    "transaction_type": random.choice(['receipt', 'payment', 'replenishment']),
                    "amount": Decimal(str(fake.pydecimal(left_digits=3, right_digits=2, positive=True))),
                    "balance_after": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "created_by": user,
                },
            )
            transactions.append(ct)
        return transactions

    def seed_budget_categories(self, fake, count):
        categories = []
        for _ in range(min(count, 10)):
            bc, _ = BudgetCategory.objects.get_or_create(
                name=fake.word().capitalize() + " Budget",
                defaults={
                    "code": fake.unique.bothify(text='BC-####'),
                    "description": fake.sentence(),
                    "is_active": True,
                },
            )
            categories.append(bc)
        return categories

    def seed_budgets(self, fake, fiscal_years, budget_categories, user, count):
        budgets = []
        for _ in range(min(count, max(1, len(fiscal_years)))):
            fy = random.choice(fiscal_years)
            bc = random.choice(budget_categories) if budget_categories else None
            b, _ = Budget.objects.get_or_create(
                name=fake.sentence(nb_words=3) + f' {fy}',
                defaults={
                    "fiscal_year": fy,
                    "total_planned": Decimal(str(fake.pydecimal(left_digits=6, right_digits=2, positive=True))),
                    "created_by": user,
                    "status": random.choice(['draft', 'confirmed', 'validated', 'done']),
                },
            )
            budgets.append(b)
        return budgets

    def seed_budget_lines(self, fake, budgets, accounts, count):
        lines = []
        for budget in budgets:
            for _ in range(random.randint(1, 5)):
                acc = random.choice(accounts) if accounts else None
                bl, _ = BudgetLine.objects.get_or_create(
                    budget=budget,
                    account=acc,
                    defaults={
                        "planned_amount": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                        "actual_amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    },
                )
                lines.append(bl)
        return lines

    def seed_asset_categories(self, fake, count):
        categories = []
        for _ in range(min(count, 10)):
            ac, _ = AssetCategory.objects.get_or_create(
                name=fake.word().capitalize() + " Assets",
                defaults={
                    "depreciation_method": random.choice(['straight_line', 'declining_balance', 'units_of_production']),
                    "useful_life": fake.random_int(min=12, max=240),
                    "salvage_percent": Decimal(str(fake.pydecimal(left_digits=1, right_digits=2, positive=True))),
                    "is_active": True,
                },
            )
            categories.append(ac)
        return categories

    def seed_assets(self, fake, asset_categories, user, count):
        assets = []
        for _ in range(count):
            ac = random.choice(asset_categories)
            a, _ = Asset.objects.get_or_create(
                name=fake.company() + " Asset",
                defaults={
                    "code": fake.unique.bothify(text='AST-####'),
                    "category": ac,
                    "purchase_date": fake.date_between(start_date='-5y', end_date='today'),
                    "purchase_cost": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                    "current_value": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                    "created_by": user,
                    "status": random.choice(['draft', 'running', 'fully_depreciated']),
                },
            )
            assets.append(a)
        return assets

    def seed_asset_depreciations(self, fake, assets, count):
        depreciations = []
        for asset in random.sample(assets, min(count, len(assets))):
            period_num = fake.random_int(min=1, max=60)
            ad, _ = AssetDepreciation.objects.get_or_create(
                asset=asset,
                period=period_num,
                defaults={
                    "date": fake.date_between(start_date='-5y', end_date='today'),
                    "depreciation_amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "accumulated_depreciation": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                    "remaining_value": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                },
            )
            depreciations.append(ad)
        return depreciations

    def seed_asset_disposals(self, fake, assets, user, count):
        disposals = []
        for asset in random.sample(assets, min(count // 2, len(assets))):
            ad, _ = AssetDisposal.objects.get_or_create(
                asset=asset,
                defaults={
                    "disposal_date": fake.date_between(start_date='-1y', end_date='today'),
                    "disposal_method": random.choice(['sale', 'scrap', 'donation', 'write_off']),
                    "sale_amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "gain_loss": Decimal('0'),
                    "notes": fake.sentence(),
                    "created_by": user,
                },
            )
            disposals.append(ad)
        return disposals

    def seed_financial_report_templates(self, fake, count):
        templates = []
        template_types = ['balance_sheet', 'income_statement', 'cash_flow', 'trial_balance']
        for _ in range(min(count, len(template_types))):
            tt = random.choice(template_types)
            frt, _ = FinancialReportTemplate.objects.get_or_create(
                name=fake.sentence(nb_words=3),
                defaults={
                    "report_type": tt,
                    "description": fake.sentence(),
                    "is_active": True,
                },
            )
            templates.append(frt)
        return templates

    def seed_report_lines(self, fake, templates, count):
        lines = []
        for template in templates:
            for i in range(random.randint(3, 8)):
                rl, _ = ReportLine.objects.get_or_create(
                    template=template,
                    sequence=(i + 1) * 10,
                    defaults={
                        "name": fake.sentence(nb_words=2),
                        "code": fake.unique.bothify(text='RL-####'),
                        "computation_type": random.choice(['sum_of_accounts', 'sum_of_lines', 'formula', 'total']),
                    },
                )
                lines.append(rl)
        return lines

    def seed_generated_reports(self, fake, templates, user, count):
        reports = []
        for _ in range(min(count, len(templates))):
            template = random.choice(templates)
            start = fake.date_between(start_date='-1y', end_date='-30d')
            end = fake.date_between(start_date=start, end_date='today')
            gr, _ = GeneratedReport.objects.get_or_create(
                title=fake.sentence(nb_words=3),
                defaults={
                    "template": template,
                    "period_from": start,
                    "period_to": end,
                    "generated_by": user,
                    "status": random.choice(['generating', 'completed', 'failed']),
                },
            )
            reports.append(gr)
        return reports

    def seed_generated_report_data(self, fake, reports, count):
        data = []
        for report in reports:
            for i in range(random.randint(3, 8)):
                grd, _ = GeneratedReportData.objects.get_or_create(
                    report=report,
                    sequence=i,
                    defaults={
                        "label": fake.sentence(nb_words=2),
                        "current_amount": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                        "comparison_amount": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                    },
                )
                data.append(grd)
        return data

    def seed_voucher_sequences(self, fake):
        sequences = []
        current_year = fake.date_between(start_date='-1y', end_date='today').year
        for vtype in ['payment', 'receipt', 'journal', 'contra']:
            vs, _ = VoucherSequence.objects.get_or_create(
                voucher_type=vtype,
                year=current_year,
                defaults={
                    "last_number": fake.random_int(min=0, max=100),
                },
            )
            sequences.append(vs)
        return sequences

    def seed_vouchers(self, fake, journals, user, count):
        vouchers = []
        voucher_types = ['payment', 'receipt', 'journal', 'contra']
        for _ in range(count):
            j = random.choice(journals)
            vt = random.choice(voucher_types)
            v = Voucher.objects.create(
                voucher_type=vt,
                journal=j,
                date=fake.date_between(start_date='-1y', end_date='today'),
                narration=fake.sentence(),
                total_amount=Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                created_by=user,
                status=random.choice(['draft', 'approved', 'posted']),
            )
            vouchers.append(v)
        return vouchers

    def seed_voucher_lines(self, fake, vouchers, accounts, analytic_accounts, count):
        lines = []
        for voucher in vouchers:
            for _ in range(random.randint(2, 5)):
                acc = random.choice(accounts) if accounts else None
                aa = random.choice(analytic_accounts) if analytic_accounts else None
                vl, _ = VoucherLine.objects.get_or_create(
                    voucher=voucher,
                    account=acc,
                    defaults={
                        "analytic_account": aa,
                        "debit": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                        "credit": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                        "description": fake.sentence(),
                    },
                )
                lines.append(vl)
        return lines

    def seed_voucher_approvals(self, fake, vouchers, user, count):
        approvals = []
        for voucher in random.sample(vouchers, min(count, len(vouchers))):
            va, _ = VoucherApproval.objects.get_or_create(
                voucher=voucher,
                approver=user,
                defaults={
                    "level": 1,
                    "status": random.choice(['pending', 'approved', 'rejected']),
                    "remarks": fake.sentence(),
                },
            )
            approvals.append(va)
        return approvals

    def seed_voucher_attachments(self, fake, vouchers, user, count):
        # Skip creating attachments since file upload requires actual files
        return []

    def seed_fiscal_positions(self, fake, count):
        positions = []
        for _ in range(min(count, 5)):
            fp, _ = FiscalPosition.objects.get_or_create(
                name=fake.country() + " Position",
                defaults={
                    "notes": fake.sentence(),
                    "is_active": True,
                },
            )
            positions.append(fp)
        return positions

    def seed_fiscal_position_tax_mappings(self, fake, positions, taxes, count):
        mappings = []
        for position in positions:
            for _ in range(random.randint(1, 3)):
                src_tax = random.choice(taxes) if taxes else None
                dst_tax = random.choice(taxes) if taxes else None
                if src_tax is None:
                    continue
                fptm, _ = FiscalPositionTaxMapping.objects.get_or_create(
                    fiscal_position=position,
                    source_tax=src_tax,
                    defaults={
                        "destination_tax": dst_tax,
                    },
                )
                mappings.append(fptm)
        return mappings

    def seed_fiscal_position_account_mappings(self, fake, positions, accounts, count):
        mappings = []
        for position in positions:
            for _ in range(random.randint(1, 5)):
                src_acc = random.choice(accounts) if accounts else None
                dst_acc = random.choice(accounts) if accounts else None
                if src_acc is None or dst_acc is None:
                    continue
                fpam, _ = FiscalPositionAccountMapping.objects.get_or_create(
                    fiscal_position=position,
                    source_account=src_acc,
                    defaults={
                        "destination_account": dst_acc,
                    },
                )
                mappings.append(fpam)
        return mappings

    def seed_incoterms(self, fake):
        terms = []
        incoterm_data = [
            ("EXW", "Ex Works"),
            ("FCA", "Free Carrier"),
            ("CPT", "Carriage Paid To"),
            ("CIP", "Carriage and Insurance Paid to"),
            ("DAT", "Delivered at Terminal"),
            ("DAP", "Delivered at Place"),
            ("DDP", "Delivered Duty Paid"),
            ("FAS", "Free Alongside Ship"),
            ("FOB", "Free on Board"),
            ("CFR", "Cost and Freight"),
            ("CIF", "Cost, Insurance and Freight"),
        ]
        for code, name in incoterm_data:
            it, _ = Incoterm.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": fake.sentence(),
                },
            )
            terms.append(it)
        return terms

    def seed_reconciliation_models(self, fake, accounts, count):
        rmodels = []
        for _ in range(min(count, 5)):
            rm, _ = ReconciliationModel.objects.get_or_create(
                name=fake.sentence(nb_words=3),
                defaults={
                    "model_type": random.choice(['writeoff', 'invoice_matching', 'manual']),
                    "is_active": True,
                },
            )
            rmodels.append(rm)
        return rmodels

    def seed_bank_statements(self, fake, bank_accounts, count):
        statements = []
        for _ in range(min(count, len(bank_accounts))):
            ba = random.choice(bank_accounts)
            start = fake.date_between(start_date='-1y', end_date='-30d')
            end = fake.date_between(start_date=start, end_date='today')
            bs, _ = BankStatement.objects.get_or_create(
                bank_account=ba,
                period_start=start,
                period_end=end,
                defaults={
                    "date": end,
                    "opening_balance": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                    "closing_balance": Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True))),
                    "status": random.choice(['draft', 'confirmed', 'reconciled']),
                },
            )
            statements.append(bs)
        return statements

    def seed_bank_statement_lines(self, fake, statements, count):
        lines = []
        for statement in statements:
            for _ in range(random.randint(3, 8)):
                bsl, _ = BankStatementLine.objects.get_or_create(
                    statement=statement,
                    reference=fake.unique.bothify(text='REF-######'),
                    defaults={
                        "date": fake.date_between(start_date=statement.period_start, end_date=statement.period_end),
                        "description": fake.sentence(),
                        "amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    },
                )
                lines.append(bsl)
        return lines

    def seed_checks(self, fake, bank_accounts, vendors, count):
        checks = []
        for _ in range(min(count, len(bank_accounts))):
            ba = random.choice(bank_accounts)
            v = random.choice(vendors) if vendors else None
            c, _ = Check.objects.get_or_create(
                check_number=fake.unique.bothify(text='CHK-########'),
                defaults={
                    "bank_account": ba,
                    "amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "date": fake.date_between(start_date='-1y', end_date='today'),
                    "payee": v.name if v else fake.name(),
                    "memo": fake.sentence(),
                    "status": random.choice(['draft', 'issued', 'deposited', 'cleared', 'cancelled']),
                },
            )
            checks.append(c)
        return checks

    def seed_bank_transfers(self, fake, bank_accounts, count):
        transfers = []
        for _ in range(min(count, len(bank_accounts) // 2)):
            from_acc = random.choice(bank_accounts)
            to_acc = random.choice([ba for ba in bank_accounts if ba != from_acc])
            bt, _ = BankTransfer.objects.get_or_create(
                reference=fake.unique.bothify(text='BTR-######'),
                defaults={
                    "from_account": from_acc,
                    "to_account": to_acc,
                    "amount": Decimal(str(fake.pydecimal(left_digits=4, right_digits=2, positive=True))),
                    "date": fake.date_between(start_date='-1y', end_date='today'),
                    "description": fake.sentence(),
                    "status": random.choice(['draft', 'completed', 'cancelled']),
                },
            )
            transfers.append(bt)
        return transfers

    def seed_deferred_revenues(self, fake, count):
        revenues = []
        for _ in range(min(count, 5)):
            total = Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True)))
            dr, _ = DeferredRevenue.objects.get_or_create(
                name=fake.sentence(nb_words=3),
                defaults={
                    "total_amount": total,
                    "recognized_amount": Decimal('0'),
                    "remaining_amount": total,
                    "start_date": fake.date_between(start_date='-2y', end_date='-1y'),
                    "end_date": fake.date_between(start_date='-1y', end_date='+1y'),
                    "status": random.choice(['draft', 'running', 'fully_recognized']),
                },
            )
            revenues.append(dr)
        return revenues

    def seed_deferred_expenses(self, fake, count):
        expenses = []
        for _ in range(min(count, 5)):
            total = Decimal(str(fake.pydecimal(left_digits=5, right_digits=2, positive=True)))
            de, _ = DeferredExpense.objects.get_or_create(
                name=fake.sentence(nb_words=3),
                defaults={
                    "total_amount": total,
                    "recognized_amount": Decimal('0'),
                    "remaining_amount": total,
                    "start_date": fake.date_between(start_date='-2y', end_date='-1y'),
                    "end_date": fake.date_between(start_date='-1y', end_date='+1y'),
                    "status": random.choice(['draft', 'running', 'fully_recognized']),
                },
            )
            expenses.append(de)
        return expenses

    def seed_audit_logs(self, fake, user, count):
        logs = []
        actions = ['create', 'update', 'delete', 'post', 'approve']
        for _ in range(min(count, 10)):
            al = AuditLog.objects.create(
                model_name=random.choice(['Invoice', 'Bill', 'Payment', 'Voucher', 'Budget']),
                object_id=fake.random_int(min=1, max=1000),
                action=random.choice(actions),
                description=fake.sentence(),
                user=user,
                ip_address=fake.ipv4(),
            )
            logs.append(al)
        return logs
