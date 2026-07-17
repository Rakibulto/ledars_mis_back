import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from authentication.models import User
from employee.models import Department, Designation, Employee
from inventory.models import Category, Item
from projects.models import Project
from vendorportal.models.models import VendorProfile
from procurement.models import (
    # Core
    PurchaseOrder,
    ItemPO,
    PurchaseRequisition,
    ItemPR,
    ApprovalRequest,
    ApprovalHistory,
    # Requisition
    OfficeManagement,
    MaterialRequisition,
    MaterialItem,
    # RFQ
    RFQ,
    # Quotation
    VendorQuotation,
    QuotationItem,
    QuotationOpening,
    # Comparative
    ComparativeStatement,
    ComparativeLineItem,
    # Award
    Award,
    AwardNotification,
    # Work Order
    WorkOrder,
    WorkOrderItem,
    VendorAcceptance,
    # GRN
    GoodsReceiptNote,
    GRNItem,
    GRNVerification,
    # Payment Requisition
    PaymentRequisition,
    PaymentRequisitionItem,
    # Treasury
    TreasuryProcessing,
    PaymentRecord,
    PaymentTimeline,
    # Budget & Account
    Budget,
    Account,
    # Vendor Management
    VendorCategory,
    VendorCategoryMapping,
    VendorEvaluation,
    VendorOnboarding,
    VendorVerification,
    VendorPerformance,
    # Notification
    ProcurementNotification,
    # Settings
    ApprovalMatrix,
    EmailTemplate,
    ProcurementRole,
    ProcurementUserRole,
    NotificationSetting,
)


