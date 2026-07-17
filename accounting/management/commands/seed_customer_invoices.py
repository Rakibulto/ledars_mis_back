"""
Seed the CustomerInvoice transaction workspace with exactly the same
records that appear in the frontend mock-data.js (3 customers, 3 invoices).

Run:
    python manage.py seed_customer_invoices
    python manage.py seed_customer_invoices --clear   # wipe before re-seeding
"""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounting.models import Customer
from accounting.models.transaction_customer_inv import (
    CustomerInvoice,
    CustomerInvoiceAllocation,
    CustomerInvoiceAttachment,
    CustomerInvoiceChatter,
    CustomerInvoiceLine,
)


# ── Exact frontend MOCK_CUSTOMERS ──────────────────────────────────────────
CUSTOMER_SEED = [
    {
        "name": "UNICEF Regional Office",
        "email": "finance@unicef.org",
        "credit_limit": Decimal("350000.00"),
        "code": "UNICEF-001",
        "status": "active",
    },
    {
        "name": "Save The Children",
        "email": "ap@stc.org",
        "credit_limit": Decimal("240000.00"),
        "code": "STC-001",
        "status": "active",
    },
    {
        "name": "BRAC Social Innovation",
        "email": "accounts@brac.net",
        "credit_limit": Decimal("180000.00"),
        "code": "BRAC-001",
        "status": "active",
    },
]

