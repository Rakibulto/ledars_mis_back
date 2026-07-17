"""
Seed the assets module with LEDARS-specific fixed asset data that mirrors
the frontend demo-data constants exactly, so the workspace pages display
real backend records from day one.

Run: python manage.py seed_assets_workspace
     python manage.py seed_assets_workspace --clear   # wipe and re-seed
"""

from decimal import Decimal
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from accounting.models import (
    AssetCategory,
    Asset,
    AssetDepreciation,
    AssetDisposal,
    AssetImpairment,
    AssetTransfer,
    Vendor,
    CostCenter,
)

User = get_user_model()


# ── Canonical seed data ──────────────────────────────────────────────────────

CATEGORIES = [
    {
        "code": "VEH",
        "name": "Vehicles",
        "depreciation_method": "straight_line",
        "useful_life": 60,  # 5 years in months
        "salvage_percent": Decimal("10.00"),
        "asset_account_name": "1501 - Vehicles",
    },
    {
        "code": "IT",
        "name": "IT Equipment",
        "depreciation_method": "straight_line",
        "useful_life": 36,  # 3 years
        "salvage_percent": Decimal("5.00"),
        "asset_account_name": "1502 - IT Equipment",
    },
    {
        "code": "MED",
        "name": "Medical Equipment",
        "depreciation_method": "declining_balance",
        "useful_life": 48,  # 4 years
        "salvage_percent": Decimal("8.00"),
        "asset_account_name": "1503 - Medical Equipment",
    },
    {
        "code": "FUR",
        "name": "Furniture & Fixtures",
        "depreciation_method": "straight_line",
        "useful_life": 84,  # 7 years
        "salvage_percent": Decimal("5.00"),
        "asset_account_name": "1504 - Furniture & Fixtures",
    },
]

ASSETS = [
    {
        "code": "AST-001",
        "name": "Toyota Hilux Field Vehicle",
        "category_code": "VEH",
        "purchase_date": date(2024, 1, 15),
        "purchase_cost": Decimal("420000.00"),
        "current_value": Decimal("252000.00"),
        "status": "running",
        "location": "Dhaka HQ Garage",
        "custodian": "Logistics Lead",
        "condition": "good",
        "project_name": "Fleet Management",
        "serial_number": "AST-001-SN-1001",
        "vendor_name": "Toyota Bangladesh Ltd",
        "cost_center_name": "Operations",
    },
    {
        "code": "AST-002",
        "name": "Dell Laptops Batch 2025",
        "category_code": "IT",
        "purchase_date": date(2025, 3, 10),
        "purchase_cost": Decimal("180000.00"),
        "current_value": Decimal("96000.00"),
        "status": "running",
        "location": "ICT Lab Floor 2",
        "custodian": "IT Coordinator",
        "condition": "good",
        "project_name": "Digital Education",
        "serial_number": "AST-002-SN-1002",
        "vendor_name": "Dell Technologies BD",
        "cost_center_name": "ICT Department",
    },
    {
        "code": "AST-003",
        "name": "Clinic Cold Chain Unit",
        "category_code": "MED",
        "purchase_date": date(2025, 6, 1),
        "purchase_cost": Decimal("95000.00"),
        "current_value": Decimal("71250.00"),
        "status": "running",
        "location": "Jessore Clinic",
        "custodian": "Clinic Operations",
        "condition": "fair",
        "project_name": "Cold Chain",
        "serial_number": "AST-003-SN-1003",
        "vendor_name": "MedEquip International",
        "cost_center_name": "Health Program",
    },
    {
        "code": "AST-004",
        "name": "Retired Generator",
        "category_code": "VEH",
        "purchase_date": date(2021, 5, 1),
        "purchase_cost": Decimal("64000.00"),
        "current_value": Decimal("0.00"),
        "status": "disposed",
        "location": "Warehouse Yard",
        "custodian": "Warehouse Officer",
        "condition": "retired",
        "project_name": "Power Backup",
        "serial_number": "AST-004-SN-1004",
        "vendor_name": "Energen Solutions",
        "cost_center_name": "Operations",
        "disposal": {
            "disposal_date": date(2026, 2, 11),
            "disposal_method": "sale",
            "sale_amount": Decimal("5000.00"),
            "gain_loss": Decimal("-4500.00"),
            "notes": "Disposed after repeated generator failure and replacement approval.",
        },
    },
    {
        "code": "AST-005",
        "name": "Boardroom Conference Furniture Set",
        "category_code": "FUR",
        "purchase_date": date(2025, 8, 20),
        "purchase_cost": Decimal("128000.00"),
        "current_value": Decimal("109714.00"),
        "status": "running",
        "location": "Dhaka HQ Garage",
        "custodian": "Logistics Lead",
        "condition": "good",
        "project_name": "General Fund",
        "serial_number": "AST-005-SN-1005",
        "vendor_name": "Office World BD",
        "cost_center_name": "Administration",
    },
    {
        "code": "AST-006",
        "name": "Archive Desktop Fleet",
        "category_code": "IT",
        "purchase_date": date(2022, 12, 1),
        "purchase_cost": Decimal("76000.00"),
        "current_value": Decimal("3800.00"),
        "status": "fully_depreciated",
        "location": "ICT Lab Floor 2",
        "custodian": "IT Coordinator",
        "condition": "retired",
        "project_name": "Digital Education",
        "serial_number": "AST-006-SN-1006",
        "vendor_name": "Dell Technologies BD",
        "cost_center_name": "ICT Department",
    },
]