class Command(BaseCommand):
    help = "Seed procurement module with realistic test data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing procurement data before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing procurement data...")
            self._clear_data()

        self.stdout.write("Seeding procurement data...")

        user = self._get_or_create_user()
        dept, desig = self._get_or_create_department()
        employees = self._get_or_create_employees(user, dept, desig)
        categories, items = self._get_or_create_inventory()
        project = self._get_or_create_project(user)

        locations = self._create_office_locations(user)
        budgets = self._create_budgets(user)
        accounts = self._create_accounts(user)
        suppliers = self._create_suppliers(user, categories)
        requisitions = self._create_material_requisitions(
            user, employees, dept, categories, items, budgets, accounts, locations
        )
        rfq_categories = self._create_rfq_categories(user)
        rfqs = self._create_rfqs(user, requisitions, rfq_categories, items)
        quotations = self._create_vendor_quotations(user, rfqs, suppliers, items)
        self._create_quotation_openings(user, employees, rfqs)
        comparatives = self._create_comparative_statements(
            user, rfqs, quotations, suppliers, items
        )
        awards = self._create_awards(user, comparatives, rfqs, suppliers)
        self._create_award_notifications(user, awards, suppliers)
        work_orders = self._create_work_orders(
            user, employees, awards, suppliers, items
        )
        self._create_vendor_acceptances(work_orders)
        grns = self._create_grns(user, employees, work_orders, suppliers, items)
        self._create_grn_verifications(employees, grns)
        payment_reqs = self._create_payment_requisitions(
            user,
            employees,
            work_orders,
            grns,
            suppliers,
            budgets,
            accounts,
            project,
            dept,
            items,
        )
        self._create_treasury_processing(user, employees, payment_reqs, suppliers)
        self._create_purchase_requisitions(employees, dept, project, items)
        purchase_orders = self._create_purchase_orders(employees, suppliers, items)
        self._create_approval_requests(user)
        self._create_vendor_management(user, employees, suppliers)
        self._create_notifications(user)
        self._create_settings(user, employees, dept)

        self.stdout.write(
            self.style.SUCCESS("Successfully seeded all procurement data!")
        )

    def _clear_data(self):
        models_to_clear = [
            PaymentTimeline,
            PaymentRecord,
            TreasuryProcessing,
            PaymentRequisitionItem,
            PaymentRequisition,
            GRNVerification,
            GRNItem,
            GoodsReceiptNote,
            VendorAcceptance,
            WorkOrderItem,
            WorkOrder,
            AwardNotification,
            Award,
            ComparativeLineItem,
            ComparativeStatement,
            QuotationItem,
            QuotationOpening,
            VendorQuotation,
            RFQ,
            MaterialItem,
            MaterialRequisition,
            ItemPO,
            PurchaseOrder,
            ItemPR,
            PurchaseRequisition,
            ApprovalHistory,
            ApprovalRequest,
            VendorPerformance,
            VendorEvaluation,
            VendorOnboarding,
            VendorVerification,
            VendorCategoryMapping,
            VendorCategory,
            ProcurementNotification,
            ProcurementUserRole,
            ProcurementRole,
            NotificationSetting,
            EmailTemplate,
            ApprovalMatrix,
            Account,
            Budget,
            VendorProfile,
        ]
        for model in models_to_clear:
            model.objects.all().delete()
        self.stdout.write("Cleared all procurement data.")

    def _get_or_create_user(self):
        user = User.objects.filter(email="leaders@leaders.com").first()
        if not user:
            user = User.objects.create_superuser(
                username="leaders",
                email="leaders@leaders.com",
                password="Leaders1234",
            )
        return user

    def _get_or_create_department(self):
        dept_names = ["Procurement", "Finance", "Administration", "IT", "HR"]
        depts = []
        for name in dept_names:
            d, _ = Department.objects.get_or_create(name=name)
            depts.append(d)
        desig, _ = Designation.objects.get_or_create(
            name="Officer", department=depts[0]
        )
        return depts[0], desig

    def _get_or_create_employees(self, user, dept, desig):
        emp, _ = Employee.objects.get_or_create(
            user=user,
            defaults={
                "employee_name": "Admin User",
                "department": dept,
                "designation": desig,
            },
        )
        employees = [emp]
        names = [
            ("Procurement Officer", "procurement_officer@leaders.com"),
            ("Finance Manager", "finance_manager@leaders.com"),
            ("Store Keeper", "store_keeper@leaders.com"),
        ]
        for name, email in names:
            u, _ = User.objects.get_or_create(
                email=email,
                defaults={"username": email.split("@")[0], "password": "pass"},
            )
            e, _ = Employee.objects.get_or_create(
                user=u,
                defaults={
                    "employee_name": name,
                    "department": dept,
                    "designation": desig,
                },
            )
            employees.append(e)
        return employees

    def _get_or_create_inventory(self):
        main_cat, _ = Category.objects.get_or_create(
            name="Office Supplies",
            defaults={"code": "OS", "level": "Main", "status": "Active"},
        )
        sub_stationery, _ = Category.objects.get_or_create(
            name="Stationery",
            defaults={
                "code": "ST",
                "level": "Sub",
                "parent": main_cat,
                "status": "Active",
            },
        )
        sub_furniture, _ = Category.objects.get_or_create(
            name="Furniture & Fixtures",
            defaults={
                "code": "FF",
                "level": "Sub",
                "parent": main_cat,
                "status": "Active",
            },
        )
        it_cat, _ = Category.objects.get_or_create(
            name="IT Equipment",
            defaults={"code": "IT", "level": "Main", "status": "Active"},
        )
        sub_it_hw, _ = Category.objects.get_or_create(
            name="IT Hardware",
            defaults={
                "code": "HW",
                "level": "Sub",
                "parent": it_cat,
                "status": "Active",
            },
        )
        sub_it_acc, _ = Category.objects.get_or_create(
            name="IT Accessories",
            defaults={
                "code": "IA",
                "level": "Sub",
                "parent": it_cat,
                "status": "Active",
            },
        )
        categories = [main_cat, it_cat]

        item_data = [
            ("ITM-001", "A4 Paper (Ream)", main_cat, sub_stationery, Decimal("350.00")),
            (
                "ITM-002",
                "Ballpoint Pen (Box)",
                main_cat,
                sub_stationery,
                Decimal("120.00"),
            ),
            ("ITM-003", "Printer Toner", it_cat, sub_it_acc, Decimal("4500.00")),
            ("ITM-004", "Laptop Computer", it_cat, sub_it_hw, Decimal("65000.00")),
            ("ITM-005", "Office Chair", main_cat, sub_furniture, Decimal("8500.00")),
            ("ITM-006", "Desk Lamp", main_cat, sub_furniture, Decimal("1200.00")),
            (
                "ITM-007",
                "Whiteboard Marker (Set)",
                main_cat,
                sub_stationery,
                Decimal("250.00"),
            ),
            ("ITM-008", "USB Flash Drive 32GB", it_cat, sub_it_acc, Decimal("450.00")),
            (
                "ITM-009",
                "Photocopy Paper (Box)",
                main_cat,
                sub_stationery,
                Decimal("1800.00"),
            ),
            ("ITM-010", "Desktop Monitor", it_cat, sub_it_hw, Decimal("18000.00")),
        ]
        items = []
        for code, name, cat, subcat, price in item_data:
            item, _ = Item.objects.get_or_create(
                item_code=code,
                defaults={
                    "item_name": name,
                    "category": cat,
                    "subcategory": subcat,
                    "unit_price": price,
                    "current_stock": random.randint(10, 200),
                    "reorder_level": 5,
                    "reorder_quantity": 10,
                    "minimum_stock": 5,
                    "maximum_stock": 500,
                    "unit": "Piece",
                    "status": "Active",
                },
            )
            items.append(item)
        return categories, items

    def _get_or_create_project(self, user):
        proj, _ = Project.objects.get_or_create(
            code="PROJ-001",
            defaults={
                "name": "Community Development Program",
                "budget": Decimal("5000000.00"),
                "start_date": date.today() - timedelta(days=90),
                "end_date": date.today() + timedelta(days=270),
                "status": "Active",
                "created_by": user,
            },
        )
        return proj

    # ── Office Locations ──────────────────────────────────────
    def _create_office_locations(self, user):
        locations_data = [
            ("Head Office", "123 Main Street, Dhaka"),
            ("Regional Office - Chittagong", "45 Station Road, Chittagong"),
            ("Field Office - Sylhet", "78 Tea Garden Road, Sylhet"),
        ]
        locations = []
        for name, addr in locations_data:
            loc, _ = OfficeManagement.objects.get_or_create(
                name=name,
                defaults={
                    "address": addr,
                    "district": "Dhaka" if "Dhaka" in name else "Chattogram" if "Chittagong" in name else "Sylhet",
                    "created_by": user,
                },
            )
            locations.append(loc)
        return locations

    # ── Budgets ───────────────────────────────────────────────
    def _create_budgets(self, user):
        budget_data = [
            ("Operational Budget 2025", Decimal("2000000.00")),
            ("Capital Budget 2025", Decimal("5000000.00")),
            ("Project Budget - CDP", Decimal("3000000.00")),
        ]
        budgets = []
        for name, amount in budget_data:
            b, _ = Budget.objects.get_or_create(
                name=name,
                defaults={"allocated_amount": amount, "created_by": user},
            )
            budgets.append(b)
        return budgets

    # ── Accounts ──────────────────────────────────────────────
    def _create_accounts(self, user):
        account_data = [
            "General Operations Account",
            "Project Fund Account",
            "Petty Cash Account",
        ]
        accounts = []
        for name in account_data:
            a, _ = Account.objects.get_or_create(
                name=name,
                defaults={"balance": Decimal("500000.00"), "created_by": user},
            )
            accounts.append(a)
        return accounts

    # ── Suppliers ─────────────────────────────────────────────
    def _create_suppliers(self, user, categories):
        supplier_data = [
            {
                "name": "ABC Trading Co.",
                "contact_person": "Mr. Kamal Hossain",
                "phone": "+8801711111111",
                "email": "info@abctrading.com",
                "address": "12 Banani, Dhaka",
                "rating": Decimal("4.50"),
                "total_orders": 25,
                "payment_terms": "Net 30",
                "tax_id": "TIN-12345678",
                "status": "Active",
            },
            {
                "name": "XYZ Supplies Ltd.",
                "contact_person": "Ms. Fatima Rahman",
                "phone": "+8801722222222",
                "email": "sales@xyzsupplies.com",
                "address": "56 Gulshan, Dhaka",
                "rating": Decimal("4.20"),
                "total_orders": 18,
                "payment_terms": "Net 15",
                "tax_id": "TIN-87654321",
                "status": "Active",
            },
            {
                "name": "Tech Solutions BD",
                "contact_person": "Mr. Rafiq Ahmed",
                "phone": "+8801733333333",
                "email": "contact@techsol.com.bd",
                "address": "89 Uttara, Dhaka",
                "rating": Decimal("3.80"),
                "total_orders": 12,
                "payment_terms": "Net 45",
                "tax_id": "TIN-11223344",
                "status": "Active",
            },
            {
                "name": "Global Office Mart",
                "contact_person": "Mr. Nasir Uddin",
                "phone": "+8801744444444",
                "email": "global@officemart.com",
                "address": "34 Motijheel, Dhaka",
                "rating": Decimal("4.00"),
                "total_orders": 8,
                "payment_terms": "Net 30",
                "tax_id": "TIN-55667788",
                "status": "Active",
            },
            {
                "name": "Prime Distributors",
                "contact_person": "Ms. Shirin Akter",
                "phone": "+8801755555555",
                "email": "info@primedist.com",
                "address": "67 Dhanmondi, Dhaka",
                "rating": Decimal("3.50"),
                "total_orders": 5,
                "payment_terms": "Advance",
                "tax_id": "TIN-99887766",
                "status": "Inactive",
            },
        ]
        suppliers = []
        main_cats = (
            [c for c in categories if c.level == "Main"]
            if hasattr(categories[0], "level")
            else categories[:1]
        )
        for i, data in enumerate(supplier_data):
            cat = main_cats[i % len(main_cats)] if main_cats else None
            s, _ = VendorProfile.objects.get_or_create(
                name=data["name"],
                defaults={
                    "contact_person": data["contact_person"],
                    "phone": data["phone"],
                    "email": data["email"],
                    "address": data["address"],
                    "rating": data["rating"],
                    "total_orders": data["total_orders"],
                    "tax_id": data["tax_id"],
                    "status": data["status"],
                    "created_by": user,
                },
            )
            if cat:
                s.categories.add(cat)
            suppliers.append(s)
        self.stdout.write(f"  Created {len(suppliers)} suppliers")
        return suppliers

    # ── Material Requisitions ─────────────────────────────────
    def _create_material_requisitions(
        self, user, employees, dept, categories, items, budgets, accounts, locations
    ):
        requisitions = []
        req_data = [
            {
                "purpose": "Monthly office supplies for Head Office",
                "priority": "Medium",
                "status": "Approved",
                "item_indices": [0, 1, 6],
                "quantities": [10, 5, 3],
            },
            {
                "purpose": "IT equipment for new staff onboarding",
                "priority": "High",
                "status": "Approved",
                "item_indices": [3, 7, 9],
                "quantities": [2, 5, 2],
            },
            {
                "purpose": "Furniture replacement for conference room",
                "priority": "Medium",
                "status": "Converted to RFQ",
                "item_indices": [4, 5],
                "quantities": [8, 4],
            },
            {
                "purpose": "Quarterly stationery stock replenishment",
                "priority": "Low",
                "status": "Pending Approval",
                "item_indices": [0, 1, 6, 8],
                "quantities": [20, 10, 6, 5],
            },
            {
                "purpose": "Printer toner cartridge urgent order",
                "priority": "Urgent",
                "status": "Draft",
                "item_indices": [2],
                "quantities": [4],
            },
        ]
        main_cats = [c for c in categories if hasattr(c, "level") and c.level == "Main"]
        for i, data in enumerate(req_data):
            mr = MaterialRequisition.objects.create(
                department=dept,
                category=categories[i % len(categories)],
                budget_code=budgets[i % len(budgets)],
                account_code=accounts[i % len(accounts)],
                status=data["status"],
                priority=data["priority"],
                purpose=data["purpose"],
                delivery_location=locations[i % len(locations)],
                delivery_date=date.today() + timedelta(days=random.randint(7, 30)),
                contact_person="Admin User",
                contact_phone="+8801700000000",
                approver1=employees[0],
                approver2=employees[1] if len(employees) > 1 else None,
                created_by=user,
            )
            for idx, item_i in enumerate(data["item_indices"]):
                MaterialItem.objects.create(
                    material_requisition=mr,
                    item=items[item_i],
                    quantity=data["quantities"][idx],
                    created_by=user,
                )
            requisitions.append(mr)
        self.stdout.write(f"  Created {len(requisitions)} material requisitions")
        return requisitions

    # ── RFQ Categories ────────────────────────────────────────
    def _create_rfq_categories(self, user):
        cat_data = [
            ("Office Supplies", "General office supply procurement"),
            ("IT Equipment", "Information technology hardware and software"),
            ("Furniture", "Office furniture and fixtures"),
            ("Services", "Professional and consulting services"),
        ]
        cats = []
        for name, desc in cat_data:
            c, _ = Category.objects.get_or_create(
                name=name,
                defaults={
                    "description": desc,
                    "status": "Active",
                    "created_by": user,
                },
            )
            cats.append(c)
        return cats

    # ── RFQs ──────────────────────────────────────────────────
    def _create_rfqs(self, user, requisitions, rfq_categories, items):
        rfqs = []
        rfq_data = [
            {
                "title": "Office Supplies - Q1 2025",
                "description": "Request for quotation for quarterly office supplies including paper, pens, and markers.",
                "status": "Open",
                "cat_idx": 0,
                "req_idx": 0,
                "item_indices": [0, 1, 6],
            },
            {
                "title": "IT Equipment Procurement - Batch 1",
                "description": "Procurement of laptops, monitors, and USB drives for new staff.",
                "status": "Closed",
                "cat_idx": 1,
                "req_idx": 1,
                "item_indices": [3, 7, 9],
            },
            {
                "title": "Office Furniture Replacement",
                "description": "Replacement of chairs and desk lamps for conference room.",
                "status": "Awarded",
                "cat_idx": 2,
                "req_idx": 2,
                "item_indices": [4, 5],
            },
            {
                "title": "Printer Consumables",
                "description": "Toner cartridges and photocopy paper for all offices.",
                "status": "Draft",
                "cat_idx": 0,
                "req_idx": None,
                "item_indices": [2, 8],
            },
        ]
        for i, data in enumerate(rfq_data):
            rfq = RFQ.objects.create(
                rfq_category=rfq_categories[data["cat_idx"]],
                requisition=(
                    requisitions[data["req_idx"]]
                    if data["req_idx"] is not None
                    else None
                ),
                rfq_title=data["title"],
                description=data["description"],
                submission_deadline=date.today()
                + timedelta(days=random.randint(7, 30)),
                status=data["status"],
                suppliers_count=3,
                responses_received=random.randint(1, 3),
                total_estimated_value=Decimal(str(random.randint(50000, 500000))),
                created_by=user,
            )
            selected_items = [items[idx] for idx in data["item_indices"]]
            rfq.items.set(selected_items)
            rfqs.append(rfq)
        self.stdout.write(f"  Created {len(rfqs)} RFQs")
        return rfqs

    # ── Vendor Quotations ─────────────────────────────────────
    def _create_vendor_quotations(self, user, rfqs, suppliers, items):
        quotations = []
        # For each of the first 3 RFQs, create quotations from different suppliers
        for rfq_idx, rfq in enumerate(rfqs[:3]):
            rfq_items = list(rfq.items.all())
            for sup_idx in range(min(3, len(suppliers))):
                supplier = suppliers[sup_idx]
                # Check unique_together (rfq, supplier)
                if VendorQuotation.objects.filter(rfq=rfq, supplier=supplier).exists():
                    quotations.append(
                        VendorQuotation.objects.get(rfq=rfq, supplier=supplier)
                    )
                    continue
                status_choices = ["Submitted", "Under Review", "Accepted", "Rejected"]
                vq = VendorQuotation.objects.create(
                    rfq=rfq,
                    supplier=supplier,
                    submission_date=timezone.now()
                    - timedelta(days=random.randint(1, 15)),
                    validity_date=date.today() + timedelta(days=60),
                    delivery_terms="Delivery within 15 working days",
                    payment_terms="Net 30 after delivery",
                    warranty_terms="1 year standard warranty",
                    remarks=f"Quotation from {supplier.name}",
                    status=status_choices[sup_idx % len(status_choices)],
                    created_by=user,
                )
                for item in rfq_items:
                    base_price = item.unit_price or Decimal("1000.00")
                    price_variation = Decimal(str(random.uniform(0.85, 1.15)))
                    QuotationItem.objects.create(
                        quotation=vq,
                        item=item,
                        quantity=random.randint(2, 20),
                        unit_price=(base_price * price_variation).quantize(
                            Decimal("0.01")
                        ),
                    )
                quotations.append(vq)
        self.stdout.write(f"  Created {len(quotations)} vendor quotations")
        return quotations

    # ── Quotation Openings ────────────────────────────────────
    def _create_quotation_openings(self, user, employees, rfqs):
        for rfq in rfqs[:3]:
            if hasattr(rfq, "opening"):
                continue
            qo = QuotationOpening.objects.create(
                rfq=rfq,
                opening_date=timezone.now() - timedelta(days=random.randint(1, 10)),
                venue="Conference Room A, Head Office",
                status="Completed",
                minutes="All quotations reviewed and documented. Committee recommends proceeding to comparative analysis.",
                opened_by=user,
            )
            if employees:
                qo.committee_members.set(employees[:3])
        self.stdout.write("  Created quotation openings")

    # ── Comparative Statements ────────────────────────────────
    def _create_comparative_statements(self, user, rfqs, quotations, suppliers, items):
        comparatives = []
        for rfq_idx, rfq in enumerate(rfqs[:3]):
            rfq_quotations = [q for q in quotations if q.rfq_id == rfq.id]
            if not rfq_quotations:
                continue
            cs = ComparativeStatement.objects.create(
                rfq=rfq,
                title=f"Comparative Analysis - {rfq.rfq_title}",
                recommended_supplier=suppliers[0] if suppliers else None,
                justification="Lowest price with acceptable quality and delivery terms.",
                status="Approved" if rfq_idx < 2 else "Draft",
                created_by=user,
                approved_by=user if rfq_idx < 2 else None,
                approved_date=timezone.now() if rfq_idx < 2 else None,
            )
            cs.quotations.set(rfq_quotations)

            rfq_items = list(rfq.items.all())
            for item in rfq_items:
                for q_idx, quot in enumerate(rfq_quotations):
                    qi = QuotationItem.objects.filter(quotation=quot, item=item).first()
                    price = qi.unit_price if qi else Decimal("1000.00")
                    qty = qi.quantity if qi else 1
                    ComparativeLineItem.objects.create(
                        comparative=cs,
                        item=item,
                        quotation=quot,
                        supplier=quot.supplier,
                        quoted_price=price,
                        quantity=qty,
                        is_lowest=(q_idx == 0),
                        is_recommended=(q_idx == 0),
                        remarks="Best value" if q_idx == 0 else "",
                    )
            comparatives.append(cs)
        self.stdout.write(f"  Created {len(comparatives)} comparative statements")
        return comparatives

    # ── Awards ────────────────────────────────────────────────
    def _create_awards(self, user, comparatives, rfqs, suppliers):
        awards = []
        for i, cs in enumerate(comparatives[:2]):
            award = Award.objects.create(
                comparative_statement=cs,
                rfq=cs.rfq,
                award_date=date.today() - timedelta(days=random.randint(1, 15)),
                total_amount=Decimal(str(random.randint(100000, 500000))),
                justification="Selected based on lowest price with best delivery terms as per comparative analysis.",
                terms_and_conditions="Standard procurement terms apply. Delivery within 15 working days.",
                status="Accepted" if i == 0 else "Notified",
                awarded_by=user,
            )
            awards.append(award)
        self.stdout.write(f"  Created {len(awards)} awards")
        return awards

    # ── Award Notifications ───────────────────────────────────
    def _create_award_notifications(self, user, awards, suppliers):
        for award in awards:
            # Award notification to the first seeded supplier
            winner = suppliers[0] if suppliers else None
            if winner:
                winner_profile = (
                    VendorProfile.objects.filter(email__iexact=winner.email).first()
                    if winner and winner.email
                    else None
                )
                if winner_profile:
                    AwardNotification.objects.get_or_create(
                        award=award,
                        vendor_profile=winner_profile,
                        defaults={
                            "notification_type": "Award",
                            "message": f"Congratulations! You have been awarded the contract for {award.comparative_statement.title}.",
                            "is_sent": True,
                            "sent_date": timezone.now() - timedelta(days=2),
                            "is_acknowledged": True,
                            "acknowledged_date": timezone.now() - timedelta(days=1),
                            "sent_by": user,
                        },
                    )
            # Regret notification to another supplier
            other_supplier = [s for s in suppliers if s.id != (winner.id if winner else None)]
            if other_supplier:
                regret_profile = (
                    VendorProfile.objects.filter(email__iexact=other_supplier[0].email).first()
                    if other_supplier[0].email
                    else None
                )
                if regret_profile:
                    AwardNotification.objects.get_or_create(
                        award=award,
                        vendor_profile=regret_profile,
                    defaults={
                        "notification_type": "Regret",
                        "message": "We regret to inform you that your quotation was not selected for this procurement.",
                        "is_sent": True,
                        "sent_date": timezone.now() - timedelta(days=2),
                        "sent_by": user,
                    },
                )
        self.stdout.write("  Created award notifications")

    # ── Work Orders ───────────────────────────────────────────
    def _create_work_orders(self, user, employees, awards, suppliers, items):
        work_orders = []
        wo_data = [
            {
                "supplier_idx": 0,
                "status": "Completed",
                "item_indices": [0, 1, 6],
                "quantities": [10, 5, 3],
                "prices": [Decimal("350.00"), Decimal("115.00"), Decimal("240.00")],
            },
            {
                "supplier_idx": 1,
                "status": "In Progress",
                "item_indices": [3, 9],
                "quantities": [2, 2],
                "prices": [Decimal("63000.00"), Decimal("17500.00")],
            },
            {
                "supplier_idx": 0,
                "status": "Sent to Vendor",
                "item_indices": [4, 5],
                "quantities": [8, 4],
                "prices": [Decimal("8200.00"), Decimal("1150.00")],
            },
        ]
        for i, data in enumerate(wo_data):
            wo = WorkOrder.objects.create(
                award=awards[i] if i < len(awards) else None,
                supplier=suppliers[data["supplier_idx"]],
                delivery_date=date.today() + timedelta(days=random.randint(7, 30)),
                delivery_address="Head Office, 123 Main Street, Dhaka",
                terms_and_conditions="Standard terms and conditions apply.",
                special_instructions="Handle with care. Deliver during office hours only.",
                status=data["status"],
                approved_by=employees[0] if data["status"] != "Draft" else None,
                approved_date=timezone.now() if data["status"] != "Draft" else None,
                created_by=user,
            )
            for idx, item_i in enumerate(data["item_indices"]):
                WorkOrderItem.objects.create(
                    work_order=wo,
                    item=items[item_i],
                    quantity=data["quantities"][idx],
                    unit_price=data["prices"][idx],
                )
            work_orders.append(wo)
        self.stdout.write(f"  Created {len(work_orders)} work orders")
        return work_orders

    # ── Vendor Acceptances ────────────────────────────────────
    def _create_vendor_acceptances(self, work_orders):
        statuses = ["Accepted", "Accepted", "Pending"]
        for i, wo in enumerate(work_orders):
            if hasattr(wo, "vendor_acceptance"):
                continue
            VendorAcceptance.objects.create(
                work_order=wo,
                status=statuses[i % len(statuses)],
                response_date=(
                    timezone.now() - timedelta(days=random.randint(1, 5))
                    if statuses[i % len(statuses)] != "Pending"
                    else None
                ),
                remarks=(
                    "Terms accepted. Will deliver as per schedule."
                    if statuses[i % len(statuses)] == "Accepted"
                    else ""
                ),
            )
        self.stdout.write("  Created vendor acceptances")

    # ── GRNs ──────────────────────────────────────────────────
    def _create_grns(self, user, employees, work_orders, suppliers, items):
        grns = []
        # Create GRN for the first (completed) work order
        wo = work_orders[0]
        grn = GoodsReceiptNote.objects.create(
            work_order=wo,
            supplier=wo.supplier,
            receipt_date=date.today() - timedelta(days=5),
            delivery_note_number="DN-2025-001",
            invoice_number="INV-2025-0042",
            invoice_amount=Decimal("5075.00"),
            remarks="All items received in good condition",
            status="Verified",
            received_by=employees[2] if len(employees) > 2 else employees[0],
            created_by=user,
        )
        wo_items = wo.work_order_items.all()
        for wi in wo_items:
            GRNItem.objects.create(
                grn=grn,
                item=wi.item,
                ordered_quantity=wi.quantity,
                received_quantity=wi.quantity,
                accepted_quantity=wi.quantity,
                rejected_quantity=0,
                unit_price=wi.unit_price,
                condition="Good",
            )
        grns.append(grn)

        # Create a second GRN (partially verified)
        if len(work_orders) > 1:
            wo2 = work_orders[1]
            grn2 = GoodsReceiptNote.objects.create(
                work_order=wo2,
                supplier=wo2.supplier,
                receipt_date=date.today() - timedelta(days=2),
                delivery_note_number="DN-2025-002",
                invoice_number="INV-2025-0056",
                invoice_amount=Decimal("161000.00"),
                remarks="Partial delivery received",
                status="Pending Verification",
                received_by=employees[2] if len(employees) > 2 else employees[0],
                created_by=user,
            )
            wo2_items = wo2.work_order_items.all()
            for wi in wo2_items:
                GRNItem.objects.create(
                    grn=grn2,
                    item=wi.item,
                    ordered_quantity=wi.quantity,
                    received_quantity=max(1, wi.quantity - 1),
                    accepted_quantity=max(1, wi.quantity - 1),
                    rejected_quantity=0,
                    unit_price=wi.unit_price,
                    condition="Good",
                )
            grns.append(grn2)
        self.stdout.write(f"  Created {len(grns)} GRNs")
        return grns

    # ── GRN Verifications ─────────────────────────────────────
    def _create_grn_verifications(self, employees, grns):
        for grn in grns:
            for grn_item in grn.grn_items.all():
                GRNVerification.objects.get_or_create(
                    grn=grn,
                    grn_item=grn_item,
                    defaults={
                        "inspection_date": timezone.now() - timedelta(days=1),
                        "status": "Passed" if grn.status == "Verified" else "Pending",
                        "findings": (
                            "Item condition satisfactory"
                            if grn.status == "Verified"
                            else "Awaiting inspection"
                        ),
                        "verified_by": employees[0],
                    },
                )
        self.stdout.write("  Created GRN verifications")

    # ── Payment Requisitions ──────────────────────────────────
    def _create_payment_requisitions(
        self,
        user,
        employees,
        work_orders,
        grns,
        suppliers,
        budgets,
        accounts,
        project,
        dept,
        items,
    ):
        payment_reqs = []
        prf_data = [
            {
                "wo_idx": 0,
                "grn_idx": 0,
                "supplier_idx": 0,
                "invoice_number": "INV-2025-0042",
                "total_amount": Decimal("5075.00"),
                "tax_amount": Decimal("761.25"),
                "priority": "Medium",
                "status": "Approved",
                "purpose": "Payment for office supplies delivered per WO.",
                "item_desc": [
                    ("A4 Paper (Ream) x 10", 0, 10, Decimal("350.00")),
                    ("Ballpoint Pen (Box) x 5", 1, 5, Decimal("115.00")),
                    ("Whiteboard Marker x 3", 6, 3, Decimal("240.00")),
                ],
            },
            {
                "wo_idx": 1,
                "grn_idx": 1 if len(grns) > 1 else 0,
                "supplier_idx": 1,
                "invoice_number": "INV-2025-0056",
                "total_amount": Decimal("161000.00"),
                "tax_amount": Decimal("24150.00"),
                "priority": "High",
                "status": "Submitted",
                "purpose": "Payment for IT equipment - laptops and monitors.",
                "item_desc": [
                    ("Laptop Computer x 2", 3, 2, Decimal("63000.00")),
                    ("Desktop Monitor x 2", 9, 2, Decimal("17500.00")),
                ],
            },
        ]
        for data in prf_data:
            prf = PaymentRequisition.objects.create(
                work_order=(
                    work_orders[data["wo_idx"]]
                    if data["wo_idx"] < len(work_orders)
                    else None
                ),
                grn=grns[data["grn_idx"]] if data["grn_idx"] < len(grns) else None,
                supplier=suppliers[data["supplier_idx"]],
                invoice_number=data["invoice_number"],
                invoice_date=date.today() - timedelta(days=random.randint(3, 10)),
                invoice_amount=data["total_amount"],
                budget_code=budgets[0],
                account_code=accounts[0],
                project=project,
                department=dept,
                total_amount=data["total_amount"],
                tax_amount=data["tax_amount"],
                priority=data["priority"],
                purpose=data["purpose"],
                status=data["status"],
                approver=employees[1] if len(employees) > 1 else employees[0],
                approved_date=timezone.now() if data["status"] == "Approved" else None,
                created_by=user,
            )
            for desc, item_idx, qty, price in data["item_desc"]:
                PaymentRequisitionItem.objects.create(
                    payment_requisition=prf,
                    description=desc,
                    item=items[item_idx],
                    quantity=qty,
                    unit_price=price,
                )
            payment_reqs.append(prf)
        self.stdout.write(f"  Created {len(payment_reqs)} payment requisitions")
        return payment_reqs

    # ── Treasury Processing ───────────────────────────────────
    def _create_treasury_processing(self, user, employees, payment_reqs, suppliers):
        for i, prf in enumerate(payment_reqs):
            tp = TreasuryProcessing.objects.create(
                payment_requisition=prf,
                budget_verified=True if i == 0 else False,
                budget_remarks=(
                    "Budget allocation confirmed" if i == 0 else "Under review"
                ),
                finance_remarks="All documents verified" if i == 0 else "",
                approved_amount=prf.total_amount if i == 0 else Decimal("0"),
                payment_method="Bank Transfer" if i == 0 else None,
                payment_scheduled_date=(
                    date.today() + timedelta(days=3) if i == 0 else None
                ),
                status="Payment Processed" if i == 0 else "Pending Review",
                reviewed_by=employees[1] if len(employees) > 1 else employees[0],
                reviewed_date=timezone.now() if i == 0 else None,
                approved_by=employees[0] if i == 0 else None,
                approved_date=timezone.now() if i == 0 else None,
                created_by=user,
            )
            # Create payment record for completed one
            if i == 0:
                PaymentRecord.objects.create(
                    treasury_processing=tp,
                    supplier=prf.supplier,
                    payment_date=date.today() - timedelta(days=1),
                    amount=prf.total_amount,
                    payment_method="Bank Transfer",
                    reference_number="TXN-2025-00142",
                    bank_name="Dutch Bangla Bank",
                    account_number="1234567890",
                    status="Completed",
                    remarks="Payment successfully processed",
                    processed_by=user,
                )

            # Payment timeline
            stages = ["PRF Submitted", "Finance Review"]
            if i == 0:
                stages += [
                    "Budget Verified",
                    "Approved for Payment",
                    "Payment Scheduled",
                    "Payment Processed",
                ]
            for stage in stages:
                PaymentTimeline.objects.create(
                    payment_requisition=prf,
                    stage=stage,
                    remarks=f"{stage} completed",
                    performed_by=user,
                )
        self.stdout.write("  Created treasury processing records")

    # ── Purchase Requisitions ─────────────────────────────────
    def _create_purchase_requisitions(self, employees, dept, project, items):
        pr_data = [
            {
                "status": "Approved",
                "item_indices": [0, 1, 2],
                "quantities": [15, 8, 3],
            },
            {
                "status": "Draft",
                "item_indices": [3, 7],
                "quantities": [1, 10],
            },
        ]
        for data in pr_data:
            pr = PurchaseRequisition.objects.create(
                department=dept,
                project=project,
                estimated_amount=Decimal("0"),
                status=data["status"],
                approver=employees[0],
                created_by=employees[0],
            )
            for idx, item_i in enumerate(data["item_indices"]):
                ItemPR.objects.create(
                    purchase_requisition=pr,
                    item=items[item_i],
                    quantity=data["quantities"][idx],
                )
        self.stdout.write("  Created purchase requisitions")

    # ── Purchase Orders ───────────────────────────────────────
    def _create_purchase_orders(self, employees, suppliers, items):
        po_data = [
            {
                "supplier_idx": 0,
                "status": "Completed",
                "item_indices": [0, 1],
                "quantities": [20, 10],
            },
            {
                "supplier_idx": 1,
                "status": "Approved",
                "item_indices": [3, 9],
                "quantities": [3, 2],
            },
        ]
        orders = []
        for data in po_data:
            po = PurchaseOrder.objects.create(
                supplier=suppliers[data["supplier_idx"]],
                delivery_date=date.today() + timedelta(days=15),
                approval_status=data["status"],
                created_by=employees[0],
            )
            for idx, item_i in enumerate(data["item_indices"]):
                ItemPO.objects.create(
                    purchase_order=po,
                    item=items[item_i],
                    quantity=data["quantities"][idx],
                )
            orders.append(po)
        self.stdout.write(f"  Created {len(orders)} purchase orders")
        return orders

    # ── Approval Requests ─────────────────────────────────────
    def _create_approval_requests(self, user):
        ar_data = [
            {
                "type": "Purchase Requisition",
                "department": "Procurement",
                "amount": Decimal("45000.00"),
                "priority": "Normal",
                "status": "Approved",
                "description": "Approval for quarterly office supply procurement.",
            },
            {
                "type": "Purchase Order",
                "department": "IT",
                "amount": Decimal("161000.00"),
                "priority": "High",
                "status": "Pending",
                "description": "Approval needed for IT equipment purchase order.",
            },
            {
                "type": "Request For Quotation",
                "department": "Procurement",
                "amount": Decimal("72000.00"),
                "priority": "Normal",
                "status": "Approved",
                "description": "RFQ distribution approval for furniture replacement.",
            },
        ]
        for data in ar_data:
            ar = ApprovalRequest.objects.create(
                type=data["type"],
                department=data["department"],
                amount=data["amount"],
                priority=data["priority"],
                status=data["status"],
                description=data["description"],
                current_approver=user,
                approval_level=1,
                total_levels=2,
                created_by=user,
            )
            ApprovalHistory.objects.create(
                approval_request=ar,
                approver=user,
                role="Procurement Manager",
                action="Approved" if data["status"] == "Approved" else None,
                comments=(
                    "Reviewed and approved"
                    if data["status"] == "Approved"
                    else "Pending review"
                ),
                level=1,
            )
        self.stdout.write("  Created approval requests")

    # ── Vendor Management ─────────────────────────────────────
    def _create_vendor_management(self, user, employees, suppliers):
        # Vendor Categories
        vc_data = [
            ("Office Supplies Vendor", "Suppliers of general office materials"),
            ("IT Hardware Vendor", "Suppliers of IT equipment and accessories"),
            ("Furniture Vendor", "Suppliers of office furniture"),
            ("Service Provider", "Professional service providers"),
        ]
        vendor_cats = []
        for name, desc in vc_data:
            vc, _ = VendorCategory.objects.get_or_create(
                name=name, defaults={"description": desc, "is_active": True}
            )
            vendor_cats.append(vc)

        # Category mappings
        for i, supplier in enumerate(suppliers[:4]):
            cat = vendor_cats[i % len(vendor_cats)]
            VendorCategoryMapping.objects.get_or_create(supplier=supplier, category=cat)

        # Evaluations
        for supplier in suppliers[:3]:
            if VendorEvaluation.objects.filter(supplier=supplier).exists():
                continue
            VendorEvaluation.objects.create(
                supplier=supplier,
                evaluation_date=date.today() - timedelta(days=random.randint(10, 60)),
                quality_rating=random.randint(3, 5),
                delivery_rating=random.randint(3, 5),
                price_rating=random.randint(3, 5),
                compliance_rating=random.randint(3, 5),
                communication_rating=random.randint(3, 5),
                comments="Performance within acceptable range.",
                recommendation="Continue business relationship.",
                evaluated_by=employees[0],
            )

        # Onboarding
        for supplier in suppliers[:3]:
            if hasattr(supplier, "onboarding"):
                continue
            VendorOnboarding.objects.create(
                supplier=supplier,
                status="Approved",
                trade_license=True,
                tax_certificate=True,
                bank_details=True,
                nda_signed=True,
                reference_verified=True,
                compliance_checked=True,
                remarks="All verification steps completed.",
                initiated_by=user,
                completed_date=timezone.now() - timedelta(days=30),
            )

        # Verification
        for supplier in suppliers[:3]:
            if hasattr(supplier, "verification"):
                continue
            VendorVerification.objects.create(
                supplier=supplier,
                status="Verified",
                verification_date=date.today() - timedelta(days=30),
                documents_verified=True,
                financial_check=True,
                compliance_check=True,
                remarks="Vendor verified and approved for procurement.",
                verified_by=employees[0],
            )

        # Performance records
        for supplier in suppliers[:3]:
            for month_offset in range(3):
                m = date.today().month - month_offset
                y = date.today().year
                if m <= 0:
                    m += 12
                    y -= 1
                if VendorPerformance.objects.filter(
                    supplier=supplier, period_month=m, period_year=y
                ).exists():
                    continue
                VendorPerformance.objects.create(
                    supplier=supplier,
                    period_month=m,
                    period_year=y,
                    total_orders=random.randint(3, 10),
                    on_time_deliveries=random.randint(2, 8),
                    late_deliveries=random.randint(0, 2),
                    rejected_items=random.randint(0, 1),
                    total_spent=Decimal(str(random.randint(50000, 300000))),
                    avg_delivery_days=Decimal(str(random.uniform(3.0, 10.0))).quantize(
                        Decimal("0.1")
                    ),
                    compliance_score=Decimal(str(random.uniform(80.0, 99.0))).quantize(
                        Decimal("0.01")
                    ),
                )
        self.stdout.write("  Created vendor management data")

    # ── Notifications ─────────────────────────────────────────
    def _create_notifications(self, user):
        notif_data = [
            {
                "title": "New Material Requisition Submitted",
                "message": "A new material requisition REQ-2025-0001 has been submitted for approval.",
                "notification_type": "Requisition",
                "priority": "Medium",
            },
            {
                "title": "RFQ Closing Soon",
                "message": "RFQ RFQ-2025-001 submission deadline is approaching in 3 days.",
                "notification_type": "RFQ",
                "priority": "High",
            },
            {
                "title": "Award Decision Pending",
                "message": "Comparative statement CS-2025-0001 is approved. Please proceed with award.",
                "notification_type": "Award",
                "priority": "Medium",
            },
            {
                "title": "Payment Processed",
                "message": "Payment of BDT 5,075.00 has been successfully processed via bank transfer.",
                "notification_type": "Payment",
                "priority": "Low",
            },
            {
                "title": "GRN Pending Verification",
                "message": "GRN GRN-2025-0002 requires quality inspection and verification.",
                "notification_type": "GRN",
                "priority": "High",
            },
            {
                "title": "Work Order Sent to Vendor",
                "message": "Work order WO-2025-0003 has been sent to the vendor for acceptance.",
                "notification_type": "Work Order",
                "priority": "Medium",
            },
        ]
        for data in notif_data:
            ProcurementNotification.objects.get_or_create(
                title=data["title"],
                recipient=user,
                defaults={
                    "message": data["message"],
                    "notification_type": data["notification_type"],
                    "priority": data["priority"],
                },
            )
        self.stdout.write("  Created procurement notifications")

    # ── Settings ──────────────────────────────────────────────
    def _create_settings(self, user, employees, dept):
        # Approval Matrix
        matrix_data = [
            (
                "Material Requisition",
                1,
                Decimal("0"),
                Decimal("50000"),
                "Department Head",
            ),
            (
                "Material Requisition",
                2,
                Decimal("50000"),
                Decimal("500000"),
                "Director",
            ),
            (
                "Purchase Requisition",
                1,
                Decimal("0"),
                Decimal("100000"),
                "Procurement Manager",
            ),
            ("RFQ", 1, Decimal("0"), None, "Procurement Manager"),
            (
                "Comparative Statement",
                1,
                Decimal("0"),
                Decimal("200000"),
                "Procurement Committee",
            ),
            ("Award", 1, Decimal("0"), None, "Director"),
            ("Work Order", 1, Decimal("0"), Decimal("100000"), "Procurement Manager"),
            (
                "Payment Requisition",
                1,
                Decimal("0"),
                Decimal("50000"),
                "Finance Manager",
            ),
            ("GRN", 1, Decimal("0"), None, "Store Manager"),
        ]
        for module, level, min_amt, max_amt, role in matrix_data:
            ApprovalMatrix.objects.get_or_create(
                module=module,
                approval_level=level,
                defaults={
                    "min_amount": min_amt,
                    "max_amount": max_amt,
                    "approver_role": role,
                    "approver": employees[0] if employees else None,
                    "department": dept,
                    "is_active": True,
                },
            )

        # Email Templates
        templates = [
            {
                "name": "Requisition Submitted",
                "module": "Requisition",
                "subject": "New Requisition Submitted - {{requisition_no}}",
                "body": "Dear {{approver_name}},\n\nA new material requisition {{requisition_no}} has been submitted for your approval.\n\nPurpose: {{purpose}}\nAmount: {{amount}}\n\nPlease review and take action.\n\nRegards,\nProcurement System",
            },
            {
                "name": "RFQ Published",
                "module": "RFQ",
                "subject": "New RFQ Published - {{rfq_number}}",
                "body": "Dear {{supplier_name}},\n\nA new Request for Quotation has been published.\n\nRFQ: {{rfq_number}}\nTitle: {{rfq_title}}\nDeadline: {{deadline}}\n\nPlease submit your quotation before the deadline.\n\nRegards,\nProcurement Team",
            },
            {
                "name": "Award Notification",
                "module": "Award",
                "subject": "Contract Award Notification - {{award_number}}",
                "body": "Dear {{supplier_name}},\n\nWe are pleased to inform you that you have been awarded the contract {{award_number}}.\n\nTotal Amount: {{total_amount}}\n\nPlease confirm your acceptance.\n\nRegards,\nProcurement Team",
            },
            {
                "name": "Payment Processed",
                "module": "Payment",
                "subject": "Payment Processed - {{prf_number}}",
                "body": "Dear {{supplier_name}},\n\nPayment for {{prf_number}} has been processed.\n\nAmount: {{amount}}\nMethod: {{payment_method}}\nReference: {{reference_number}}\n\nRegards,\nFinance Team",
            },
        ]
        for tmpl in templates:
            EmailTemplate.objects.get_or_create(
                name=tmpl["name"],
                defaults={
                    "module": tmpl["module"],
                    "subject": tmpl["subject"],
                    "body": tmpl["body"],
                    "is_active": True,
                    "variables": [],
                    "created_by": user,
                },
            )

        # Procurement Roles
        role_data = [
            {
                "name": "Procurement Manager",
                "description": "Full procurement management access",
                "perms": {
                    "can_create_requisition": True,
                    "can_approve_requisition": True,
                    "can_create_rfq": True,
                    "can_manage_vendors": True,
                    "can_create_comparative": True,
                    "can_approve_comparative": True,
                    "can_create_award": True,
                    "can_create_work_order": True,
                    "can_approve_work_order": True,
                    "can_create_grn": True,
                    "can_create_payment": True,
                    "can_approve_payment": True,
                    "can_process_treasury": False,
                    "can_view_reports": True,
                    "can_manage_settings": True,
                },
            },
            {
                "name": "Finance Officer",
                "description": "Finance and payment processing access",
                "perms": {
                    "can_create_requisition": False,
                    "can_approve_requisition": False,
                    "can_create_rfq": False,
                    "can_manage_vendors": False,
                    "can_create_comparative": False,
                    "can_approve_comparative": False,
                    "can_create_award": False,
                    "can_create_work_order": False,
                    "can_approve_work_order": False,
                    "can_create_grn": False,
                    "can_create_payment": True,
                    "can_approve_payment": True,
                    "can_process_treasury": True,
                    "can_view_reports": True,
                    "can_manage_settings": False,
                },
            },
            {
                "name": "Store Keeper",
                "description": "Inventory and GRN management",
                "perms": {
                    "can_create_requisition": True,
                    "can_approve_requisition": False,
                    "can_create_rfq": False,
                    "can_manage_vendors": False,
                    "can_create_comparative": False,
                    "can_approve_comparative": False,
                    "can_create_award": False,
                    "can_create_work_order": False,
                    "can_approve_work_order": False,
                    "can_create_grn": True,
                    "can_create_payment": False,
                    "can_approve_payment": False,
                    "can_process_treasury": False,
                    "can_view_reports": True,
                    "can_manage_settings": False,
                },
            },
        ]
        roles = []
        for rd in role_data:
            role, _ = ProcurementRole.objects.get_or_create(
                name=rd["name"],
                defaults={"description": rd["description"], **rd["perms"]},
            )
            roles.append(role)

        # Assign roles to user
        if roles:
            ProcurementUserRole.objects.get_or_create(user=user, role=roles[0])

        # Notification Settings
        ns_data = [
            ("Requisition", "Requisition Submitted"),
            ("Requisition", "Requisition Approved"),
            ("RFQ", "RFQ Published"),
            ("RFQ", "RFQ Closed"),
            ("Quotation", "Quotation Received"),
            ("Comparative", "Comparative Approved"),
            ("Award", "Award Decision Made"),
            ("Work Order", "Work Order Issued"),
            ("GRN", "Goods Received"),
            ("Payment", "Payment Requested"),
            ("Treasury", "Payment Processed"),
        ]
        for module, event in ns_data:
            NotificationSetting.objects.get_or_create(
                module=module,
                event_name=event,
                defaults={
                    "email_enabled": True,
                    "in_app_enabled": True,
                    "sms_enabled": False,
                    "is_active": True,
                },
            )
        self.stdout.write("  Created procurement settings")
