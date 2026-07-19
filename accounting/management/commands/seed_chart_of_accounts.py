"""
Seed chart of accounts with exact LEDARS structure.
Run: python manage.py seed_chart_of_accounts
Run (project): python manage.py seed_chart_of_accounts --ngo-project 1
Run (clear + reseed): python manage.py seed_chart_of_accounts --clear
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounting.models import AccountType, AccountGroup, Account

# Shared globally across all projects — never duplicated into project CoA.
BANK_CASH_CODES = {"1101", "1102", "1103"}
# Global parents needed so bank/cash hierarchy stays consistent.
BANK_CASH_PARENT_CODES = {"1000", "1100"}
# Legacy second bank ledger from earlier seed — keep inactive, do not re-seed.
LEGACY_BANK_CASH_CODES = {"1104"}


class Command(BaseCommand):
    help = "Seed chart of accounts (AccountTypes, AccountGroups, Accounts)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear all existing accounts, groups, and types before seeding",
        )
        parser.add_argument(
            "--ngo-project",
            type=int,
            default=None,
            help="Seed project-scoped CoA for this ProjectManagementProject id "
            "(bank/cash accounts stay global)",
        )

    def handle(self, *args, **options):
        ngo_project_id = options.get("ngo_project")
        ngo_project = None
        if ngo_project_id:
            from project_managements.models import ProjectManagementProject

            ngo_project = ProjectManagementProject.objects.filter(
                pk=ngo_project_id
            ).first()
            if not ngo_project:
                raise CommandError(f"NGO project id={ngo_project_id} not found.")

        try:
            with transaction.atomic():
                if options["clear"]:
                    if ngo_project:
                        self.stdout.write(
                            f"Clearing CoA for project {ngo_project_id} "
                            "(global bank/cash kept)..."
                        )
                        Account.objects.filter(ngo_project_id=ngo_project_id).delete()
                    else:
                        self.stdout.write("Clearing existing COA data...")
                        Account.objects.all().delete()
                        AccountGroup.objects.all().delete()
                        AccountType.objects.all().delete()
                        self.stdout.write(
                            self.style.WARNING(
                                "All accounts, groups, and types deleted."
                            )
                        )
                self.seed(ngo_project=ngo_project)
            scope = (
                f" for project {ngo_project_id}" if ngo_project_id else " (global)"
            )
            self.stdout.write(
                self.style.SUCCESS(f"Chart of accounts seeded successfully{scope}!")
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Seeding failed: {e}"))
            raise

    def seed(self, ngo_project=None):
        types = self._seed_account_types()
        self._seed_accounts(types, ngo_project=ngo_project)
        self._retire_legacy_bank_ledgers(types)

    def _retire_legacy_bank_ledgers(self, types):
        """Collapse duplicate Cash at Bank ledgers to a single global 1103."""
        bank_type = types.get("Bank and Cash")
        cash_at_bank = Account.objects.filter(code="1103", ngo_project__isnull=True).first()
        if cash_at_bank:
            if cash_at_bank.name != "Cash at Bank":
                cash_at_bank.name = "Cash at Bank"
                if bank_type:
                    cash_at_bank.account_type = bank_type
                cash_at_bank.is_active = True
                cash_at_bank.is_deprecated = False
                cash_at_bank.save()
                self.stdout.write("  Renamed global 1103 → Cash at Bank")

        for code in LEGACY_BANK_CASH_CODES:
            legacy = Account.objects.filter(code=code, ngo_project__isnull=True).first()
            if not legacy:
                continue
            if cash_at_bank:
                # Move bank master links onto the single Cash at Bank ledger
                moved = legacy.bank_accounts.update(account=cash_at_bank)
                if moved:
                    self.stdout.write(
                        f"  Re-linked {moved} bank master(s) from {code} → 1103"
                    )
            legacy.is_active = False
            legacy.is_deprecated = True
            legacy.save(update_fields=["is_active", "is_deprecated"])
            self.stdout.write(f"  Retired legacy global bank ledger {code} ({legacy.name})")

    def _seed_account_types(self):
        data = [
            ("Assets", "asset", "current"),
            ("Bank and Cash", "asset", "bank_cash"),
            ("Liabilities", "liability", "current"),
            ("Shareholders Equity", "equity", "na"),
            ("Revenue", "income", "na"),
            ("Cost of Goods Sold", "expense", "na"),
            ("Operating Expenses", "expense", "na"),
            ("VAT & Tax Control", "liability", "na"),
        ]
        created = {}
        for name, classification, liquidity in data:
            obj, is_new = AccountType.objects.get_or_create(
                name=name,
                defaults={
                    "classification": classification,
                    "liquidity_type": liquidity,
                    "is_active": True,
                },
            )
            if obj.liquidity_type != liquidity:
                obj.liquidity_type = liquidity
                obj.classification = classification
                obj.save(update_fields=["liquidity_type", "classification"])
            created[name] = obj
            if is_new:
                self.stdout.write(f"  + AccountType: {name}")
        return created

    def _accounts_data(self):
        # Structure: (code, name, type_name, parent_code, is_contra)
        return [
            ("1000", "Assets", "Assets", None, False),
            ("1100", "Current Assets", "Assets", "1000", False),
            ("1101", "Cash In Hand", "Bank and Cash", "1100", False),
            ("1102", "Petty Cash", "Bank and Cash", "1100", False),
            ("1103", "Cash at Bank", "Bank and Cash", "1100", False),
            ("1105", "Accounts Receivable", "Assets", "1100", False),
            ("1106", "Supplier Advance", "Assets", "1100", False),
            ("1107", "Employee Advance", "Assets", "1100", False),
            ("1108", "VAT Receivable", "Assets", "1100", False),
            ("1109", "Tax Deducted at Source Receivable", "Assets", "1100", False),
            ("1110", "Closing Inventory", "Assets", "1100", False),
            ("1111", "Goods In Transit", "Assets", "1100", False),
            ("1112", "Prepaid Expenses", "Assets", "1100", False),
            ("1200", "Fixed Assets", "Assets", "1000", False),
            ("1201", "Office Equipment", "Assets", "1200", False),
            ("1202", "Furniture & Fixture", "Assets", "1200", False),
            ("1203", "Computer & Accessories", "Assets", "1200", False),
            ("1204", "Vehicle", "Assets", "1200", False),
            ("1205", "Generator / IPS", "Assets", "1200", False),
            ("1206", "Air Conditioner", "Assets", "1200", False),
            ("1207", "Accumulated Depreciation", "Assets", "1200", True),
            ("1208", "Warehouse Equipment", "Assets", "1200", False),
            ("2000", "Liabilities", "Liabilities", None, False),
            ("2100", "Current Liabilities", "Liabilities", "2000", False),
            ("2101", "Accounts Payable", "Liabilities", "2100", False),
            ("2102", "Customer Advance against Sale", "Liabilities", "2100", False),
            ("2103", "Salary Payable", "Liabilities", "2100", False),
            ("2104", "Bonus Payable", "Liabilities", "2100", False),
            ("2105", "Rent Payable", "Liabilities", "2100", False),
            ("2106", "Utility Bills Payable", "Liabilities", "2100", False),
            ("2107", "VAT Payable", "Liabilities", "2100", False),
            ("2108", "Tax Payable", "Liabilities", "2100", False),
            ("2109", "Commission Payable", "Liabilities", "2100", False),
            ("2110", "Provision for Expenses", "Liabilities", "2100", False),
            ("2200", "Long Term Liabilities", "Liabilities", "2000", False),
            ("2201", "Bank Loan", "Liabilities", "2200", False),
            ("2202", "Loan from Directors", "Liabilities", "2200", False),
            ("2203", "Lease Liability", "Liabilities", "2200", False),
            ("3000", "Shareholders' Equity", "Shareholders Equity", None, False),
            ("3001", "Paid up Capital", "Shareholders Equity", "3000", False),
            ("3002", "Additional Capital", "Shareholders Equity", "3000", False),
            ("3003", "Retained Earnings", "Shareholders Equity", "3000", False),
            ("3004", "Partner's Capital", "Shareholders Equity", "3000", False),
            ("3005", "Drawings", "Shareholders Equity", "3000", True),
            ("4000", "Revenue", "Revenue", None, False),
            ("4101", "Sales Revenue", "Revenue", "4000", False),
            ("4102", "Sales Return", "Revenue", "4000", True),
            ("4103", "Sales Discount", "Revenue", "4000", True),
            ("4200", "Other Income", "Revenue", None, False),
            ("4201", "Commission Income", "Revenue", "4200", False),
            ("4202", "Interest Income", "Revenue", "4200", False),
            ("4203", "Miscellaneous Income", "Revenue", "4200", False),
            ("4204", "Wastage sale", "Revenue", "4200", False),
            ("5000", "Cost of Goods Sold", "Cost of Goods Sold", None, False),
            ("5001", "Cost of Goods Sold (COGS)", "Cost of Goods Sold", "5000", False),
            ("5101", "Opening Stock", "Cost of Goods Sold", "5000", False),
            ("5102", "Purchase", "Cost of Goods Sold", "5000", False),
            ("5103", "Import Purchase", "Cost of Goods Sold", "5000", False),
            ("5104", "Carriage Inward", "Cost of Goods Sold", "5000", False),
            ("5105", "Loading & Unloading", "Cost of Goods Sold", "5000", False),
            ("5106", "Purchase Return", "Cost of Goods Sold", "5000", True),
            ("5107", "Purchase Discount", "Cost of Goods Sold", "5000", True),
            ("5108", "Closing Stock Adjustment", "Cost of Goods Sold", "5000", False),
            ("6000", "Operating Expenses", "Operating Expenses", None, False),
            ("6100", "Administrative Expenses", "Operating Expenses", "6000", False),
            ("6101", "Salary & Allowance", "Operating Expenses", "6100", False),
            ("6102", "Bonus Expense", "Operating Expenses", "6100", False),
            ("6103", "Office Rent", "Operating Expenses", "6100", False),
            ("6104", "Electricity Bill", "Operating Expenses", "6100", False),
            ("6105", "Water Bill", "Operating Expenses", "6100", False),
            ("6106", "Internet Bill", "Operating Expenses", "6100", False),
            ("6107", "Stationery Expense", "Operating Expenses", "6100", False),
            ("6108", "Printing Expense", "Operating Expenses", "6100", False),
            ("6109", "Mobile Bill expense", "Operating Expenses", "6100", False),
            ("6110", "Courier expense", "Operating Expenses", "6100", False),
            ("6111", "Entertainment expense", "Operating Expenses", "6100", False),
            ("6112", "Repair & Maintenance Expense", "Operating Expenses", "6100", False),
            ("6113", "Legal & professional fee", "Operating Expenses", "6100", False),
            ("6114", "ERP Subscription Fee", "Operating Expenses", "6100", False),
            ("6115", "Office Maintenance", "Operating Expenses", "6100", False),
            ("6116", "Cleaning Expense", "Operating Expenses", "6100", False),
            ("6117", "Depreciation Expense", "Operating Expenses", "6100", False),
            ("6200", "Selling & Distribution Expenses", "Operating Expenses", "6000", False),
            ("6201", "Transportation Expense", "Operating Expenses", "6200", False),
            ("6202", "Delivery Expense", "Operating Expenses", "6200", False),
            ("6203", "Fuel Expense", "Operating Expenses", "6200", False),
            ("6204", "Sales Commission / Incentive", "Operating Expenses", "6200", False),
            ("6205", "TA/DA Expense", "Operating Expenses", "6200", False),
            ("6206", "Marketing Expense", "Operating Expenses", "6200", False),
            ("6207", "Advertisement Expense", "Operating Expenses", "6200", False),
            ("6208", "Promotional Materials/Expense", "Operating Expenses", "6200", False),
            ("6300", "Finance Expenses", "Operating Expenses", "6000", False),
            ("6301", "Bank Charge", "Operating Expenses", "6300", False),
            ("6302", "Interest on Loan", "Operating Expenses", "6300", False),
            ("7000", "VAT & Tax Control Accounts", "VAT & Tax Control", None, False),
            ("7001", "Input VAT", "Assets", "7000", False),
            ("7002", "Output VAT", "Liabilities", "7000", False),
            ("7003", "VAT Adjustment Account", "Cost of Goods Sold", "7000", False),
            ("7004", "Advance Income Tax (AIT)", "Assets", "7000", False),
            ("7005", "Tax Deducted at Source (TDS)", "Liabilities", "7000", False),
            ("7006", "Tax Deducted at Source (VDS)", "Liabilities", "7000", False),
        ]

    def _upsert_account(self, code, name, at, is_contra, ngo_project):
        lookup = {"code": code, "ngo_project": ngo_project}
        obj, is_new = Account.objects.update_or_create(
            **lookup,
            defaults={
                "name": name,
                "account_type": at,
                "is_active": True,
                "is_contra": is_contra,
            },
        )
        return obj, is_new

    def _seed_accounts(self, types, ngo_project=None):
        accounts_data = self._accounts_data()
        created = {}
        global_bank_parents = {}

        # Always ensure global bank/cash hierarchy exists
        for code, name, type_name, parent_code, is_contra in accounts_data:
            if code not in BANK_CASH_CODES and code not in BANK_CASH_PARENT_CODES:
                continue
            at = types.get(type_name)
            obj, is_new = self._upsert_account(code, name, at, is_contra, None)
            global_bank_parents[code] = obj
            if code in BANK_CASH_CODES or ngo_project is None:
                action = "Created" if is_new else "Updated"
                scope = " [GLOBAL BANK]" if code in BANK_CASH_CODES else " [GLOBAL]"
                self.stdout.write(f"  {action}: {code} - {name}{scope}")

        for code, name, type_name, parent_code, is_contra in accounts_data:
            if ngo_project is not None and code in BANK_CASH_CODES:
                # Keep bank/cash global only — reuse for all projects
                created[code] = global_bank_parents[code]
                continue

            if ngo_project is not None and code in BANK_CASH_PARENT_CODES:
                # Project also gets its own asset headers; bank leaves stay global
                pass

            at = types.get(type_name)
            if ngo_project is None and code in BANK_CASH_CODES:
                created[code] = global_bank_parents[code]
                continue
            if ngo_project is None and code in BANK_CASH_PARENT_CODES:
                created[code] = global_bank_parents[code]
                continue

            obj, is_new = self._upsert_account(
                code, name, at, is_contra, ngo_project
            )
            created[code] = obj
            action = "Created" if is_new else "Updated"
            contra_tag = " [CONTRA]" if is_contra else ""
            scope = f" [P{ngo_project.id}]" if ngo_project else ""
            self.stdout.write(f"  {action}: {code} - {name}{contra_tag}{scope}")

        # Parent links — bank/cash always parent to global 1100
        updated = 0
        for code, name, type_name, parent_code, is_contra in accounts_data:
            if not parent_code:
                continue
            if code in BANK_CASH_CODES:
                obj = global_bank_parents.get(code)
                parent = global_bank_parents.get(parent_code)
                if obj and parent and obj.parent_id != parent.id:
                    obj.parent = parent
                    obj.save(update_fields=["parent"])
                    updated += 1
                continue

            obj = created.get(code)
            parent = created.get(parent_code)
            if obj and parent and obj.parent_id != parent.id:
                obj.parent = parent
                obj.save(update_fields=["parent"])
                updated += 1

        # Also link global parents if seeded for bank hierarchy
        for code, name, type_name, parent_code, is_contra in accounts_data:
            if code not in BANK_CASH_PARENT_CODES or not parent_code:
                continue
            obj = global_bank_parents.get(code)
            parent = global_bank_parents.get(parent_code)
            if obj and parent and obj.parent_id != parent.id:
                obj.parent = parent
                obj.save(update_fields=["parent"])
                updated += 1

        self.stdout.write(f"  Total accounts in scope: {len(created)}")
        self.stdout.write(f"  Parent links updated: {updated}")
