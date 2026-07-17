"""
Seed workspace transaction pages: vendor bills, credit notes, customer receipts,
bank deposits, and supplier payments with realistic LEDARS NGO data.

Run: python manage.py seed_workspace
     python manage.py seed_workspace --clear   (drops and re-seeds workspace rows)
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounting.models import (
    Customer,
    Vendor,
    Invoice,
    Bill,
    BillLine,
    CreditNote,
    Journal,
    Account,
    CustomerReceipt,
    CustomerReceiptAllocation,
    BankDeposit,
    SupplierPayment,
)

User = get_user_model()

TODAY = date(2026, 3, 30)


def d(delta_days: int) -> date:
    return TODAY + timedelta(days=delta_days)


class Command(BaseCommand):
    help = "Seed workspace transaction pages with sample data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing workspace data before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            SupplierPayment.objects.all().delete()
            BankDeposit.objects.all().delete()
            CustomerReceiptAllocation.objects.all().delete()
            CustomerReceipt.objects.all().delete()
            self.stdout.write("Cleared existing workspace data.")

        user = User.objects.filter(is_superuser=True).first()

        # ── Journals ──────────────────────────────────────────────────────────
        purchase_journal = Journal.objects.filter(journal_type="purchase").first()
        sales_journal = Journal.objects.filter(journal_type="sales").first()
        if not purchase_journal:
            purchase_journal = Journal.objects.first()
        if not sales_journal:
            sales_journal = purchase_journal

        # ── Default expense account ────────────────────────────────────────────
        expense_account = (
            Account.objects.filter(account_type__classification="expense").first()
            or Account.objects.first()
        )

        # ── Seed Vendors ───────────────────────────────────────────────────────
        VENDOR_DATA = [
            {
                "name": "HealthServe Supplies Ltd",
                "email": "ap@healthserve.com",
                "phone": "+880-11-8800",
            },
            {
                "name": "Office Depot Bangladesh",
                "email": "billing@officedepot.bd",
                "phone": "+880-11-7700",
            },
            {
                "name": "Green Logistics Co.",
                "email": "finance@greenlogistics.bd",
                "phone": "+880-11-6600",
            },
        ]
        vendors = []
        for vd in VENDOR_DATA:
            v, _ = Vendor.objects.get_or_create(
                name=vd["name"],
                defaults={
                    "email": vd["email"],
                    "phone": vd["phone"],
                    "status": "active",
                },
            )
            vendors.append(v)
        self.stdout.write(f"  Vendors: {len(vendors)} ready.")

        # ── Seed Bills ─────────────────────────────────────────────────────────
        BILL_DATA = [
            {
                "vendor_idx": 0,
                "bill_date": d(-25),
                "due_date": d(-3),
                "amount": Decimal("98700"),
                "vendor_reference": "HSV-11984",
                "goods_receipt_ref": "GRN-884",
                "match_status": "3-way matched",
                "dispute_flag": False,
                "payment_proposal": "Next run",
                "approval_route": "Finance Controller",
                "description": "Medical supplies - Q1 2026",
            },
            {
                "vendor_idx": 1,
                "bill_date": d(-20),
                "due_date": d(10),
                "amount": Decimal("23400"),
                "vendor_reference": "ODB-5023",
                "goods_receipt_ref": "GRN-891",
                "match_status": "2-way matched",
                "dispute_flag": False,
                "payment_proposal": "Next run",
                "approval_route": "Admin Manager",
                "description": "Office stationery and supplies",
            },
            {
                "vendor_idx": 2,
                "bill_date": d(-15),
                "due_date": d(5),
                "amount": Decimal("56200"),
                "vendor_reference": "GL-7241",
                "goods_receipt_ref": "",
                "match_status": "Awaiting receipt",
                "dispute_flag": True,
                "payment_proposal": "On-hold",
                "approval_route": "COO",
                "description": "Field logistics - March 2026",
            },
        ]
        bills = []
        for bd in BILL_DATA:
            vendor = vendors[bd["vendor_idx"]]
            existing = Bill.objects.filter(vendor=vendor, bill_date=bd["bill_date"]).first()
            if existing:
                bills.append(existing)
                continue

            bill = Bill.objects.create(
                vendor=vendor,
                journal=purchase_journal,
                bill_date=bd["bill_date"],
                due_date=bd["due_date"],
                vendor_reference=bd["vendor_reference"],
                goods_receipt_ref=bd["goods_receipt_ref"],
                match_status=bd["match_status"],
                dispute_flag=bd["dispute_flag"],
                payment_proposal=bd["payment_proposal"],
                approval_route=bd["approval_route"],
                subtotal=bd["amount"],
                tax_amount=Decimal("0"),
                total_amount=bd["amount"],
                amount_paid=Decimal("0"),
                amount_due=bd["amount"],
                status="draft",
                notes=bd["description"],
                created_by=user,
            )
            if expense_account:
                BillLine.objects.create(
                    bill=bill,
                    account=expense_account,
                    description=bd["description"],
                    quantity=1,
                    unit_price=bd["amount"],
                    subtotal=bd["amount"],
                )
            bills.append(bill)
        self.stdout.write(f"  Bills: {len(bills)} ready.")

        # ── Seed Customers ─────────────────────────────────────────────────────
        CUSTOMER_DATA = [
            {"name": "UNHCR Bangladesh", "email": "unhcr@ledars.ngo"},
            {"name": "UNICEF Field Office", "email": "unicef@ledars.ngo"},
            {"name": "World Vision BD", "email": "wv@ledars.ngo"},
        ]
        customers = []
        for cd in CUSTOMER_DATA:
            c, _ = Customer.objects.get_or_create(
                name=cd["name"],
                defaults={"email": cd["email"], "status": "active"},
            )
            customers.append(c)
        self.stdout.write(f"  Customers: {len(customers)} ready.")

        # ── Seed Credit Notes ──────────────────────────────────────────────────
        CN_DATA = [
            {
                "customer_idx": 0,
                "date": d(-10),
                "amount": Decimal("15000"),
                "reason": "Price adjustment on grant disbursement",
                "adjustment_type": "Price Adjustment",
                "approval_route": "AR Manager",
                "refund_reference": "REF-CN-001",
                "application_notes": "Applied to INV-2026-001",
                "status": "draft",
            },
            {
                "customer_idx": 1,
                "date": d(-5),
                "amount": Decimal("8500"),
                "reason": "Service not delivered - partial credit",
                "adjustment_type": "Service Credit",
                "approval_route": "Finance Head",
                "refund_reference": "REF-CN-002",
                "application_notes": "Pending allocation",
                "status": "draft",
            },
        ]
        for cn_data in CN_DATA:
            customer = customers[cn_data["customer_idx"]]
            if CreditNote.objects.filter(
                customer=customer, date=cn_data["date"]
            ).exists():
                continue
            CreditNote.objects.create(
                customer=customer,
                journal=sales_journal,
                date=cn_data["date"],
                reason=cn_data["reason"],
                total_amount=cn_data["amount"],
                status=cn_data["status"],
                adjustment_type=cn_data["adjustment_type"],
                approval_route=cn_data["approval_route"],
                refund_reference=cn_data["refund_reference"],
                application_notes=cn_data["application_notes"],
                created_by=user,
            )
        cn_count = CreditNote.objects.count()
        self.stdout.write(f"  CreditNotes: {cn_count} total.")

        # ── Seed Customer Receipts ─────────────────────────────────────────────
        RECEIPT_DATA = [
            {
                "customer_idx": 0,
                "date": d(-8),
                "method": "Bank Transfer",
                "bank_account_name": "NGO Operations – Dhaka",
                "amount": Decimal("125000"),
                "reference": "UNHCR-PAY-2026-03",
                "collection_owner": "Rina Akter",
                "status": "posted",
                "allocation_status": "fully_allocated",
                "notes": "Q1 grant instalment",
            },
            {
                "customer_idx": 1,
                "date": d(-3),
                "method": "Cheque",
                "bank_account_name": "NGO Operations – Dhaka",
                "amount": Decimal("45000"),
                "reference": "UNICEF-ADV-2026-Q1",
                "collection_owner": "Karim Hossain",
                "status": "draft",
                "allocation_status": "unallocated",
                "notes": "Advance payment for field activities",
            },
            {
                "customer_idx": 2,
                "date": d(-1),
                "method": "Bank Transfer",
                "bank_account_name": "Project Account – Sylhet",
                "amount": Decimal("68000"),
                "reference": "WV-2026-MAR-02",
                "collection_owner": "Nadia Islam",
                "status": "draft",
                "allocation_status": "unallocated",
                "notes": "Field programme funding",
            },
        ]
        if not CustomerReceipt.objects.exists():
            for rd in RECEIPT_DATA:
                customer = customers[rd["customer_idx"]]
                unapplied = (
                    Decimal("0")
                    if rd["allocation_status"] == "fully_allocated"
                    else rd["amount"]
                )
                receipt = CustomerReceipt.objects.create(
                    customer=customer,
                    date=rd["date"],
                    method=rd["method"],
                    bank_account_name=rd["bank_account_name"],
                    amount=rd["amount"],
                    unapplied_amount=unapplied,
                    reference=rd["reference"],
                    collection_owner=rd["collection_owner"],
                    status=rd["status"],
                    allocation_status=rd["allocation_status"],
                    notes=rd["notes"],
                    created_by=user,
                )
                if rd["allocation_status"] == "fully_allocated":
                    CustomerReceiptAllocation.objects.create(
                        receipt=receipt,
                        invoice_number="INV-2026-001",
                        amount=rd["amount"],
                    )
        self.stdout.write(f"  CustomerReceipts: {CustomerReceipt.objects.count()} total.")

        # ── Seed Bank Deposits ─────────────────────────────────────────────────
        DEPOSIT_DATA = [
            {
                "date": d(-7),
                "bank_account_name": "NGO Operations – Dhaka",
                "source": "UNHCR Grant",
                "deposit_method": "Bank Transfer",
                "deposit_slip_ref": "SLP-2026-031",
                "prepared_by": "Rina Akter",
                "amount": Decimal("125000"),
                "description": "Q1 2026 grant receipt from UNHCR",
                "status": "posted",
                "reconciliation_status": "reconciled",
            },
            {
                "date": d(-2),
                "bank_account_name": "Project Account – Sylhet",
                "source": "World Vision BD",
                "deposit_method": "Cheque",
                "deposit_slip_ref": "SLP-2026-032",
                "prepared_by": "Karim Hossain",
                "amount": Decimal("68000"),
                "description": "Field programme funding – March 2026",
                "status": "draft",
                "reconciliation_status": "pending",
            },
        ]
        if not BankDeposit.objects.exists():
            for dd in DEPOSIT_DATA:
                BankDeposit.objects.create(**{**dd, "created_by": user})
        self.stdout.write(f"  BankDeposits: {BankDeposit.objects.count()} total.")

        # ── Seed Supplier Payments ─────────────────────────────────────────────
        SP_DATA = [
            {
                "vendor_idx": 0,
                "date": d(-2),
                "method": "Bank Transfer",
                "bank_account_name": "NGO Operations – Dhaka",
                "amount": Decimal("98700"),
                "status": "posted",
                "release_status": "released",
                "payment_run": "PR-2026-Q1-01",
                "bill_refs": [bills[0].bill_number] if bills else ["BILL-2026-00001"],
                "approval_route": "Finance Controller",
                "settlement_reference": "SETTLE-2026-031",
                "notes": "Full payment of March medical supplies bill",
            },
            {
                "vendor_idx": 1,
                "date": d(3),
                "method": "Bank Transfer",
                "bank_account_name": "NGO Operations – Dhaka",
                "amount": Decimal("23400"),
                "status": "draft",
                "release_status": "queued",
                "payment_run": "PR-2026-Q1-02",
                "bill_refs": [bills[1].bill_number] if len(bills) > 1 else ["BILL-2026-00002"],
                "approval_route": "Admin Manager",
                "settlement_reference": "",
                "notes": "Pending release for office supplies payment",
            },
            {
                "vendor_idx": 2,
                "date": d(5),
                "method": "Cheque",
                "bank_account_name": "NGO Operations – Dhaka",
                "amount": Decimal("56200"),
                "status": "draft",
                "release_status": "blocked",
                "payment_run": "PR-2026-Q1-02",
                "bill_refs": [bills[2].bill_number] if len(bills) > 2 else ["BILL-2026-00003"],
                "approval_route": "COO",
                "settlement_reference": "",
                "notes": "Blocked pending dispute resolution on logistics bill",
            },
        ]
        if not SupplierPayment.objects.exists():
            for sp in SP_DATA:
                vendor = vendors[sp.pop("vendor_idx")]
                SupplierPayment.objects.create(
                    vendor=vendor,
                    created_by=user,
                    **sp,
                )
        self.stdout.write(f"  SupplierPayments: {SupplierPayment.objects.count()} total.")

        self.stdout.write(self.style.SUCCESS("\n✅  Workspace seed complete!"))
