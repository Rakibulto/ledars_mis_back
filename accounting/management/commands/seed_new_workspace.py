"""
Seed the 5 new accounting workspace transaction pages:
  - CashWorkspaceTransaction
  - ContraEntry
  - ExpenseEntry
  - PayrollEntry
  - InventoryEntry

Also ensures DeferredRevenue and DeferredExpense have realistic data with
all required fields (reference, periods, description).

Run:
    python manage.py seed_new_workspace
    python manage.py seed_new_workspace --clear   (wipe and re-seed)
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounting.models import (
    CashWorkspaceTransaction,
    ContraEntry,
    ExpenseEntry,
    PayrollEntry,
    InventoryEntry,
    DeferredRevenue,
    DeferredExpense,
)

User = get_user_model()

TODAY = date(2026, 4, 12)


def d(delta: int) -> date:
    return TODAY + timedelta(days=delta)


class Command(BaseCommand):
    help = "Seed new accounting workspace pages with realistic LEDARS NGO data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing records before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            InventoryEntry.objects.all().delete()
            PayrollEntry.objects.all().delete()
            ExpenseEntry.objects.all().delete()
            ContraEntry.objects.all().delete()
            CashWorkspaceTransaction.objects.all().delete()
            DeferredRevenue.objects.all().delete()
            DeferredExpense.objects.all().delete()
            self.stdout.write("  Cleared existing new-workspace data.")

        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not user:
            self.stderr.write("No user found — please create a user first.")
            return

        self._seed_cash(user)
        self._seed_contra(user)
        self._seed_expense(user)
        self._seed_payroll(user)
        self._seed_inventory(user)
        self._seed_deferred_revenue(user)
        self._seed_deferred_expense(user)

        self.stdout.write(self.style.SUCCESS("\n✅  New-workspace seed complete!"))

    # ── Cash Workspace Transactions ───────────────────────────────────────────

    def _seed_cash(self, user):
        if CashWorkspaceTransaction.objects.exists():
            self.stdout.write("  CashWorkspaceTransactions: already seeded, skipping.")
            return

        rows = [
            {
                "date": d(-30),
                "account": "Petty Cash – Main Office",
                "counterparty": "Field Operations Team",
                "direction": "outflow",
                "amount": Decimal("12500.00"),
                "payment_method": "Cash",
                "reference": "PCR-2026-031",
                "description": "Field distribution – March round 1",
                "status": "posted",
            },
            {
                "date": d(-22),
                "account": "Petty Cash – Sylhet Office",
                "counterparty": "UNHCR Liaison",
                "direction": "inflow",
                "amount": Decimal("45000.00"),
                "payment_method": "Bank Transfer",
                "reference": "UNHCR-CASH-2026-03",
                "description": "Q1 cash grant instalment received",
                "status": "posted",
            },
            {
                "date": d(-15),
                "account": "Petty Cash – Main Office",
                "counterparty": "HealthServe Supplies Ltd",
                "direction": "outflow",
                "amount": Decimal("8750.00"),
                "payment_method": "Cash",
                "reference": "PCR-2026-032",
                "description": "Medical consumables – emergency purchase",
                "status": "draft",
            },
            {
                "date": d(-7),
                "account": "Petty Cash – Cox's Bazar",
                "counterparty": "Local Transport Vendor",
                "direction": "outflow",
                "amount": Decimal("3200.00"),
                "payment_method": "Cash",
                "reference": "PCR-2026-033",
                "description": "Vehicle hire for field visit",
                "status": "draft",
            },
            {
                "date": d(-3),
                "account": "Petty Cash – Main Office",
                "counterparty": "Save The Children",
                "direction": "inflow",
                "amount": Decimal("20000.00"),
                "payment_method": "Cheque",
                "reference": "STC-REIMB-2026-04",
                "description": "Reimbursement for joint field activities",
                "status": "draft",
            },
        ]
        for row in rows:
            CashWorkspaceTransaction.objects.create(**row, created_by=user)
        self.stdout.write(f"  CashWorkspaceTransactions: {CashWorkspaceTransaction.objects.count()} seeded.")

    # ── Contra Entries ────────────────────────────────────────────────────────

    def _seed_contra(self, user):
        if ContraEntry.objects.exists():
            self.stdout.write("  ContraEntries: already seeded, skipping.")
            return

        rows = [
            {
                "date": d(-28),
                "from_account": "Bank – NGO Operations Dhaka",
                "to_account": "Petty Cash – Main Office",
                "transfer_channel": "Internal Transfer",
                "treasury_owner": "Finance Controller",
                "reference": "CT-2026-031",
                "amount": Decimal("50000.00"),
                "description": "Monthly petty cash replenishment – March 2026",
                "status": "posted",
            },
            {
                "date": d(-18),
                "from_account": "Petty Cash – Sylhet Office",
                "to_account": "Bank – Project Account Sylhet",
                "transfer_channel": "Cash Deposit",
                "treasury_owner": "Regional Finance Officer",
                "reference": "CT-2026-032",
                "amount": Decimal("32500.00"),
                "description": "Excess petty cash deposited post field mission",
                "status": "posted",
            },
            {
                "date": d(-10),
                "from_account": "Bank – NGO Operations Dhaka",
                "to_account": "Petty Cash – Cox's Bazar",
                "transfer_channel": "Internal Transfer",
                "treasury_owner": "Finance Controller",
                "reference": "CT-2026-033",
                "amount": Decimal("15000.00"),
                "description": "Emergency field fund top-up",
                "status": "draft",
            },
            {
                "date": d(-5),
                "from_account": "Bank – Project Account Sylhet",
                "to_account": "Bank – NGO Operations Dhaka",
                "transfer_channel": "Bank Transfer",
                "treasury_owner": "Finance Head",
                "reference": "CT-2026-034",
                "amount": Decimal("120000.00"),
                "description": "Grant balance consolidation to main account",
                "status": "draft",
            },
        ]
        for row in rows:
            ContraEntry.objects.create(**row, created_by=user)
        self.stdout.write(f"  ContraEntries: {ContraEntry.objects.count()} seeded.")

    # ── Expense Entries ───────────────────────────────────────────────────────

    def _seed_expense(self, user):
        if ExpenseEntry.objects.exists():
            self.stdout.write("  ExpenseEntries: already seeded, skipping.")
            return

        rows = [
            {
                "date": d(-29),
                "category": "Travel & Transport",
                "employee": "Karim Hossain",
                "cost_center": "Field Operations",
                "approval_route": "Field Manager",
                "reference": "EXP-REF-2026-031",
                "amount": Decimal("6800.00"),
                "description": "Dhaka to Cox's Bazar field visit – March 2026",
                "status": "posted",
            },
            {
                "date": d(-24),
                "category": "Office Supplies",
                "employee": "Rina Akter",
                "cost_center": "Administration",
                "approval_route": "Admin Manager",
                "reference": "EXP-REF-2026-032",
                "amount": Decimal("2350.00"),
                "description": "Q1 stationery and printer consumables",
                "status": "posted",
            },
            {
                "date": d(-17),
                "category": "Medical Supplies",
                "employee": "Dr. Nasrin Islam",
                "cost_center": "Health Programme",
                "approval_route": "Programme Director",
                "reference": "EXP-REF-2026-033",
                "amount": Decimal("18900.00"),
                "description": "Emergency ORS and wound care kits – Sylhet district",
                "status": "submitted",
            },
            {
                "date": d(-11),
                "category": "Communication",
                "employee": "Nadia Islam",
                "cost_center": "MEAL Unit",
                "approval_route": "MEAL Coordinator",
                "reference": "EXP-REF-2026-034",
                "amount": Decimal("1450.00"),
                "description": "Mobile data and calling cards – field monitors",
                "status": "submitted",
            },
            {
                "date": d(-4),
                "category": "Training & Capacity Building",
                "employee": "Md. Rafiq",
                "cost_center": "HR Department",
                "approval_route": "HR Head",
                "reference": "EXP-REF-2026-035",
                "amount": Decimal("9500.00"),
                "description": "Safeguarding training workshop – April cohort",
                "status": "submitted",
            },
        ]
        for row in rows:
            ExpenseEntry.objects.create(**row, created_by=user)
        self.stdout.write(f"  ExpenseEntries: {ExpenseEntry.objects.count()} seeded.")

    # ── Payroll Entries ───────────────────────────────────────────────────────

    def _seed_payroll(self, user):
        if PayrollEntry.objects.exists():
            self.stdout.write("  PayrollEntries: already seeded, skipping.")
            return

        rows = [
            {
                "date": d(-31),
                "payroll_cycle": "Monthly – March 2026",
                "period_start": date(2026, 3, 1),
                "period_end": date(2026, 3, 31),
                "employee_count": 87,
                "gross_amount": Decimal("3850000.00"),
                "net_amount": Decimal("3412000.00"),
                "approval_route": "Finance Controller → ED",
                "funding_source": "UNHCR Project Fund",
                "description": "Main staff payroll – March 2026 full cycle",
                "status": "posted",
            },
            {
                "date": d(-28),
                "payroll_cycle": "Casual Labour – March W4",
                "period_start": date(2026, 3, 22),
                "period_end": date(2026, 3, 31),
                "employee_count": 34,
                "gross_amount": Decimal("620000.00"),
                "net_amount": Decimal("585000.00"),
                "approval_route": "Field Manager → Finance Controller",
                "funding_source": "World Vision Field Budget",
                "description": "Casual labourers – Sylhet distribution drive",
                "status": "posted",
            },
            {
                "date": d(-3),
                "payroll_cycle": "Monthly – April 2026",
                "period_start": date(2026, 4, 1),
                "period_end": date(2026, 4, 30),
                "employee_count": 89,
                "gross_amount": Decimal("3920000.00"),
                "net_amount": Decimal("3476000.00"),
                "approval_route": "Finance Controller → ED",
                "funding_source": "UNHCR Project Fund",
                "description": "Main staff payroll – April 2026 draft",
                "status": "draft",
            },
        ]
        for row in rows:
            PayrollEntry.objects.create(**row, created_by=user)
        self.stdout.write(f"  PayrollEntries: {PayrollEntry.objects.count()} seeded.")

    # ── Inventory Entries ─────────────────────────────────────────────────────

    def _seed_inventory(self, user):
        if InventoryEntry.objects.exists():
            self.stdout.write("  InventoryEntries: already seeded, skipping.")
            return

        rows = [
            {
                "date": d(-27),
                "warehouse": "Central Warehouse – Dhaka",
                "category": "Medical Supplies",
                "movement_type": "Receipt",
                "item_reference": "ORS-500ML-SACHET",
                "quantity": Decimal("2500"),
                "unit_cost": Decimal("18.50"),
                "procurement_reference": "PO-2026-031",
                "description": "Oral rehydration salts received from HealthServe",
                "status": "posted",
            },
            {
                "date": d(-21),
                "warehouse": "Central Warehouse – Dhaka",
                "category": "Non-Food Items",
                "movement_type": "Issuance",
                "item_reference": "HYGIENE-KIT-FAMILY",
                "quantity": Decimal("400"),
                "unit_cost": Decimal("850.00"),
                "procurement_reference": "WO-2026-022",
                "description": "Hygiene kits issued for Sylhet field distribution",
                "status": "posted",
            },
            {
                "date": d(-14),
                "warehouse": "Field Store – Cox's Bazar",
                "category": "Food Commodities",
                "movement_type": "Transfer",
                "item_reference": "RICE-50KG-BAG",
                "quantity": Decimal("120"),
                "unit_cost": Decimal("3200.00"),
                "procurement_reference": "WFP-TRANSFER-2026-08",
                "description": "WFP rice transfer to Cox's Bazar sub-store",
                "status": "draft",
            },
            {
                "date": d(-8),
                "warehouse": "Central Warehouse – Dhaka",
                "category": "Office Equipment",
                "movement_type": "Receipt",
                "item_reference": "LAPTOP-DELL-I5",
                "quantity": Decimal("5"),
                "unit_cost": Decimal("65000.00"),
                "procurement_reference": "PO-2026-044",
                "description": "IT equipment for MEAL unit upgrade",
                "status": "draft",
            },
            {
                "date": d(-2),
                "warehouse": "Field Store – Sylhet",
                "category": "Medical Supplies",
                "movement_type": "Adjustment",
                "item_reference": "PARACETAMOL-500MG-STRIP",
                "quantity": Decimal("-50"),
                "unit_cost": Decimal("12.00"),
                "procurement_reference": "",
                "description": "Inventory write-off – expired stock",
                "status": "draft",
            },
        ]
        for row in rows:
            InventoryEntry.objects.create(**row, created_by=user)
        self.stdout.write(f"  InventoryEntries: {InventoryEntry.objects.count()} seeded.")

    # ── Deferred Revenue ──────────────────────────────────────────────────────

    def _seed_deferred_revenue(self, user):
        if DeferredRevenue.objects.exists():
            self.stdout.write("  DeferredRevenue: already seeded, skipping.")
            return

        rows = [
            {
                "reference": "UNEARNED-2026-01",
                "name": "UNHCR Multi-Year Grant – 2025-2026",
                "total_amount": Decimal("1200000.00"),
                "recognized_amount": Decimal("900000.00"),
                "remaining_amount": Decimal("300000.00"),
                "start_date": date(2025, 1, 1),
                "end_date": date(2026, 12, 31),
                "periods": 24,
                "description": "Multi-year humanitarian grant – Q3 2025 start",
                "status": "running",
            },
            {
                "reference": "UNEARNED-2026-02",
                "name": "Save The Children Service Contract Q1",
                "total_amount": Decimal("480000.00"),
                "recognized_amount": Decimal("160000.00"),
                "remaining_amount": Decimal("320000.00"),
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 6, 30),
                "periods": 6,
                "description": "Q1/Q2 service delivery contract revenue",
                "status": "running",
            },
            {
                "reference": "UNEARNED-2026-03",
                "name": "UNICEF Retainer – Health Programme",
                "total_amount": Decimal("720000.00"),
                "recognized_amount": Decimal("720000.00"),
                "remaining_amount": Decimal("0.00"),
                "start_date": date(2025, 4, 1),
                "end_date": date(2026, 3, 31),
                "periods": 12,
                "description": "Completed annual health programme retainer",
                "status": "fully_recognized",
            },
            {
                "reference": "UNEARNED-2026-04",
                "name": "World Vision Field Partnership – April Tranche",
                "total_amount": Decimal("360000.00"),
                "recognized_amount": Decimal("0.00"),
                "remaining_amount": Decimal("360000.00"),
                "start_date": date(2026, 4, 1),
                "end_date": date(2026, 9, 30),
                "periods": 6,
                "description": "New partnership tranche – pending first recognition",
                "status": "draft",
            },
        ]
        for row in rows:
            DeferredRevenue.objects.create(**row, created_by=user)
        self.stdout.write(f"  DeferredRevenue: {DeferredRevenue.objects.count()} seeded.")

    # ── Deferred Expense ──────────────────────────────────────────────────────

    def _seed_deferred_expense(self, user):
        if DeferredExpense.objects.exists():
            self.stdout.write("  DeferredExpense: already seeded, skipping.")
            return

        rows = [
            {
                "reference": "PREPAID-2026-01",
                "name": "Office Lease – Main Dhaka HQ",
                "total_amount": Decimal("600000.00"),
                "recognized_amount": Decimal("150000.00"),
                "remaining_amount": Decimal("450000.00"),
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 12, 31),
                "periods": 12,
                "description": "Annual office lease prepaid January 2026",
                "status": "running",
            },
            {
                "reference": "PREPAID-2026-02",
                "name": "Vehicle Insurance – Fleet Policy",
                "total_amount": Decimal("180000.00"),
                "recognized_amount": Decimal("45000.00"),
                "remaining_amount": Decimal("135000.00"),
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 12, 31),
                "periods": 12,
                "description": "Annual fleet insurance premium – prepaid",
                "status": "running",
            },
            {
                "reference": "PREPAID-2026-03",
                "name": "ERP Software Licence – Annual",
                "total_amount": Decimal("240000.00"),
                "recognized_amount": Decimal("80000.00"),
                "remaining_amount": Decimal("160000.00"),
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 12, 31),
                "periods": 12,
                "description": "Annual ERP/HRIS licence fee paid upfront",
                "status": "running",
            },
            {
                "reference": "PREPAID-2025-01",
                "name": "Field Generator Maintenance Contract",
                "total_amount": Decimal("96000.00"),
                "recognized_amount": Decimal("96000.00"),
                "remaining_amount": Decimal("0.00"),
                "start_date": date(2025, 7, 1),
                "end_date": date(2026, 3, 31),
                "periods": 9,
                "description": "Completed generator AMC for field offices",
                "status": "fully_recognized",
            },
        ]
        for row in rows:
            DeferredExpense.objects.create(**row, created_by=user)
        self.stdout.write(f"  DeferredExpense: {DeferredExpense.objects.count()} seeded.")