# Impairment records (linked by asset code)
IMPAIRMENTS = [
    {
        "asset_code": "AST-003",
        "date": date(2026, 2, 14),
        "amount": Decimal("8000.00"),
        "reason": "Cooling capacity downgraded after power fluctuations.",
        "reviewer": "Finance Controller",
    },
]

# Internal transfer records (linked by asset code)
TRANSFERS = [
    {
        "asset_code": "AST-001",
        "date": date(2025, 11, 9),
        "from_location": "Dhaka HQ Garage",
        "to_location": "Cox's Bazar Field Office",
        "assignee": "Field Logistics Officer",
        "reason": "Vehicle redeployed to emergency response program.",
    },
]


class Command(BaseCommand):
    help = "Seed LEDARS fixed asset workspace with canonical demo data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing asset data before re-seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("  Clearing existing asset data...")
            AssetTransfer.objects.all().delete()
            AssetImpairment.objects.all().delete()
            AssetDisposal.objects.all().delete()
            AssetDepreciation.objects.all().delete()
            Asset.objects.all().delete()
            AssetCategory.objects.all().delete()
            self.stdout.write(self.style.WARNING("  Existing data cleared."))

        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR("No user found – create a user first."))
            return

        try:
            with transaction.atomic():
                self._seed(user)
            self.stdout.write(self.style.SUCCESS("Asset workspace seeded successfully!"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Seeding failed: {exc}"))
            raise

    def _seed(self, user):
        # 1 – Categories
        self.stdout.write("  Seeding asset categories...")
        cat_map = {}
        for data in CATEGORIES:
            cat, _ = AssetCategory.objects.update_or_create(
                code=data["code"],
                defaults={
                    "name": data["name"],
                    "depreciation_method": data["depreciation_method"],
                    "useful_life": data["useful_life"],
                    "salvage_percent": data["salvage_percent"],
                    "is_active": True,
                },
            )
            cat_map[data["code"]] = cat
        self.stdout.write(f"    {len(cat_map)} categories ready.")

        # 2 – Ensure vendors / cost-centers exist (get_or_create)
        self.stdout.write("  Ensuring vendors & cost centers...")
        vendor_names = {a["vendor_name"] for a in ASSETS}
        vendor_map = {}
        for vname in vendor_names:
            v, _ = Vendor.objects.get_or_create(
                name=vname,
                defaults={"email": "", "phone": "", "status": "active"},
            )
            vendor_map[vname] = v

        cc_names = {a["cost_center_name"] for a in ASSETS}
        cc_map = {}
        for ccname in cc_names:
            cc, _ = CostCenter.objects.get_or_create(
                name=ccname,
                defaults={"code": ccname[:20].upper().replace(" ", "-")},
            )
            cc_map[ccname] = cc

        # 3 – Assets
        self.stdout.write("  Seeding assets...")
        asset_map = {}
        for data in ASSETS:
            cat = cat_map[data["category_code"]]
            vendor = vendor_map[data["vendor_name"]]
            cost_center = cc_map[data["cost_center_name"]]
            asset, _ = Asset.objects.update_or_create(
                code=data["code"],
                defaults={
                    "name": data["name"],
                    "category": cat,
                    "purchase_date": data["purchase_date"],
                    "purchase_cost": data["purchase_cost"],
                    "salvage_value": (data["purchase_cost"] * cat.salvage_percent / 100).quantize(
                        Decimal("0.01")
                    ),
                    "current_value": data["current_value"],
                    "depreciation_method": cat.depreciation_method,
                    "useful_life": cat.useful_life,
                    "depreciation_start_date": data["purchase_date"],
                    "serial_number": data["serial_number"],
                    "location": data["location"],
                    "custodian": data["custodian"],
                    "condition": data["condition"],
                    "project_name": data["project_name"],
                    "schedule_revision": 1,
                    "status": data["status"],
                    "vendor": vendor,
                    "cost_center": cost_center,
                    "created_by": user,
                },
            )
            asset_map[data["code"]] = asset

            # Disposal
            if "disposal" in data and not hasattr(asset, "_disposal_seeded"):
                d = data["disposal"]
                AssetDisposal.objects.update_or_create(
                    asset=asset,
                    defaults={
                        "disposal_date": d["disposal_date"],
                        "disposal_method": d["disposal_method"],
                        "sale_amount": d["sale_amount"],
                        "gain_loss": d["gain_loss"],
                        "notes": d["notes"],
                        "created_by": user,
                    },
                )

        self.stdout.write(f"    {len(asset_map)} assets ready.")

        # 4 – Depreciation lines (generate posted lines up to today)
        self.stdout.write("  Generating depreciation lines...")
        from datetime import date as date_cls
        today = date_cls.today()
        total_lines = 0
        for asset in asset_map.values():
            if asset.status == "disposed":
                continue
            # Only add lines if none exist yet
            if asset.depreciation_lines.exists():
                continue
            purchase_cost = float(asset.purchase_cost)
            salvage = float(asset.salvage_value)
            life = int(asset.useful_life)
            depreciable = max(purchase_cost - salvage, 0)
            monthly_amount = round(depreciable / max(life, 1), 2) if life else 0
            current_val = purchase_cost
            purchase_date = asset.purchase_date

            # Calculate how many months have elapsed
            elapsed = (today.year - purchase_date.year) * 12 + (today.month - purchase_date.month)
            posted_periods = min(elapsed, life - 1)

            lines = []
            accum = 0
            for period in range(1, life + 1):
                period_date = date_cls(
                    purchase_date.year + (purchase_date.month + period - 2) // 12,
                    (purchase_date.month + period - 2) % 12 + 1,
                    1,
                )
                amount = min(monthly_amount, max(current_val - salvage, 0))
                accum = round(accum + amount, 2)
                remaining = round(max(current_val - amount, salvage), 2)
                line_status = "posted" if period <= posted_periods else "planned"
                lines.append(
                    AssetDepreciation(
                        asset=asset,
                        date=period_date,
                        period=period,
                        depreciation_amount=Decimal(str(amount)),
                        accumulated_depreciation=Decimal(str(accum)),
                        remaining_value=Decimal(str(remaining)),
                        status=line_status,
                    )
                )
                current_val = remaining
                if remaining <= salvage:
                    break

            AssetDepreciation.objects.bulk_create(lines, ignore_conflicts=True)
            total_lines += len(lines)
        self.stdout.write(f"    {total_lines} depreciation lines ready.")

        # 5 – Impairments
        self.stdout.write("  Seeding impairments...")
        for data in IMPAIRMENTS:
            asset = asset_map.get(data["asset_code"])
            if not asset:
                continue
            AssetImpairment.objects.get_or_create(
                asset=asset,
                date=data["date"],
                defaults={
                    "amount": data["amount"],
                    "reason": data["reason"],
                    "reviewer": data["reviewer"],
                },
            )
        self.stdout.write(f"    {len(IMPAIRMENTS)} impairment records ready.")

        # 6 – Transfers
        self.stdout.write("  Seeding transfers...")
        for data in TRANSFERS:
            asset = asset_map.get(data["asset_code"])
            if not asset:
                continue
            AssetTransfer.objects.get_or_create(
                asset=asset,
                date=data["date"],
                defaults={
                    "from_location": data["from_location"],
                    "to_location": data["to_location"],
                    "assignee": data["assignee"],
                    "reason": data["reason"],
                },
            )
        self.stdout.write(f"    {len(TRANSFERS)} transfer records ready.")
