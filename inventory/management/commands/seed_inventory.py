"""
Seed comprehensive LEDARS NGO inventory data.
Run: python manage.py seed_inventory
"""

import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Seed LEDARS inventory with comprehensive NGO data"

    def handle(self, *args, **options):
        from inventory.models import (
            Category,
            UnitOfMeasure,
            Product,
            Warehouse,
            StorageLocation,
            PutawayRule,
            RemovalStrategy,
            OperationType,
            Route,
            ShippingMethod,
            PackagingType,
            ProductTemplate,
            ProductVariant,
            GRNSequence,
            GRN,
            GRNLineItem,
            GINSequence,
            GIN,
            GINLineItem,
            StockTransferSequence,
            StockTransfer,
            StockTransferLine,
            StockAdjustmentSequence,
            StockAdjustment,
            StockAdjustmentLine,
            LotSerial,
            StockMove,
            QualityCheck,
            QualityAlert,
            QualityControlPoint,
            QualityTeam,
            QCTemplate,
            InventoryValuation,
            LandedCost,
            ScrapRecord,
            ReturnRecord,
            ReorderRule,
            KittingBOM,
            KittingBOMLine,
            DonorFundedInventory,
            FieldDistribution,
            InventorySettings,
        )
        from vendorportal.models.models import VendorProfile

        user = User.objects.first()
        self.stdout.write("Clearing old inventory data...")

        # Clear in dependency order
        for M in [
            FieldDistribution,
            DonorFundedInventory,
            KittingBOMLine,
            KittingBOM,
            ReorderRule,
            ReturnRecord,
            ScrapRecord,
            LandedCost,
            InventoryValuation,
            QCTemplate,
            QualityControlPoint,
            QualityAlert,
            QualityCheck,
            QualityTeam,
            StockMove,
            LotSerial,
            StockAdjustmentLine,
            StockAdjustment,
            StockAdjustmentSequence,
            StockTransferLine,
            StockTransfer,
            StockTransferSequence,
            GINLineItem,
            GIN,
            GINSequence,
            GRNLineItem,
            GRN,
            GRNSequence,
            ProductVariant,
            ProductTemplate,
            PackagingType,
            PutawayRule,
            RemovalStrategy,
            OperationType,
            Route,
            ShippingMethod,
            StorageLocation,
            Warehouse,
            InventorySettings,
        ]:
            M.objects.all().delete()

        # Delete products and categories that don't have procurement FK refs
        Product.objects.all().delete()
        Category.objects.all().delete()

        self.stdout.write("Seeding inventory data...")

        # ── Categories (20 - matching frontend demo-data) ──
        cats = {}
        main_cats = [
            ("CAT-001", "IT Equipment", "standard"),
            ("CAT-002", "Office Supplies", "average"),
            ("CAT-003", "Furniture", "standard"),
            ("CAT-004", "Medical Supplies", "fifo"),
            ("CAT-005", "Relief Items", "fifo"),
            ("CAT-006", "Vehicle Parts", "average"),
            ("CAT-007", "Field Equipment", "standard"),
            ("CAT-008", "Communication", "standard"),
        ]
        for code, name, costing in main_cats:
            obj, _ = Category.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "level": "Main",
                    "costing_method": costing,
                    "status": "Active",
                    "created_by": user,
                },
            )
            cats[code] = obj

        sub_cats = [
            ("CAT-009", "Laptops", "CAT-001"),
            ("CAT-010", "Desktops", "CAT-001"),
            ("CAT-011", "Networking", "CAT-001"),
            ("CAT-012", "Stationery", "CAT-002"),
            ("CAT-013", "Printing", "CAT-002"),
            ("CAT-014", "Office Furniture", "CAT-003"),
            ("CAT-015", "Field Furniture", "CAT-003"),
            ("CAT-016", "Medicines", "CAT-004"),
            ("CAT-017", "First Aid", "CAT-004"),
            ("CAT-018", "Food", "CAT-005"),
            ("CAT-019", "Shelter Materials", "CAT-005"),
            ("CAT-020", "Hygiene Kits", "CAT-005"),
        ]
        for code, name, parent_code in sub_cats:
            obj, _ = Category.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "level": "Sub",
                    "parent": cats[parent_code],
                    "status": "Active",
                    "created_by": user,
                },
            )
            cats[code] = obj

        self.stdout.write(f"  Categories: {Category.objects.count()}")

        # ── Units of Measure (15) ──
        uoms = {}
        uom_data = [
            ("Piece", "pcs", "unit", 1),
            ("Unit", "unit", "unit", 1),
            ("Box", "box", "unit", 1),
            ("Carton", "ctn", "unit", 1),
            ("Pack", "pack", "unit", 1),
            ("Kilogram", "kg", "weight", 1),
            ("Gram", "g", "weight", 0.001),
            ("Ton", "ton", "weight", 1000),
            ("Liter", "L", "volume", 1),
            ("Milliliter", "mL", "volume", 0.001),
            ("Meter", "m", "length", 1),
            ("Centimeter", "cm", "length", 0.01),
            ("Roll", "roll", "unit", 1),
            ("Sheet", "sht", "unit", 1),
            ("Tablet", "tab", "unit", 1),
        ]
        for name, code, category, ratio in uom_data:
            obj, _ = UnitOfMeasure.objects.update_or_create(
                name=name,
                defaults={
                    "is_active": True,
                },
            )
            uoms[name] = obj

        self.stdout.write(f"  UOMs: {UnitOfMeasure.objects.count()}")

        # ── Suppliers (get or create) ──
        suppliers = {}
        sup_data = [
            ("Dell Bangladesh", "dell@bd.com", "01711111111"),
            ("PharmaCo Ltd.", "pharma@co.com", "01722222222"),
            ("Local Rice Mill", "rice@mill.com", "01733333333"),
            ("Office World", "office@world.com", "01744444444"),
            ("Kit Assembly Unit", "kit@assembly.com", "01755555555"),
            ("AquaSafe International", "aqua@safe.com", "01766666666"),
            ("TechComm Systems", "tech@comm.com", "01777777777"),
        ]
        for name, email, phone in sup_data:
            obj, _ = VendorProfile.objects.get_or_create(
                name=name,
                defaults={
                    "email": email,
                    "phone": phone,
                    "address": "Dhaka, Bangladesh",
                    "status": "Active",
                    "created_by": user,
                },
            )
            suppliers[name] = obj

        # ── Products (25 - expanded NGO demo inventory) ──
        products = {}
        prod_data = [
            (
                "PRD-0001",
                "Dell Laptop Latitude 5520",
                cats["CAT-009"],
                cats["CAT-001"],
                uoms["pcs"],
                "Dell Bangladesh",
                85000,
                90000,
                25,
                5,
                50,
                "lot",
                2.1,
                True,
                False,
            ),
            (
                "PRD-0002",
                "HP Monitor 24-inch",
                cats["CAT-010"],
                cats["CAT-001"],
                uoms["pcs"],
                "Dell Bangladesh",
                25000,
                28000,
                40,
                8,
                80,
                "serial",
                4.5,
                True,
                False,
            ),
            (
                "PRD-0003",
                "Cisco Router 2901",
                cats["CAT-011"],
                cats["CAT-001"],
                uoms["pcs"],
                "TechComm Systems",
                45000,
                52000,
                12,
                2,
                30,
                "serial",
                3.2,
                True,
                False,
            ),
            (
                "PRD-0004",
                "A4 Paper 80gsm (Ream)",
                cats["CAT-012"],
                cats["CAT-002"],
                uoms["pack"],
                "Office World",
                450,
                550,
                200,
                0,
                500,
                "none",
                2.5,
                True,
                False,
            ),
            (
                "PRD-0005",
                "Toner Cartridge HP 26A",
                cats["CAT-013"],
                cats["CAT-002"],
                uoms["pcs"],
                "Office World",
                3500,
                4200,
                30,
                5,
                60,
                "lot",
                0.8,
                True,
                False,
            ),
            (
                "PRD-0006",
                "Office Desk Wooden 5x3ft",
                cats["CAT-014"],
                cats["CAT-003"],
                uoms["pcs"],
                "Office World",
                12000,
                15000,
                15,
                0,
                40,
                "none",
                35,
                True,
                False,
            ),
            (
                "PRD-0007",
                "Paracetamol 500mg (Strip)",
                cats["CAT-016"],
                cats["CAT-004"],
                uoms["tab"],
                "PharmaCo Ltd.",
                120,
                180,
                500,
                50,
                1000,
                "lot",
                0.05,
                True,
                True,
            ),
            (
                "PRD-0008",
                "First Aid Kit Standard",
                cats["CAT-017"],
                cats["CAT-004"],
                uoms["pcs"],
                "PharmaCo Ltd.",
                2500,
                3000,
                60,
                10,
                150,
                "lot",
                1.5,
                True,
                True,
            ),
            (
                "PRD-0009",
                "Rice 50kg Bag",
                cats["CAT-018"],
                cats["CAT-005"],
                uoms["kg"],
                "Local Rice Mill",
                2800,
                3200,
                300,
                100,
                500,
                "lot",
                50,
                True,
                True,
            ),
            (
                "PRD-0010",
                "Tarpaulin Sheet 4x6m",
                cats["CAT-019"],
                cats["CAT-005"],
                uoms["sht"],
                "Kit Assembly Unit",
                1800,
                2200,
                150,
                20,
                400,
                "none",
                3.5,
                True,
                False,
            ),
            (
                "PRD-0011",
                "Hygiene Kit Family",
                cats["CAT-020"],
                cats["CAT-005"],
                uoms["pcs"],
                "Kit Assembly Unit",
                850,
                1100,
                120,
                30,
                300,
                "lot",
                2.0,
                True,
                True,
            ),
            (
                "PRD-0012",
                "Walkie Talkie Motorola",
                cats["CAT-008"],
                cats["CAT-008"],
                uoms["pcs"],
                "TechComm Systems",
                15000,
                18000,
                20,
                4,
                50,
                "serial",
                0.35,
                True,
                False,
            ),
            (
                "PRD-0013",
                "Solar Panel 100W",
                cats["CAT-007"],
                cats["CAT-007"],
                uoms["pcs"],
                "TechComm Systems",
                18000,
                22000,
                10,
                2,
                30,
                "serial",
                12,
                True,
                False,
            ),
            (
                "PRD-0014",
                "Water Purification Tablets",
                cats["CAT-020"],
                cats["CAT-005"],
                uoms["tab"],
                "AquaSafe International",
                350,
                450,
                800,
                0,
                2000,
                "lot",
                0.01,
                True,
                True,
            ),
            (
                "PRD-0015",
                "Oil Filter Toyota",
                cats["CAT-006"],
                cats["CAT-006"],
                uoms["pcs"],
                "Dell Bangladesh",
                1200,
                1500,
                25,
                3,
                50,
                "none",
                0.5,
                True,
                False,
            ),
            (
                "PRD-0016",
                "Lenovo ThinkPad E14",
                cats["CAT-009"],
                cats["CAT-001"],
                uoms["pcs"],
                "Dell Bangladesh",
                78000,
                84500,
                18,
                4,
                40,
                "serial",
                1.8,
                True,
                False,
            ),
            (
                "PRD-0017",
                "Network Switch 24 Port",
                cats["CAT-011"],
                cats["CAT-001"],
                uoms["pcs"],
                "TechComm Systems",
                16500,
                19500,
                22,
                3,
                45,
                "serial",
                2.4,
                True,
                False,
            ),
            (
                "PRD-0018",
                "USB Flash Drive 64GB",
                cats["CAT-011"],
                cats["CAT-001"],
                uoms["pcs"],
                "TechComm Systems",
                650,
                850,
                150,
                20,
                300,
                "none",
                0.02,
                True,
                False,
            ),
            (
                "PRD-0019",
                "Ball Pen Blue (Box)",
                cats["CAT-012"],
                cats["CAT-002"],
                uoms["box"],
                "Office World",
                180,
                240,
                260,
                10,
                500,
                "none",
                0.45,
                True,
                False,
            ),
            (
                "PRD-0020",
                "Plastic Chair Stackable",
                cats["CAT-015"],
                cats["CAT-003"],
                uoms["pcs"],
                "Office World",
                1350,
                1700,
                90,
                5,
                180,
                "none",
                2.8,
                True,
                False,
            ),
            (
                "PRD-0021",
                "Examination Gloves Latex (Box)",
                cats["CAT-017"],
                cats["CAT-004"],
                uoms["box"],
                "PharmaCo Ltd.",
                420,
                520,
                180,
                15,
                360,
                "lot",
                0.6,
                True,
                True,
            ),
            (
                "PRD-0022",
                "ORS Sachet",
                cats["CAT-016"],
                cats["CAT-004"],
                uoms["pack"],
                "PharmaCo Ltd.",
                95,
                130,
                420,
                40,
                900,
                "lot",
                0.12,
                True,
                True,
            ),
            (
                "PRD-0023",
                "Blanket Relief Grade",
                cats["CAT-019"],
                cats["CAT-005"],
                uoms["pcs"],
                "Kit Assembly Unit",
                650,
                880,
                240,
                25,
                500,
                "lot",
                1.9,
                True,
                False,
            ),
            (
                "PRD-0024",
                "Rechargeable Lantern",
                cats["CAT-008"],
                cats["CAT-008"],
                uoms["pcs"],
                "AquaSafe International",
                1450,
                1850,
                85,
                6,
                160,
                "serial",
                0.9,
                True,
                False,
            ),
            (
                "PRD-0025",
                "Vehicle Tire 265/70R16",
                cats["CAT-006"],
                cats["CAT-006"],
                uoms["pcs"],
                "Dell Bangladesh",
                9800,
                11800,
                16,
                2,
                36,
                "none",
                14.2,
                True,
                False,
            ),
        ]
        for (
            code,
            name,
            subcat,
            maincat,
            uom,
            sup_name,
            cost,
            sale,
            on_hand,
            reserved,
            max_stock,
            tracking,
            weight,
            is_active,
            expiry,
        ) in prod_data:
            obj, _ = Product.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": maincat,
                    "subcategory": subcat,
                    "uom": uom,
                    "cost": Decimal(str(cost)),
                    "sale_price": Decimal(str(sale)),
                    "on_hand": Decimal(str(on_hand)),
                    "reserved": Decimal(str(reserved)),
                    "max_stock": Decimal(str(max_stock)),
                    "reorder_level": Decimal(str(max(on_hand * Decimal("0.2"), 5))),
                    "tracking": tracking,
                    "weight": Decimal(str(weight)),
                    "barcode": f"880{code.replace('PRD-', '')}00001",
                    "expiry_tracking": expiry,
                    "is_active": is_active,
                    "supplier": suppliers[sup_name],
                    "location": "Central Warehouse",
                    "product_type": "storable",
                    "status": "Active",
                    "created_by": user,
                },
            )
            products[code] = obj

        self.stdout.write(f"  Products: {Product.objects.count()}")

        # ── Warehouses (5) ──
        wh = {}
        wh_data = [
            (
                "WH-01",
                "Central Warehouse - Dhaka",
                "Mirpur-10, Dhaka",
                "Md. Rahman",
                "01811111111",
                "Central",
                15000,
            ),
            (
                "WH-02",
                "Regional Warehouse - Chittagong",
                "Agrabad, Chittagong",
                "Md. Karim",
                "01822222222",
                "Regional",
                8000,
            ),
            (
                "WH-03",
                "Field Store - Cox's Bazar",
                "Ukhia, Cox's Bazar",
                "Md. Alam",
                "01833333333",
                "Field",
                3000,
            ),
            (
                "WH-04",
                "Field Store - Sylhet",
                "Zakiganj, Sylhet",
                "Md. Hasan",
                "01844444444",
                "Field",
                2500,
            ),
            (
                "WH-05",
                "Transit Hub - Dhaka Airport",
                "Kurmitola, Dhaka",
                "Md. Fahim",
                "01855555555",
                "Transit",
                5000,
            ),
        ]
        for code, name, addr, mgr, phone, wtype, cap in wh_data:
            obj, _ = Warehouse.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "address": addr,
                    "manager": mgr,
                    "phone": phone,
                    "warehouse_type": wtype,
                    "capacity_sqft": cap,
                },
            )
            wh[code] = obj

        self.stdout.write(f"  Warehouses: {Warehouse.objects.count()}")

        # ── Storage Locations (10) ──
        loc = {}
        loc_data = [
            ("Zone A - Receiving", "WH-01", "internal", None, False, False),
            ("Zone B - IT Storage", "WH-01", "internal", None, False, False),
            ("Zone C - Medical Cold", "WH-01", "internal", None, False, False),
            ("Zone D - Relief Items", "WH-01", "internal", None, False, False),
            ("Zone E - Scrap Area", "WH-01", "scrap", None, True, False),
            ("Returns Bay", "WH-01", "internal", None, False, True),
            ("Rack A1 - Electronics", "WH-02", "internal", None, False, False),
            ("Rack B1 - Supplies", "WH-02", "internal", None, False, False),
            ("Field Tent Storage", "WH-03", "internal", None, False, False),
            ("Transit Staging", "WH-05", "transit", None, False, False),
        ]
        for name, wh_code, ltype, parent, is_scrap, is_return in loc_data:
            obj, _ = StorageLocation.objects.update_or_create(
                name=name,
                warehouse=wh[wh_code],
                defaults={
                    "location_type": ltype,
                    "is_scrap": is_scrap,
                    "is_return": is_return,
                },
            )
            loc[name] = obj

        self.stdout.write(f"  Locations: {StorageLocation.objects.count()}")

        # ── Operation Types (5) ──
        ops = {}
        op_data = [
            ("Receipts", "REC", "incoming", "WH-01"),
            ("Delivery Orders", "DEL", "outgoing", "WH-01"),
            ("Internal Transfers", "INT", "internal", "WH-01"),
            ("Returns", "RET", "returns", "WH-01"),
            ("Scrap", "SCR", "scrap", "WH-01"),
        ]
        for name, code, otype, wh_code in op_data:
            obj, _ = OperationType.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "operation_type": otype,
                    "warehouse": wh[wh_code],
                },
            )
            ops[code] = obj

        # ── Putaway Rules (4) ──
        PutawayRule.objects.update_or_create(
            product=products["PRD-0001"],
            warehouse=wh["WH-01"],
            defaults={"location": loc["Zone B - IT Storage"], "sequence": 10},
        )
        PutawayRule.objects.update_or_create(
            category=cats["CAT-004"],
            warehouse=wh["WH-01"],
            defaults={
                "location": loc["Zone C - Medical Cold"],
                "sequence": 20,
                "product": None,
            },
        )
        PutawayRule.objects.update_or_create(
            category=cats["CAT-005"],
            warehouse=wh["WH-01"],
            defaults={
                "location": loc["Zone D - Relief Items"],
                "sequence": 30,
                "product": None,
            },
        )
        PutawayRule.objects.update_or_create(
            category=cats["CAT-001"],
            warehouse=wh["WH-02"],
            defaults={
                "location": loc["Rack A1 - Electronics"],
                "sequence": 10,
                "product": None,
            },
        )

        # ── Removal Strategies ──
        RemovalStrategy.objects.update_or_create(
            name="FIFO - Medical", warehouse=wh["WH-01"], defaults={"strategy": "fifo"}
        )
        RemovalStrategy.objects.update_or_create(
            name="FEFO - Relief Food",
            warehouse=wh["WH-01"],
            defaults={"strategy": "fefo"},
        )
        RemovalStrategy.objects.update_or_create(
            name="FIFO - General", warehouse=wh["WH-02"], defaults={"strategy": "fifo"}
        )

        # ── Routes (5) ──
        route_data = [
            ("R-01", "Buy", [{"step": "Purchase Order → Receipt → Warehouse"}]),
            ("R-02", "Distribute", [{"step": "Warehouse → GIN → Field"}]),
            ("R-03", "Inter-Warehouse Transfer", [{"step": "WH-A → Transit → WH-B"}]),
            ("R-04", "Supplier Return", [{"step": "QC Fail → Return → Supplier"}]),
            ("R-05", "Scrap", [{"step": "QC Fail → Scrap Location → Disposal"}]),
        ]
        for code, name, steps in route_data:
            Route.objects.update_or_create(
                code=code, defaults={"name": name, "steps": steps}
            )

        # ── Shipping Methods (5) ──
        sm_data = [
            ("SM-01", "Road Transport - Truck", "LEDARS Fleet", 5, 3),
            ("SM-02", "River Transport", "BIWTC", 3, 5),
            ("SM-03", "Air Freight", "Biman Cargo", 25, 1),
            ("SM-04", "Courier - DHL", "DHL Express", 15, 2),
            ("SM-05", "Manual Carry", "Staff", 0, 1),
        ]
        for code, name, carrier, cost_kg, days in sm_data:
            ShippingMethod.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "carrier": carrier,
                    "cost_per_kg": Decimal(str(cost_kg)),
                    "estimated_days": days,
                },
            )

        # ── Packaging Types (7) ──
        pkg_data = [
            ("PKG-01", "Small Box", 1, 2),
            ("PKG-02", "Medium Box", 5, 8),
            ("PKG-03", "Large Carton", 10, 20),
            ("PKG-04", "Pallet", 50, 500),
            ("PKG-05", "Drum", 1, 100),
            ("PKG-06", "Sack", 1, 50),
            ("PKG-07", "Bundle", 10, 15),
        ]
        for code, name, qty, wt in pkg_data:
            PackagingType.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "quantity": qty,
                    "weight": Decimal(str(wt)),
                    "dimensions": "LxWxH",
                },
            )

        # ── Product Templates (5) ──
        tmpl_data = [
            ("IT Equipment Template", cats["CAT-001"], uoms["pcs"], "serial", 0, 0, 0),
            ("Medical Consumable", cats["CAT-004"], uoms["tab"], "lot", 100, 50, 500),
            ("Relief Food Item", cats["CAT-005"], uoms["kg"], "lot", 2500, 100, 1000),
            ("Office Supply", cats["CAT-002"], uoms["pack"], "none", 500, 20, 200),
            ("Field Equipment", cats["CAT-007"], uoms["pcs"], "serial", 15000, 5, 30),
        ]
        for name, cat, uom, tracking, cost, reorder, max_s in tmpl_data:
            ProductTemplate.objects.update_or_create(
                name=name,
                defaults={
                    "category": cat,
                    "uom": uom,
                    "tracking": tracking,
                    "default_cost": Decimal(str(cost)),
                    "default_reorder": Decimal(str(reorder)),
                    "default_max": Decimal(str(max_s)),
                },
            )

        # ── Product Variants (5) ──
        var_data = [
            (
                "PRD-0001",
                "Dell Latitude 5520 - 16GB/512GB",
                "VAR-0001",
                {"RAM": "16GB", "SSD": "512GB"},
                5000,
            ),
            (
                "PRD-0001",
                "Dell Latitude 5520 - 32GB/1TB",
                "VAR-0002",
                {"RAM": "32GB", "SSD": "1TB"},
                15000,
            ),
            ("PRD-0002", 'HP Monitor 24" IPS', "VAR-0003", {"Panel": "IPS"}, 3000),
            (
                "PRD-0009",
                "Rice 50kg - Miniket",
                "VAR-0004",
                {"Variety": "Miniket"},
                200,
            ),
            ("PRD-0009", "Rice 50kg - BRRI-28", "VAR-0005", {"Variety": "BRRI-28"}, 0),
        ]
        for prod_code, name, var_code, attrs, cost_adj in var_data:
            ProductVariant.objects.update_or_create(
                code=var_code,
                defaults={
                    "product": products[prod_code],
                    "name": name,
                    "attributes": attrs,
                    "cost_adjustment": Decimal(str(cost_adj)),
                },
            )

        self.stdout.write(f"  Variants: {ProductVariant.objects.count()}")

        # ── GRN (4 Goods Receipt Notes) ──
        GRNSequence.objects.get_or_create(year=2025, defaults={"last_number": 4})
        grns = {}
        grn_data = [
            (
                "GRN-2025-001",
                "2025-01-15",
                "Dell Bangladesh",
                "WH-01",
                "Approved",
                user,
            ),
            ("GRN-2025-002", "2025-02-10", "PharmaCo Ltd.", "WH-01", "Approved", user),
            (
                "GRN-2025-003",
                "2025-03-05",
                "Local Rice Mill",
                "WH-03",
                "Pending Quality Check",
                user,
            ),
            ("GRN-2025-004", "2025-04-01", "Office World", "WH-01", "Draft", user),
        ]
        for grn_num, date, supplier_name, wh_code, status, received_by in grn_data:
            obj, _ = GRN.objects.update_or_create(
                grn_number=grn_num,
                defaults={
                    "receive_date": date,
                    "supplier": suppliers[supplier_name],
                    "warehouse": wh[wh_code],
                    "status": status,
                    "received_by": received_by,
                    "total_value": 0,
                },
            )
            grns[grn_num] = obj

        # GRN Line Items
        grn_lines = [
            ("GRN-2025-001", "PRD-0001", 10, 10, "pcs", 85000),
            ("GRN-2025-001", "PRD-0002", 20, 20, "pcs", 25000),
            ("GRN-2025-002", "PRD-0007", 200, 200, "tab", 120),
            ("GRN-2025-002", "PRD-0008", 30, 28, "pcs", 2500),
            ("GRN-2025-003", "PRD-0009", 100, 0, "kg", 2800),
            ("GRN-2025-004", "PRD-0004", 50, 0, "pack", 450),
            ("GRN-2025-004", "PRD-0005", 20, 0, "pcs", 3500),
        ]
        for grn_num, prod_code, qty, recv_qty, unit, price in grn_lines:
            GRNLineItem.objects.update_or_create(
                grn=grns[grn_num],
                item_code=products[prod_code].code,
                defaults={
                    "product": products[prod_code],
                    "item_name": products[prod_code].name,
                    "ordered_qty": qty,
                    "received_qty": recv_qty,
                    "accepted_qty": recv_qty,
                    "rejected_qty": 0,
                    "unit": unit,
                    "unit_price": Decimal(str(price)),
                },
            )
        # Update GRN totals
        for g in grns.values():
            total = sum(
                Decimal(str(l.ordered_qty)) * l.unit_price for l in g.line_items.all()
            )
            g.total_value = total
            g.save()

        self.stdout.write(
            f"  GRNs: {GRN.objects.count()} ({GRNLineItem.objects.count()} lines)"
        )

        # ── GIN (3 Goods Issue Notes) ──
        GINSequence.objects.get_or_create(year=2025, defaults={"last_number": 3})
        gins = {}
        gin_data = [
            (
                "GIN-2025-001",
                "2025-01-20",
                "Cox's Bazar Field Office",
                "Relief",
                "Cyclone Response",
                "WH-01",
                "Issued",
                user,
                user,
            ),
            (
                "GIN-2025-002",
                "2025-02-15",
                "Sylhet Regional Office",
                "WASH",
                "WASH Program",
                "WH-01",
                "Approved",
                user,
                user,
            ),
            (
                "GIN-2025-003",
                "2025-03-10",
                "Dhaka Head Office",
                "Admin",
                "Office Setup",
                "WH-01",
                "Draft",
                user,
                None,
            ),
        ]
        for (
            gin_num,
            date,
            issued_to,
            dept,
            proj,
            wh_code,
            status,
            req_by,
            app_by,
        ) in gin_data:
            obj, _ = GIN.objects.update_or_create(
                gin_number=gin_num,
                defaults={
                    "issue_date": date,
                    "issued_to": issued_to,
                    "department": dept,
                    "project": proj,
                    "warehouse": wh[wh_code],
                    "status": status,
                    "requested_by": req_by,
                    "approved_by": app_by,
                },
            )
            gins[gin_num] = obj

        gin_lines = [
            ("GIN-2025-001", "PRD-0010", 50, 50, "sht", 1800),
            ("GIN-2025-001", "PRD-0011", 30, 30, "pcs", 850),
            ("GIN-2025-001", "PRD-0009", 100, 80, "kg", 2800),
            ("GIN-2025-002", "PRD-0014", 200, 200, "tab", 350),
            ("GIN-2025-002", "PRD-0008", 10, 10, "pcs", 2500),
            ("GIN-2025-003", "PRD-0006", 5, 0, "pcs", 12000),
            ("GIN-2025-003", "PRD-0004", 20, 0, "pack", 450),
        ]
        for gin_num, prod_code, req_qty, iss_qty, unit, price in gin_lines:
            GINLineItem.objects.update_or_create(
                gin=gins[gin_num],
                item_code=products[prod_code].code,
                defaults={
                    "product": products[prod_code],
                    "item_name": products[prod_code].name,
                    "requested_qty": req_qty,
                    "issued_qty": iss_qty,
                    "unit": unit,
                    "unit_price": Decimal(str(price)),
                },
            )
        for g in gins.values():
            g.total_value = sum(
                Decimal(str(l.issued_qty)) * l.unit_price for l in g.line_items.all()
            )
            g.save()

        self.stdout.write(
            f"  GINs: {GIN.objects.count()} ({GINLineItem.objects.count()} lines)"
        )

        # ── Stock Transfers (3) ──
        StockTransferSequence.objects.get_or_create(
            year=2025, defaults={"last_number": 3}
        )
        transfers = {}
        st_data = [
            (
                "ST-2025-001",
                "2025-01-25",
                "WH-01",
                "WH-03",
                "Received",
                user,
                user,
                "DH-1234",
                "Md. Driver",
            ),
            (
                "ST-2025-002",
                "2025-02-20",
                "WH-01",
                "WH-04",
                "In Transit",
                user,
                None,
                "DH-5678",
                "Md. Roni",
            ),
            (
                "ST-2025-003",
                "2025-03-15",
                "WH-02",
                "WH-03",
                "Draft",
                user,
                None,
                None,
                None,
            ),
        ]
        for t_num, date, from_wh, to_wh, status, sent, recv, veh, drv in st_data:
            obj, _ = StockTransfer.objects.update_or_create(
                transfer_number=t_num,
                defaults={
                    "transfer_date": date,
                    "from_warehouse": wh[from_wh],
                    "to_warehouse": wh[to_wh],
                    "status": status,
                    "sent_by": sent,
                    "received_by": recv,
                    "vehicle_number": veh,
                    "driver_name": drv,
                },
            )
            transfers[t_num] = obj

        st_lines = [
            ("ST-2025-001", "PRD-0010", 30, "sht", 1800),
            ("ST-2025-001", "PRD-0011", 20, "pcs", 850),
            ("ST-2025-002", "PRD-0014", 100, "tab", 350),
            ("ST-2025-002", "PRD-0007", 50, "tab", 120),
            ("ST-2025-003", "PRD-0009", 50, "kg", 2800),
        ]
        for t_num, prod_code, qty, unit, price in st_lines:
            StockTransferLine.objects.update_or_create(
                transfer=transfers[t_num],
                item_code=products[prod_code].code,
                defaults={
                    "product": products[prod_code],
                    "item_name": products[prod_code].name,
                    "quantity": qty,
                    "unit": unit,
                    "unit_price": Decimal(str(price)),
                },
            )
        for t in transfers.values():
            t.total_value = sum(
                Decimal(str(l.quantity)) * l.unit_price for l in t.lines.all()
            )
            t.save()

        self.stdout.write(f"  Transfers: {StockTransfer.objects.count()}")

        # ── Stock Adjustments (2) ──
        StockAdjustmentSequence.objects.get_or_create(
            year=2025, defaults={"last_number": 2}
        )
        adjs = {}
        adj_data = [
            ("ADJ-2025-001", "2025-02-28", "Recount", "WH-01", "Posted", user, user),
            ("ADJ-2025-002", "2025-03-20", "Decrease", "WH-03", "Draft", user, None),
        ]
        for a_num, date, atype, wh_code, status, adj_by, app_by in adj_data:
            obj, _ = StockAdjustment.objects.update_or_create(
                adjustment_number=a_num,
                defaults={
                    "adjustment_date": date,
                    "adjustment_type": atype,
                    "warehouse": wh[wh_code],
                    "status": status,
                    "adjusted_by": adj_by,
                    "approved_by": app_by,
                },
            )
            adjs[a_num] = obj

        adj_lines = [
            (
                "ADJ-2025-001",
                "PRD-0004",
                200,
                195,
                "pack",
                450,
                "5 reams damaged in storage",
            ),
            ("ADJ-2025-001", "PRD-0005", 30, 28, "pcs", 3500, "2 cartridges expired"),
            ("ADJ-2025-002", "PRD-0009", 300, 285, "kg", 2800, "Moisture damage"),
        ]
        for a_num, prod_code, sys_qty, cnt_qty, unit, price, reason in adj_lines:
            StockAdjustmentLine.objects.update_or_create(
                adjustment=adjs[a_num],
                item_code=products[prod_code].code,
                defaults={
                    "product": products[prod_code],
                    "item_name": products[prod_code].name,
                    "system_qty": sys_qty,
                    "counted_qty": cnt_qty,
                    "difference": cnt_qty - sys_qty,
                    "unit": unit,
                    "unit_price": Decimal(str(price)),
                    "reason": reason,
                },
            )

        self.stdout.write(f"  Adjustments: {StockAdjustment.objects.count()}")

        # ── Lot/Serial Numbers (8) ──
        lot_data = [
            ("PRD-0001", "LOT-DELL-2025-001", "lot", 10, "2025-01-15", None),
            ("PRD-0002", "SN-HP-MON-001", "serial", 1, "2024-12-01", None),
            ("PRD-0002", "SN-HP-MON-002", "serial", 1, "2024-12-01", None),
            ("PRD-0007", "LOT-PARA-2025-A", "lot", 200, "2025-02-10", "2026-02-10"),
            ("PRD-0007", "LOT-PARA-2025-B", "lot", 300, "2025-03-01", "2026-03-01"),
            ("PRD-0009", "LOT-RICE-2025-001", "lot", 100, "2025-01-05", "2025-07-05"),
            ("PRD-0011", "LOT-HYG-2025-001", "lot", 60, "2025-01-20", "2026-01-20"),
            ("PRD-0014", "LOT-WPT-2025-A", "lot", 400, "2025-02-15", "2026-08-15"),
        ]
        for prod_code, number, ltype, qty, mfg, exp in lot_data:
            LotSerial.objects.update_or_create(
                product=products[prod_code],
                number=number,
                defaults={
                    "lot_type": ltype,
                    "quantity": Decimal(str(qty)),
                    "manufacture_date": mfg,
                    "expiry_date": exp,
                    "warehouse": wh["WH-01"],
                },
            )

        self.stdout.write(f"  Lot/Serial: {LotSerial.objects.count()}")

        # ── Quality Teams (4) ──
        teams = {}
        team_data = [
            ("QT-General", "General Quality Team", cats.get("CAT-001")),
            ("QT-Medical", "Medical QC Team", cats.get("CAT-004")),
            ("QT-Relief", "Relief Items QC", cats.get("CAT-005")),
            ("QT-IT", "IT Equipment QC", cats.get("CAT-001")),
        ]
        for name, desc, cat in team_data:
            obj, _ = QualityTeam.objects.update_or_create(
                name=name,
                defaults={"description": desc, "leader": user, "category": cat},
            )
            teams[name] = obj

        # ── Quality Checks (4) ──
        qc_data = [
            (
                "QC-2025-001",
                "2025-01-16",
                "Receipt",
                "PRD-0001",
                "Pass",
                "QT-IT",
                "Md. Rahman",
            ),
            (
                "QC-2025-002",
                "2025-02-11",
                "Receipt",
                "PRD-0007",
                "Pass",
                "QT-Medical",
                "Dr. Karim",
            ),
            (
                "QC-2025-003",
                "2025-03-06",
                "Return",
                "PRD-0008",
                "Conditional Pass",
                "QT-Medical",
                "Dr. Karim",
            ),
            (
                "QC-2025-004",
                "2025-04-02",
                "Periodic",
                "PRD-0004",
                "Pending",
                "QT-General",
                "Md. Hasan",
            ),
        ]
        for ref, date, ctype, prod_code, status, team_name, inspector in qc_data:
            QualityCheck.objects.update_or_create(
                reference=ref,
                defaults={
                    "date": date,
                    "check_type": ctype,
                    "product": products[prod_code],
                    "status": status,
                    "team": teams[team_name],
                    "inspector": inspector,
                    "warehouse": wh["WH-01"],
                    "notes": f"Quality check for {products[prod_code].name}",
                },
            )

        # ── Quality Alerts (2) ──
        QualityAlert.objects.update_or_create(
            reference="QA-2025-001",
            defaults={
                "title": "Damaged First Aid Kits",
                "product": products["PRD-0008"],
                "severity": "High",
                "status": "In Progress",
                "reported_by": user,
                "description": "3 first aid kits found with broken seals upon receipt",
                "corrective_action": "Supplier notified, replacement requested",
            },
        )
        QualityAlert.objects.update_or_create(
            reference="QA-2025-002",
            defaults={
                "title": "Expiring Water Purification Tablets",
                "product": products["PRD-0014"],
                "severity": "Medium",
                "status": "New",
                "reported_by": user,
                "description": "Batch LOT-WPT-2025-A approaching expiry",
            },
        )

        # ── Quality Control Points (5) ──
        qcp_data = [
            ("Visual Inspection", "Appearance", "No visible damage", "N/A", True),
            ("Weight Check", "Weight", "Within ±5% of stated weight", "5%", True),
            ("Seal Integrity", "Packaging seal", "Intact, no tampering", "N/A", True),
            ("Expiry Date Check", "Expiry date", ">6 months remaining", "N/A", True),
            (
                "Functional Test",
                "Functionality",
                "Powers on, all features work",
                "N/A",
                False,
            ),
        ]
        for name, param, std, tol, mandatory in qcp_data:
            QualityControlPoint.objects.update_or_create(
                name=name,
                defaults={
                    "parameter": param,
                    "standard": std,
                    "tolerance": tol,
                    "is_mandatory": mandatory,
                    "category": cats["CAT-001"],
                    "operation_type": ops["REC"],
                },
            )

        # ── QC Templates (4) ──
        QCTemplate.objects.update_or_create(
            name="Electronic Equipment QC",
            defaults={
                "category": cats["CAT-001"],
                "checklist": [
                    {"item": "Visual inspection", "mandatory": True},
                    {"item": "Power on test", "mandatory": True},
                    {"item": "Serial number verification", "mandatory": True},
                    {"item": "Accessories check", "mandatory": False},
                ],
            },
        )
        QCTemplate.objects.update_or_create(
            name="Medical Supply QC",
            defaults={
                "category": cats["CAT-004"],
                "checklist": [
                    {"item": "Expiry date check", "mandatory": True},
                    {"item": "Temperature log review", "mandatory": True},
                    {"item": "Seal integrity", "mandatory": True},
                    {"item": "Batch number verification", "mandatory": True},
                ],
            },
        )
        QCTemplate.objects.update_or_create(
            name="Food Item QC",
            defaults={
                "category": cats["CAT-005"],
                "checklist": [
                    {"item": "Weight verification", "mandatory": True},
                    {"item": "Packaging integrity", "mandatory": True},
                    {"item": "Moisture check", "mandatory": True},
                    {"item": "Pest inspection", "mandatory": True},
                ],
            },
        )
        QCTemplate.objects.update_or_create(
            name="General Item QC",
            defaults={
                "category": cats["CAT-002"],
                "checklist": [
                    {"item": "Quantity verification", "mandatory": True},
                    {"item": "Visual inspection", "mandatory": True},
                    {"item": "Documentation check", "mandatory": False},
                ],
            },
        )

        self.stdout.write(
            f"  Quality: {QualityCheck.objects.count()} checks, {QualityAlert.objects.count()} alerts"
        )

        # ── Inventory Valuation (7) ──
        val_products = [
            "PRD-0001",
            "PRD-0004",
            "PRD-0007",
            "PRD-0009",
            "PRD-0010",
            "PRD-0011",
            "PRD-0014",
        ]
        for prod_code in val_products:
            p = products[prod_code]
            InventoryValuation.objects.update_or_create(
                product=p,
                warehouse=wh["WH-01"],
                defaults={
                    "on_hand": p.on_hand,
                    "unit_cost": p.cost,
                    "total_value": p.on_hand * p.cost,
                    "method": "fifo" if p.expiry_tracking else "average",
                },
            )

        # ── Landed Costs (3) ──
        LandedCost.objects.update_or_create(
            reference="LC-2025-001",
            defaults={
                "grn": grns["GRN-2025-001"],
                "date": "2025-01-16",
                "freight_cost": 15000,
                "customs_duty": 5000,
                "insurance_cost": 2000,
                "handling_cost": 3000,
                "other_cost": 1000,
                "total_landed_cost": 26000,
                "split_method": "by_value",
                "status": "posted",
            },
        )
        LandedCost.objects.update_or_create(
            reference="LC-2025-002",
            defaults={
                "grn": grns["GRN-2025-002"],
                "date": "2025-02-11",
                "freight_cost": 5000,
                "customs_duty": 0,
                "insurance_cost": 1000,
                "handling_cost": 1500,
                "other_cost": 500,
                "total_landed_cost": 8000,
                "split_method": "by_quantity",
                "status": "posted",
            },
        )
        LandedCost.objects.update_or_create(
            reference="LC-2025-003",
            defaults={
                "grn": grns["GRN-2025-003"],
                "date": "2025-03-06",
                "freight_cost": 8000,
                "customs_duty": 0,
                "insurance_cost": 500,
                "handling_cost": 2000,
                "other_cost": 0,
                "total_landed_cost": 10500,
                "split_method": "equal",
                "status": "draft",
            },
        )

        # ── Stock Moves (8) ──
        moves = [
            (
                "2025-01-15",
                "GRN-2025-001",
                "PRD-0001",
                "Supplier",
                "Zone B - IT Storage",
                10,
                "Receipt",
            ),
            (
                "2025-01-15",
                "GRN-2025-001",
                "PRD-0002",
                "Supplier",
                "Zone B - IT Storage",
                20,
                "Receipt",
            ),
            (
                "2025-01-20",
                "GIN-2025-001",
                "PRD-0010",
                "Zone D - Relief Items",
                "Cox's Bazar",
                50,
                "Delivery",
            ),
            ("2025-01-25", "ST-2025-001", "PRD-0011", "WH-01", "WH-03", 20, "Transfer"),
            (
                "2025-02-10",
                "GRN-2025-002",
                "PRD-0007",
                "Supplier",
                "Zone C - Medical Cold",
                200,
                "Receipt",
            ),
            (
                "2025-02-15",
                "GIN-2025-002",
                "PRD-0014",
                "WH-01",
                "Sylhet",
                200,
                "Delivery",
            ),
            (
                "2025-02-28",
                "ADJ-2025-001",
                "PRD-0004",
                "Zone A - Receiving",
                "Adjustment",
                5,
                "Adjustment",
            ),
            (
                "2025-03-10",
                "RET-2025-001",
                "PRD-0008",
                "Cox's Bazar",
                "Returns Bay",
                3,
                "Return",
            ),
        ]
        for date, ref, prod_code, src, dest, qty, mtype in moves:
            StockMove.objects.update_or_create(
                reference=ref,
                product=products[prod_code],
                defaults={
                    "date": f"{date}T10:00:00Z",
                    "source_location": src,
                    "destination_location": dest,
                    "quantity": Decimal(str(qty)),
                    "uom": (
                        products[prod_code].uom.name
                        if products[prod_code].uom
                        else "pcs"
                    ),
                    "move_type": mtype,
                    "done_by": user,
                },
            )

        self.stdout.write(f"  Stock Moves: {StockMove.objects.count()}")

        # ── Scrap Records (2) ──
        ScrapRecord.objects.update_or_create(
            reference="SCR-2025-001",
            defaults={
                "date": "2025-02-28",
                "product": products["PRD-0004"],
                "warehouse": wh["WH-01"],
                "quantity": 5,
                "reason": "Water damage from roof leak",
                "disposal_method": "Recycling",
                "disposal_date": "2025-03-05",
                "certificate_number": "RC-2025-001",
                "status": "completed",
                "scrapped_by": user,
            },
        )
        ScrapRecord.objects.update_or_create(
            reference="SCR-2025-002",
            defaults={
                "date": "2025-03-15",
                "product": products["PRD-0007"],
                "warehouse": wh["WH-01"],
                "quantity": 20,
                "reason": "Expired batch - past use-by date",
                "disposal_method": "Incineration",
                "status": "pending",
                "scrapped_by": user,
            },
        )

        # ── Return Records (2) ──
        ReturnRecord.objects.update_or_create(
            reference="RET-2025-001",
            defaults={
                "date": "2025-03-10",
                "return_type": "supplier",
                "product": products["PRD-0008"],
                "warehouse": wh["WH-01"],
                "quantity": 3,
                "reason": "Broken seals detected during QC",
                "condition": "damaged",
                "original_reference": "GRN-2025-002",
                "status": "completed",
                "created_by": user,
            },
        )
        ReturnRecord.objects.update_or_create(
            reference="RET-2025-002",
            defaults={
                "date": "2025-03-20",
                "return_type": "customer",
                "product": products["PRD-0012"],
                "warehouse": wh["WH-03"],
                "quantity": 2,
                "reason": "Defective units from field office",
                "condition": "defective",
                "original_reference": "GIN-2025-001",
                "status": "draft",
                "created_by": user,
            },
        )

        self.stdout.write(
            f"  Scrap: {ScrapRecord.objects.count()}, Returns: {ReturnRecord.objects.count()}"
        )

        # ── Reorder Rules (5) ──
        reorder_data = [
            ("PRD-0001", "WH-01", 5, 30, 10, 14, "automatic"),
            ("PRD-0007", "WH-01", 100, 800, 200, 7, "automatic"),
            ("PRD-0009", "WH-03", 50, 400, 100, 5, "manual"),
            ("PRD-0010", "WH-01", 30, 300, 50, 10, "automatic"),
            ("PRD-0014", "WH-01", 200, 1500, 500, 14, "automatic"),
        ]
        for prod_code, wh_code, min_q, max_q, reord_q, lead, trigger in reorder_data:
            ReorderRule.objects.update_or_create(
                product=products[prod_code],
                warehouse=wh[wh_code],
                defaults={
                    "min_qty": Decimal(str(min_q)),
                    "max_qty": Decimal(str(max_q)),
                    "reorder_qty": Decimal(str(reord_q)),
                    "lead_time_days": lead,
                    "trigger": trigger,
                },
            )

        self.stdout.write(f"  Reorder Rules: {ReorderRule.objects.count()}")

        # ── Kitting / BOM (3) ──
        bom_data = [
            (
                "Emergency Relief Kit",
                "KIT-001",
                "PRD-0011",
                30,
                [("PRD-0014", 10, 350), ("PRD-0007", 20, 120), ("PRD-0010", 1, 1800)],
            ),
            (
                "Office Starter Pack",
                "KIT-002",
                "PRD-0004",
                15,
                [("PRD-0004", 5, 450), ("PRD-0005", 1, 3500)],
            ),
            (
                "Field First Aid Kit",
                "KIT-003",
                "PRD-0008",
                45,
                [("PRD-0007", 50, 120), ("PRD-0014", 20, 350)],
            ),
        ]
        for name, code, prod_code, asm_time, components in bom_data:
            bom, _ = KittingBOM.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "product": products[prod_code],
                    "assembly_time_minutes": asm_time,
                },
            )
            total_cost = Decimal("0")
            for comp_code, qty, cost in components:
                KittingBOMLine.objects.update_or_create(
                    bom=bom,
                    component=products[comp_code],
                    defaults={
                        "quantity": Decimal(str(qty)),
                        "unit_cost": Decimal(str(cost)),
                    },
                )
                total_cost += Decimal(str(qty)) * Decimal(str(cost))
            bom.total_cost = total_cost
            bom.save()

        self.stdout.write(f"  Kitting BOMs: {KittingBOM.objects.count()}")

        # ── Donor Funded Inventory (3) ──
        DonorFundedInventory.objects.update_or_create(
            grant_reference="USAID-ER-2025-001",
            defaults={
                "project_name": "Emergency Response - Cyclone Mocha",
                "donor": "USAID",
                "product": products["PRD-0010"],
                "allocated_qty": 500,
                "consumed_qty": 200,
                "remaining_qty": 300,
                "warehouse": wh["WH-03"],
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
            },
        )
        DonorFundedInventory.objects.update_or_create(
            grant_reference="UNICEF-WASH-2025-001",
            defaults={
                "project_name": "WASH Program - Sylhet Division",
                "donor": "UNICEF",
                "product": products["PRD-0014"],
                "allocated_qty": 2000,
                "consumed_qty": 800,
                "remaining_qty": 1200,
                "warehouse": wh["WH-04"],
                "start_date": "2025-01-01",
                "end_date": "2025-06-30",
            },
        )
        DonorFundedInventory.objects.update_or_create(
            grant_reference="DFID-SH-2025-001",
            defaults={
                "project_name": "Shelter Assistance - Rohingya Camps",
                "donor": "DFID",
                "product": products["PRD-0010"],
                "allocated_qty": 300,
                "consumed_qty": 150,
                "remaining_qty": 150,
                "warehouse": wh["WH-03"],
                "start_date": "2024-07-01",
                "end_date": "2025-06-30",
            },
        )

        # ── Field Distributions (3) ──
        FieldDistribution.objects.update_or_create(
            reference="FD-2025-001",
            defaults={
                "date": "2025-01-22",
                "location": "Ukhia Camp-4, Cox's Bazar",
                "gps_coordinates": "21.2258,92.1547",
                "product": products["PRD-0011"],
                "quantity": 120,
                "beneficiary_count": 120,
                "verification_method": "Biometric + ID Card",
                "status": "completed",
                "distributed_by": user,
                "notes": "Monthly hygiene kit distribution for Rohingya families",
            },
        )
        FieldDistribution.objects.update_or_create(
            reference="FD-2025-002",
            defaults={
                "date": "2025-02-18",
                "location": "Zakiganj Union, Sylhet",
                "gps_coordinates": "24.8549,92.2841",
                "product": products["PRD-0014"],
                "quantity": 500,
                "beneficiary_count": 250,
                "verification_method": "Community Register + Photo",
                "status": "completed",
                "distributed_by": user,
                "notes": "WASH program - water purification tablet distribution",
            },
        )
        FieldDistribution.objects.update_or_create(
            reference="FD-2025-003",
            defaults={
                "date": "2025-03-25",
                "location": "Teknaf, Cox's Bazar",
                "gps_coordinates": "20.8624,92.2977",
                "product": products["PRD-0010"],
                "quantity": 80,
                "beneficiary_count": 80,
                "verification_method": "Beneficiary List + Signature",
                "status": "in_progress",
                "distributed_by": user,
                "notes": "Emergency shelter materials for cyclone-affected families",
            },
        )

        self.stdout.write(
            f"  NGO: {DonorFundedInventory.objects.count()} donor-funded, {FieldDistribution.objects.count()} distributions"
        )

        # ── Inventory Settings ──
        InventorySettings.objects.update_or_create(
            id=1,
            defaults={
                "company_name": "LEDARS",
                "default_warehouse": wh["WH-01"],
                "default_valuation_method": "average",
                "enable_lot_tracking": True,
                "enable_expiry_tracking": True,
                "enable_quality_control": True,
                "enable_barcode": True,
                "low_stock_threshold": 10,
                "auto_reorder": False,
                "fiscal_year_start": 7,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Inventory seed complete!\n"
                f"  • Categories: {Category.objects.count()}\n"
                f"  • Products: {Product.objects.count()}\n"
                f"  • Warehouses: {Warehouse.objects.count()}\n"
                f"  • Storage Locations: {StorageLocation.objects.count()}\n"
                f"  • GRNs: {GRN.objects.count()} ({GRNLineItem.objects.count()} lines)\n"
                f"  • GINs: {GIN.objects.count()} ({GINLineItem.objects.count()} lines)\n"
                f"  • Transfers: {StockTransfer.objects.count()}\n"
                f"  • Adjustments: {StockAdjustment.objects.count()}\n"
                f"  • Quality: {QualityCheck.objects.count()} checks, {QualityAlert.objects.count()} alerts\n"
                f"  • Lot/Serial: {LotSerial.objects.count()}\n"
                f"  • Reorder Rules: {ReorderRule.objects.count()}\n"
                f"  • BOMs: {KittingBOM.objects.count()}\n"
                f"  • Donor-funded: {DonorFundedInventory.objects.count()}\n"
                f"  • Field Distributions: {FieldDistribution.objects.count()}\n"
            )
        )
