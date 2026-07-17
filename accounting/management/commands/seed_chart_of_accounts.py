"""
Seed chart of accounts with exact LEDARS structure.
Run: python manage.py seed_chart_of_accounts
Run (clear + reseed): python manage.py seed_chart_of_accounts --clear
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from accounting.models import AccountType, AccountGroup, Account


class Command(BaseCommand):
    help = "Seed chart of accounts (AccountTypes, AccountGroups, Accounts)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear all existing accounts, groups, and types before seeding",
        )

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                if options["clear"]:
                    self.stdout.write("Clearing existing COA data...")
                    Account.objects.all().delete()
                    AccountGroup.objects.all().delete()
                    AccountType.objects.all().delete()
                    self.stdout.write(self.style.WARNING("All accounts, groups, and types deleted."))
                self.seed()
            self.stdout.write(self.style.SUCCESS("Chart of accounts seeded successfully!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Seeding failed: {e}"))

    def seed(self):
        types = self._seed_account_types()
        self._seed_accounts(types)

    def _seed_account_types(self):
        data = [
            ("Assets", "asset", "current"),
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
                defaults={"classification": classification, "liquidity_type": liquidity, "is_active": True},
            )
            created[name] = obj
            if is_new:
                self.stdout.write(f"  + AccountType: {name}")
        return created

    def _seed_accounts(self, types):
        # Structure: (code, name, type_name, parent_code, is_contra)
        # parent_code=None means root account (no parent)
        accounts_data = [
            # ══════════════════════════════════════════════════════════════
            # 1. Assets (1xxx)
            # ══════════════════════════════════════════════════════════════
            ("1000", "Assets", "Assets", None, False),
            ("1100", "Current Assets", "Assets", "1000", False),
            ("1101", "Cash In Hand", "Assets", "1100", False),
            ("1102", "Petty Cash", "Assets", "1100", False),
            ("1103", "Cash at Bank - Dutch Bangla Bank", "Assets", "1100", False),
            ("1104", "Cash at Bank - BRAC Bank", "Assets", "1100", False),
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

            # ══════════════════════════════════════════════════════════════
            # 2. Liabilities (2xxx)
            # ══════════════════════════════════════════════════════════════
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

            # ══════════════════════════════════════════════════════════════
            # 3. Shareholders' Equity (3xxx)
            # ══════════════════════════════════════════════════════════════
            ("3000", "Shareholders' Equity", "Shareholders Equity", None, False),
            ("3001", "Paid up Capital", "Shareholders Equity", "3000", False),
            ("3002", "Additional Capital", "Shareholders Equity", "3000", False),
            ("3003", "Retained Earnings", "Shareholders Equity", "3000", False),
            ("3004", "Partner's Capital", "Shareholders Equity", "3000", False),
            ("3005", "Drawings", "Shareholders Equity", "3000", True),

            # ══════════════════════════════════════════════════════════════
            # 4. Revenue (4xxx)
            # ══════════════════════════════════════════════════════════════
            ("4000", "Revenue", "Revenue", None, False),
            ("4101", "Sales Revenue", "Revenue", "4000", False),
            ("4102", "Sales Return", "Revenue", "4000", True),
            ("4103", "Sales Discount", "Revenue", "4000", True),
            ("4200", "Other Income", "Revenue", None, False),
            ("4201", "Commission Income", "Revenue", "4200", False),
            ("4202", "Interest Income", "Revenue", "4200", False),
            ("4203", "Miscellaneous Income", "Revenue", "4200", False),
            ("4204", "Wastage sale", "Revenue", "4200", False),

            # ══════════════════════════════════════════════════════════════
            # 5. Cost of Goods Sold (5xxx)
            # ══════════════════════════════════════════════════════════════
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

            # ══════════════════════════════════════════════════════════════
            # 6. Operating Expenses (6xxx)
            # ══════════════════════════════════════════════════════════════
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

            # ══════════════════════════════════════════════════════════════
            # 7. VAT & Tax Control Accounts (7xxx)
            # ══════════════════════════════════════════════════════════════
            ("7000", "VAT & Tax Control Accounts", "VAT & Tax Control", None, False),
            ("7001", "Input VAT", "Assets", "7000", False),
            ("7002", "Output VAT", "Liabilities", "7000", False),
            ("7003", "VAT Adjustment Account", "Cost of Goods Sold", "7000", False),
            ("7004", "Advance Income Tax (AIT)", "Assets", "7000", False),
            ("7005", "Tax Deducted at Source (TDS)", "Liabilities", "7000", False),
            ("7006", "Tax Deducted at Source (VDS)", "Liabilities", "7000", False),
        ]

        # First pass: create all accounts (without parents)
        created = {}
        for code, name, type_name, parent_code, is_contra in accounts_data:
            at = types.get(type_name)
            obj, is_new = Account.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "account_type": at,
                    "is_active": True,
                    "is_contra": is_contra,
                },
            )
            created[code] = obj
            action = "Created" if is_new else "Updated"
            contra_tag = " [CONTRA]" if is_contra else ""
            self.stdout.write(f"  {action}: {code} - {name}{contra_tag}")

        # Second pass: set parent relationships
        updated = 0
        for code, name, type_name, parent_code, is_contra in accounts_data:
            if parent_code and parent_code in created:
                obj = created[code]
                parent = created[parent_code]
                if obj.parent_id != parent.id:
                    obj.parent = parent
                    obj.save(update_fields=["parent"])
                    updated += 1

        self.stdout.write(f"  Total accounts: {len(created)}")
        self.stdout.write(f"  Parent links updated: {updated}")
