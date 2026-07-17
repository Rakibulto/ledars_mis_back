from django.utils import timezone
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounting.models import Customer
from accounting.models.transaction_customer_inv import (
    CustomerInvoice,
    CustomerInvoiceAllocation,
    CustomerInvoiceChatter,
)
from accounting.serializers.customer_invoice_serializers import (
    CustomerInvoiceCustomerSerializer,
    CustomerInvoiceDetailSerializer,
    CustomerInvoiceListSerializer,
    CustomerInvoiceWriteSerializer,
)
from accounting.views.status_transition_mixin import StatusTransitionMixin


class CustomerInvoiceViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    """Full CRUD ViewSet for the CustomerInvoice transaction workspace.

    Exposes:
        GET    /api/acc-customer-invoices/           — list
        POST   /api/acc-customer-invoices/           — create
        GET    /api/acc-customer-invoices/{id}/      — retrieve
        PATCH  /api/acc-customer-invoices/{id}/      — partial update
        DELETE /api/acc-customer-invoices/{id}/      — destroy
        POST   /api/acc-customer-invoices/{id}/send/ — mark as sent
    """

    queryset = CustomerInvoice.objects.select_related("customer").prefetch_related(
        "lines", "allocations", "attachments", "chatter"
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["customer", "status", "dunning_stage", "recurring", "date"]
    search_fields = ["number", "billing_reference", "customer__name"]
    ordering_fields = ["date", "due_date", "total", "balance_due", "created_at"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerInvoiceListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return CustomerInvoiceWriteSerializer
        return CustomerInvoiceDetailSerializer

    # ── Customer dropdown helper ────────────────────────────────────────────

    @action(detail=False, methods=["get"])
    def customers(self, request):
        """Return all active customers with credit risk classification.

        Used by the frontend Create Invoice dialog to populate the customer
        dropdown with risk labels without touching the general /acc-customers/
        endpoint.
        """
        qs = Customer.objects.filter(status="active").order_by("name")
        serializer = CustomerInvoiceCustomerSerializer(qs, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        invoice = serializer.save(created_by=self.request.user)
        CustomerInvoiceChatter.objects.create(
            invoice=invoice,
            author=self.request.user.get_username(),
            message=(
                f"Invoice created for {invoice.service_period or 'current period'} "
                f"by {self.request.user.get_username()}."
            ),
            time_label=timezone.now().strftime("%d %b, %H:%M"),
            message_type="system",
        )

    # ── Custom actions ─────────────────────────────────────────────────────

    @action(detail=True, methods=["patch"], url_path="status")
    def status(self, request, pk=None):
        response = super().status(request, pk)
        if response.status_code == 200:
            invoice = self.get_object()
            if invoice.status == "paid" and invoice.balance_due > 0:
                from accounting.models import CustomerReceipt, CustomerReceiptAllocation
                donor = invoice.customer  # donor.Donor FK

                # Resolve accounting.Customer by donor code (stable mapping)
                dn_code = f"DN-{donor.pk}"
                customer, _ = Customer.objects.get_or_create(
                    code=dn_code,
                    defaults={"name": donor.name or f"Donor-{donor.pk}", "email": donor.email or ""},
                )
                if customer.name != (donor.name or ""):
                    customer.name = donor.name or f"Donor-{donor.pk}"
                    customer.email = donor.email or ""
                    customer.save(update_fields=["name", "email"])

                receipt = CustomerReceipt.objects.create(
                    customer=customer,
                    donor=donor,
                    date=timezone.now().date(),
                    amount=invoice.balance_due,
                    method="",
                    reference=f"AUTO-{invoice.number}",
                    status="posted",
                    unapplied_amount=0,
                    allocation_status="fully_allocated",
                    created_by=request.user,
                )
                CustomerReceiptAllocation.objects.create(
                    receipt=receipt,
                    invoice_number=invoice.number,
                    amount=invoice.balance_due,
                )
                invoice.paid_amount = invoice.total
                invoice.save(update_fields=["paid_amount", "balance_due", "updated_at"])
        return response

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        """Mark the invoice as sent (draft → sent)."""
        invoice = self.get_object()
        if invoice.status != "draft":
            return Response(
                {"detail": "Only draft invoices can be sent."}, status=400
            )
        invoice.status = "sent"
        invoice.save(update_fields=["status", "updated_at"])
        CustomerInvoiceChatter.objects.create(
            invoice=invoice,
            author=request.user.get_username(),
            message="Invoice sent to customer.",
            time_label=timezone.now().strftime("%d %b, %H:%M"),
            message_type="system",
        )
        return Response({"detail": "Invoice sent."})

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        """Post the invoice — creates a journal entry (like vendor bill posting)."""
        invoice = self.get_object()
        if invoice.status not in ["sent", "draft"]:
            return Response({"detail": "Invoice must be sent or draft to post."}, status=400)

        from decimal import Decimal
        from accounting.models import JournalEntry, JournalItem, Account, Journal

        with transaction.atomic():
            journal = invoice.journal or Journal.objects.filter(journal_type="sales").first() or Journal.objects.first()
            if not journal:
                return Response({"detail": "No sales journal configured."}, status=400)

            total_invoice = invoice.subtotal + invoice.tax_amount

            entry = JournalEntry.objects.create(
                journal=journal,
                date=invoice.date,
                reference=f"Invoice: {invoice.number}",
                status="posted",
                total_debit=total_invoice,
                total_credit=total_invoice,
                source_document=invoice.number,
                posted_by=request.user,
                posted_at=timezone.now(),
            )

            # DEBIT: Receivable — find a receivable account
            receivable_account = (
                Account.objects.filter(code="1105").first()
                or Account.objects.filter(name__iexact="Accounts Receivable").first()
                or Account.objects.filter(
                    account_type__classification="asset",
                    account_type__liquidity_type="receivable"
                ).first()
            )
            if receivable_account:
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=receivable_account,
                    label=f"Receivable: {invoice.number}",
                    debit=total_invoice,
                    credit=0,
                )
                receivable_account.current_balance += total_invoice
                receivable_account.save(update_fields=["current_balance"])

            # CREDIT: Revenue accounts from line items
            account_totals = {}
            for line in invoice.lines.all():
                if line.account:
                    acct_id = line.account.id
                    line_total = Decimal(str(line.amount or 0))
                    account_totals[acct_id] = account_totals.get(acct_id, Decimal("0")) + line_total

            for acct_id, amount in account_totals.items():
                acct = Account.objects.filter(pk=acct_id).first()
                if acct:
                    JournalItem.objects.create(
                        journal_entry=entry,
                        account=acct,
                        label=f"Invoice: {invoice.number}",
                        debit=0,
                        credit=amount,
                    )
                    acct.current_balance -= amount
                    acct.save(update_fields=["current_balance"])

            # CREDIT: Tax amount to tax liability if applicable
            if invoice.tax_amount and invoice.tax_amount > 0:
                tax_account = (
                    Account.objects.filter(name__icontains="vat payable").first()
                    or Account.objects.filter(name__icontains="sales tax").first()
                    or Account.objects.filter(name__icontains="tax payable").first()
                    or Account.objects.filter(
                        account_type__classification="liability",
                        account_type__liquidity_type="payable"
                    ).first()
                )
                if tax_account:
                    JournalItem.objects.create(
                        journal_entry=entry,
                        account=tax_account,
                        label=f"Tax: {invoice.number}",
                        debit=0,
                        credit=invoice.tax_amount,
                    )
                    tax_account.current_balance -= invoice.tax_amount
                    tax_account.save(update_fields=["current_balance"])

            invoice.journal_entry = entry
            invoice.linked_journals = [entry.reference]
            invoice.status = "posted"
            invoice.save(update_fields=["journal_entry", "linked_journals", "status"])

        CustomerInvoiceChatter.objects.create(
            invoice=invoice,
            author=request.user.get_username(),
            message="Invoice posted to journal.",
            time_label=timezone.now().strftime("%d %b, %H:%M"),
            message_type="system",
        )

        return Response({"detail": "Invoice posted to journal."})

    @action(detail=True, methods=["post"], url_path="register-payment")
    def register_payment(self, request, pk=None):
        """Register a payment allocation against the invoice.

        Body:
            amount   (required)  — decimal payment amount
            date     (optional)  — ISO date, defaults to today
            method   (optional)  — e.g. "Bank transfer"
            reference (optional) — e.g. "RCPT-0092"
        """
        from decimal import Decimal

        invoice = self.get_object()

        raw_amount = request.data.get("amount")
        if not raw_amount:
            return Response({"detail": "amount is required."}, status=400)

        try:
            amount = Decimal(str(raw_amount))
        except (ValueError, TypeError):
            return Response({"detail": "amount must be a number."}, status=400)

        if amount > invoice.balance_due:
            return Response(
                {"detail": f"Amount exceeds remaining balance of {invoice.balance_due:.2f}."},
                status=400,
            )

        method = request.data.get("method", "")
        reference = request.data.get("reference", "")
        payment_date = request.data.get("date", timezone.now().date())

        CustomerInvoiceAllocation.objects.create(
            invoice=invoice,
            date=payment_date,
            amount=amount,
            method=method,
            reference=reference,
        )

        # Create payment journal entry (DEBIT: Bank, CREDIT: Customer Receivable)
        from accounting.models import Journal, JournalEntry, JournalItem, Account
        payment_journal = Journal.objects.filter(journal_type="bank").first() or Journal.objects.filter(journal_type="sales").first()
        if payment_journal:
            entry = JournalEntry.objects.create(
                journal=payment_journal,
                date=payment_date or timezone.now().date(),
                reference=f"Payment: {invoice.number}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                status="posted",
                total_debit=amount,
                total_credit=amount,
                posted_by=request.user,
                posted_at=timezone.now(),
            )
            bank_account = (
                payment_journal.default_debit_account
                or payment_journal.default_credit_account
                or Account.objects.filter(
                    account_type__classification="asset",
                    account_type__liquidity_type="bank_cash",
                    is_active=True,
                ).first()
                or Account.objects.filter(name__icontains="cash in hand", is_active=True).first()
                or Account.objects.filter(name__icontains="bank", is_active=True).first()
                or Account.objects.filter(code__in=["1101", "1102", "1103", "1104"], is_active=True).first()
            )
            if bank_account:
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=bank_account,
                    label=f"Payment from {invoice.customer.name if invoice.customer else ''}",
                    debit=amount,
                    credit=0,
                )
                bank_account.current_balance += amount
                bank_account.save(update_fields=["current_balance"])
            # CREDIT: Customer Receivable (reducing what customer owes)
            receivable_account = (
                Account.objects.filter(code="1105").first()
                or Account.objects.filter(name__iexact="Accounts Receivable").first()
                or Account.objects.filter(
                    account_type__classification="asset",
                    account_type__liquidity_type="receivable"
                ).first()
            )
            if receivable_account:
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=receivable_account,
                    label=f"Payment for {invoice.number}",
                    debit=0,
                    credit=amount,
                )
                receivable_account.current_balance -= amount
                receivable_account.save(update_fields=["current_balance"])

        invoice.paid_amount += amount
        if invoice.paid_amount >= invoice.total:
            invoice.status = "paid"
        else:
            invoice.status = "partial"
        invoice.save(update_fields=["paid_amount", "balance_due", "status", "updated_at"])

        CustomerInvoiceChatter.objects.create(
            invoice=invoice,
            author=request.user.get_username(),
            message=(
                f"Payment of {amount:,.2f} registered"
                + (f" via {method}" if method else "")
                + (f" (ref: {reference})" if reference else "") + "."
            ),
            time_label=timezone.now().strftime("%d %b, %H:%M"),
            message_type="payment",
        )

        serializer = CustomerInvoiceDetailSerializer(invoice)
        return Response(serializer.data)