# ── Exact frontend MOCK_INVOICES ───────────────────────────────────────────
INVOICE_SEED = [
    {
        "number": "INV-2026-031",
        "customer_name": "UNICEF Regional Office",
        "date": date(2026, 3, 1),
        "due_date": date(2026, 3, 31),
        "status": "partial",
        "dunning_stage": "stage_2",
        "promise_to_pay": date(2026, 3, 26),
        "credit_warning": False,
        "payment_terms": "Net 30",
        "service_period": "March 2026",
        "billing_owner": "Accounts Receivable",
        "billing_reference": "SOW-EDU-031",
        "recurring": False,
        "recurring_label": "",
        "subtotal": Decimal("128000.00"),
        "tax_amount": Decimal("6400.00"),
        "total": Decimal("134400.00"),
        "paid_amount": Decimal("74400.00"),
        "balance_due": Decimal("60000.00"),
        "linked_journals": ["JE-2026-031", "JE-2026-036"],
        "lines": [
            {
                "description": "Program management fee",
                "quantity": Decimal("1"),
                "unit_price": Decimal("78000.00"),
                "amount": Decimal("78000.00"),
                "analytic": "Education Program",
            },
            {
                "description": "Monitoring and reporting",
                "quantity": Decimal("1"),
                "unit_price": Decimal("50000.00"),
                "amount": Decimal("50000.00"),
                "analytic": "Education Program",
            },
        ],
        "allocations": [
            {
                "date": date(2026, 3, 10),
                "amount": Decimal("50000.00"),
                "method": "Bank transfer",
                "reference": "RCPT-0092",
            },
            {
                "date": date(2026, 3, 15),
                "amount": Decimal("24400.00"),
                "method": "Offset",
                "reference": "RCPT-0094",
            },
        ],
        "attachments": [
            {"name": "SOW-EDU-031.pdf", "file_type": "pdf"},
            {"name": "Invoice_INV-2026-031.pdf", "file_type": "pdf"},
        ],
        "chatter": [
            {
                "author": "Billing System",
                "message": "Invoice INV-2026-031 generated for UNICEF Regional Office.",
                "time_label": "01 Mar, 09:00",
                "message_type": "system",
            },
            {
                "author": "Finance Officer",
                "message": "First payment of 50,000 received. Invoice moved to partial.",
                "time_label": "10 Mar, 14:30",
                "message_type": "payment",
            },
            {
                "author": "Finance Officer",
                "message": "Follow-up sent. Customer promised payment by 26 March.",
                "time_label": "18 Mar, 10:15",
                "message_type": "dunning",
            },
        ],
    },
    {
        "number": "INV-2026-032",
        "customer_name": "Save The Children",
        "date": date(2026, 3, 1),
        "due_date": date(2026, 3, 31),
        "status": "sent",
        "dunning_stage": "none",
        "promise_to_pay": None,
        "credit_warning": False,
        "payment_terms": "Net 30",
        "service_period": "March 2026",
        "billing_owner": "Accounts Receivable",
        "billing_reference": "RET-MAR-2026",
        "recurring": True,
        "recurring_label": "Monthly monitoring retainer",
        "subtotal": Decimal("86000.00"),
        "tax_amount": Decimal("4300.00"),
        "total": Decimal("90300.00"),
        "paid_amount": Decimal("0.00"),
        "balance_due": Decimal("90300.00"),
        "linked_journals": ["JE-2026-032"],
        "lines": [
            {
                "description": "Monitoring retainer - March",
                "quantity": Decimal("1"),
                "unit_price": Decimal("86000.00"),
                "amount": Decimal("86000.00"),
                "analytic": "Operations Support",
            },
        ],
        "allocations": [],
        "attachments": [
            {"name": "Retainer_Agreement_Mar2026.pdf", "file_type": "pdf"},
        ],
        "chatter": [
            {
                "author": "Billing System",
                "message": "Recurring invoice INV-2026-032 generated — Monthly monitoring retainer.",
                "time_label": "01 Mar, 09:01",
                "message_type": "system",
            },
            {
                "author": "Finance Officer",
                "message": "Invoice sent to Save The Children.",
                "time_label": "02 Mar, 11:00",
                "message_type": "system",
            },
        ],
    },
    {
        "number": "INV-2026-033",
        "customer_name": "BRAC Social Innovation",
        "date": date(2026, 2, 28),
        "due_date": date(2026, 3, 15),
        "status": "overdue",
        "dunning_stage": "stage_3",
        "promise_to_pay": date(2026, 3, 30),
        "credit_warning": True,
        "payment_terms": "Net 15",
        "service_period": "February 2026",
        "billing_owner": "Collections Lead",
        "billing_reference": "WS-CAP-033",
        "recurring": False,
        "recurring_label": "",
        "subtotal": Decimal("72000.00"),
        "tax_amount": Decimal("3600.00"),
        "total": Decimal("75600.00"),
        "paid_amount": Decimal("0.00"),
        "balance_due": Decimal("75600.00"),
        "linked_journals": ["JE-2026-033"],
        "lines": [
            {
                "description": "Capacity-building workshop",
                "quantity": Decimal("3"),
                "unit_price": Decimal("24000.00"),
                "amount": Decimal("72000.00"),
                "analytic": "Social Innovation",
            },
        ],
        "allocations": [],
        "attachments": [
            {"name": "Workshop_Proposal_WS-CAP-033.pdf", "file_type": "pdf"},
        ],
        "chatter": [
            {
                "author": "Billing System",
                "message": "Invoice INV-2026-033 generated for BRAC Social Innovation.",
                "time_label": "28 Feb, 09:00",
                "message_type": "system",
            },
            {
                "author": "Finance Officer",
                "message": "Invoice is now overdue. Escalated to Collections Lead.",
                "time_label": "16 Mar, 08:00",
                "message_type": "dunning",
            },
            {
                "author": "Collections Lead",
                "message": "Stage 3 dunning notice dispatched. Customer credit warning flag raised.",
                "time_label": "18 Mar, 09:30",
                "message_type": "dunning",
            },
            {
                "author": "Collections Lead",
                "message": "Customer promised full payment by 30 March.",
                "time_label": "19 Mar, 14:00",
                "message_type": "note",
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Seed CustomerInvoice workspace with exact frontend mock data (3 customers, 3 invoices)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing CustomerInvoice records before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = CustomerInvoice.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted} existing invoices."))

        try:
            with transaction.atomic():
                customers = self._seed_customers()
                self._seed_invoices(customers)
            self.stdout.write(
                self.style.SUCCESS(
                    "✔ Customer invoice seed complete — 3 customers, 3 invoices seeded."
                )
            )
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Seeding failed: {exc}"))
            raise

    # ── Helpers ────────────────────────────────────────────────────────────

    def _seed_customers(self) -> dict[str, Customer]:
        """Create or update the 3 mock customers, return name→Customer map."""
        result = {}
        for data in CUSTOMER_SEED:
            customer, created = Customer.objects.get_or_create(
                name=data["name"],
                defaults={
                    "email": data["email"],
                    "credit_limit": data["credit_limit"],
                    "code": data["code"],
                    "status": data["status"],
                },
            )
            if not created:
                # Keep email / credit_limit in sync with mock values
                Customer.objects.filter(pk=customer.pk).update(
                    email=data["email"],
                    credit_limit=data["credit_limit"],
                )
            result[data["name"]] = customer
            verb = "Created" if created else "Updated"
            self.stdout.write(f"  {verb} customer: {customer.name}")
        return result

    def _seed_invoices(self, customers: dict[str, Customer]):
        """Create invoices (and all nested records) from INVOICE_SEED."""
        for inv_data in INVOICE_SEED:
            customer = customers[inv_data["customer_name"]]

            # Skip if the invoice number already exists (idempotent)
            if CustomerInvoice.objects.filter(number=inv_data["number"]).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipped (already exists): {inv_data['number']}"
                    )
                )
                continue

            invoice = CustomerInvoice.objects.create(
                number=inv_data["number"],
                customer=customer,
                date=inv_data["date"],
                due_date=inv_data["due_date"],
                status=inv_data["status"],
                dunning_stage=inv_data["dunning_stage"],
                promise_to_pay=inv_data["promise_to_pay"],
                credit_warning=inv_data["credit_warning"],
                payment_terms=inv_data["payment_terms"],
                service_period=inv_data["service_period"],
                billing_owner=inv_data["billing_owner"],
                billing_reference=inv_data["billing_reference"],
                recurring=inv_data["recurring"],
                recurring_label=inv_data["recurring_label"],
                subtotal=inv_data["subtotal"],
                tax_amount=inv_data["tax_amount"],
                total=inv_data["total"],
                paid_amount=inv_data["paid_amount"],
                balance_due=inv_data["balance_due"],
                linked_journals=inv_data["linked_journals"],
            )

            for line in inv_data["lines"]:
                CustomerInvoiceLine.objects.create(invoice=invoice, **line)

            for alloc in inv_data["allocations"]:
                CustomerInvoiceAllocation.objects.create(invoice=invoice, **alloc)

            for attach in inv_data["attachments"]:
                CustomerInvoiceAttachment.objects.create(invoice=invoice, **attach)

            for chat in inv_data["chatter"]:
                CustomerInvoiceChatter.objects.create(invoice=invoice, **chat)

            self.stdout.write(
                f"  Created invoice: {invoice.number} ({customer.name}) — "
                f"status={invoice.status}"
            )
