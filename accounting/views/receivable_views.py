from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.utils import timezone

from accounting.models import (
    Customer,
    Invoice,
    InvoiceLine,
    InvoicePayment,
    CreditNote,
)
from accounting.serializers.receivable_serializers import (
    CustomerListSerializer,
    CustomerDetailSerializer,
    InvoiceListSerializer,
    InvoiceDetailSerializer,
    InvoiceWriteSerializer,
    CreditNoteSerializer,
)
from accounting.views.status_transition_mixin import StatusTransitionMixin


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related("receivable_account").all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["name", "email", "phone"]
    ordering_fields = ["name", "total_receivable"]

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerListSerializer
        return CustomerDetailSerializer

    @action(detail=True)
    def outstanding(self, request, pk=None):
        customer = self.get_object()
        invoices = Invoice.objects.filter(
            customer=customer, status__in=["sent", "partial", "overdue"]
        ).values("id", "invoice_number", "due_date", "total_amount", "amount_paid")
        return Response(list(invoices))


class InvoiceViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related(
        "customer", "project", "cost_center"
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["customer", "status", "project", "invoice_date"]
    search_fields = ["invoice_number", "reference", "customer__name"]
    ordering_fields = ["invoice_date", "due_date", "total_amount"]

    def get_serializer_class(self):
        if self.action == "list":
            return InvoiceListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return InvoiceWriteSerializer
        return InvoiceDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def send_invoice(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status != "draft":
            return Response({"detail": "Invoice is not in draft."}, status=400)
        invoice.status = "sent"
        invoice.save(update_fields=["status"])
        return Response({"detail": "Invoice sent."})

    @action(detail=True, methods=["post"])
    def post_invoice(self, request, pk=None):
        """Post invoice to journal."""
        invoice = self.get_object()
        if invoice.status not in ["sent"]:
            return Response({"detail": "Invoice must be sent first."}, status=400)

        from accounting.models import JournalEntry, JournalItem, Journal

        with transaction.atomic():
            journal = Journal.objects.filter(journal_type="sales").first()
            if not journal:
                return Response({"detail": "No sales journal configured."}, status=400)

            entry = JournalEntry.objects.create(
                journal=journal,
                date=invoice.invoice_date,
                reference=f"Invoice: {invoice.invoice_number}",
                status="posted",
                total_debit=invoice.total_amount,
                total_credit=invoice.total_amount,
                posted_by=request.user,
                posted_at=timezone.now(),
            )

            if invoice.customer and invoice.customer.receivable_account:
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=invoice.customer.receivable_account,
                    label=f"Receivable: {invoice.customer.name}",
                    debit=invoice.total_amount,
                    credit=0,
                )
                invoice.customer.receivable_account.current_balance += (
                    invoice.total_amount
                )
                invoice.customer.receivable_account.save(
                    update_fields=["current_balance"]
                )

            for line in invoice.lines.all():
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=line.account,
                    label=line.description,
                    debit=0,
                    credit=line.subtotal,
                )
                if line.account:
                    line.account.current_balance -= line.subtotal
                    line.account.save(update_fields=["current_balance"])

            invoice.journal_entry = entry
            invoice.save(update_fields=["journal_entry"])

        return Response({"detail": "Invoice posted to journal."})

    @action(detail=True, methods=["post"])
    def register_payment(self, request, pk=None):
        invoice = self.get_object()
        amount = request.data.get("amount")
        if not amount:
            return Response({"detail": "Amount required."}, status=400)
        amount = float(amount)
        remaining = float(invoice.total_amount) - float(invoice.amount_paid)
        if amount > remaining:
            return Response(
                {"detail": f"Amount exceeds remaining {remaining}."}, status=400
            )

        with transaction.atomic():
            InvoicePayment.objects.create(
                invoice=invoice,
                amount=amount,
                date=timezone.now().date(),
                reference=request.data.get("reference", ""),
            )

            # Create payment journal entry (DEBIT: Bank, CREDIT: Customer Receivable)
            from accounting.models import Journal, JournalEntry, JournalItem
            payment_journal = Journal.objects.filter(journal_type="bank").first() or Journal.objects.filter(journal_type="sales").first()
            if payment_journal:
                entry = JournalEntry.objects.create(
                    journal=payment_journal,
                    date=timezone.now().date(),
                    reference=f"Payment: {invoice.invoice_number}",
                    status="posted",
                    total_debit=amount,
                    total_credit=amount,
                    posted_by=request.user,
                    posted_at=timezone.now(),
                )
                # DEBIT: Bank/Cash (money received)
                bank_account = payment_journal.default_debit_account
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
                # CREDIT: Customer Receivable (reducing what they owe)
                if invoice.customer and invoice.customer.receivable_account:
                    JournalItem.objects.create(
                        journal_entry=entry,
                        account=invoice.customer.receivable_account,
                        label=f"Payment for {invoice.invoice_number}",
                        debit=0,
                        credit=amount,
                    )
                    invoice.customer.receivable_account.current_balance -= amount
                    invoice.customer.receivable_account.save(update_fields=["current_balance"])

            invoice.amount_paid += amount
            if invoice.amount_paid >= invoice.total_amount:
                invoice.status = "paid"
            else:
                invoice.status = "partial"
            invoice.save(update_fields=["amount_paid", "status"])

        return Response({"detail": f"Payment of {amount} registered."})


class CreditNoteViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = CreditNote.objects.select_related("customer", "original_invoice").all()
    serializer_class = CreditNoteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["customer", "status"]
    search_fields = ["credit_note_number", "reason"]
    ordering = ["-created_at", "-id"]

    @action(detail=False, methods=["get"])
    def customers(self, request):
        """Return active customers for the dropdown."""
        customers = Customer.objects.filter(status="active").order_by("name")
        serializer = CustomerListSerializer(customers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="create-draft")
    def create_draft(self, request):
        """Create a credit note draft with auto-assigned journal."""
        from decimal import Decimal
        from accounting.models import Journal

        customer_id = request.data.get("customer")
        date = request.data.get("date")
        reason = request.data.get("reason", "")
        total_amount = Decimal(str(request.data.get("amount", 0)))
        invoice_ref = request.data.get("invoice_ref", "")
        adjustment_type = request.data.get("adjustment_type", "")
        approval_route = request.data.get("approval_route", "")
        refund_reference = request.data.get("refund_reference", "")
        notes = request.data.get("notes", "")

        if not customer_id or not date:
            return Response({"detail": "customer and date are required."}, status=400)

        # ── Resolve customer_id to an accounting.Customer ──────────────────
        # The frontend dropdown fetches from /api/donors/ (Donor PKs).
        # CreditNote.customer FK references accounting.Customer — a separate
        # table with its own auto-increment PKs that do NOT align with Donor PKs.
        # Use a stable sentinel code "DN-{donor_pk}" so every Donor maps to
        # exactly one accounting.Customer row, regardless of PK values.
        try:
            from donor.models import Donor
            donor = Donor.objects.filter(pk=customer_id).first()
        except Exception:
            donor = None

        if donor is None:
            return Response(
                {"detail": f"Customer (donor) with id {customer_id} not found."},
                status=400,
            )

        dn_code = f"DN-{donor.pk}"
        dn_name = donor.name or f"Donor-{donor.pk}"
        dn_email = donor.email or ""

        acc_customer, _ = Customer.objects.get_or_create(
            code=dn_code,
            defaults={"name": dn_name, "email": dn_email},
        )
        # Keep display name in sync if the Donor was updated
        if acc_customer.name != dn_name:
            acc_customer.name = dn_name
            acc_customer.email = dn_email
            acc_customer.save(update_fields=["name", "email"])

        journal = (
            Journal.objects.filter(journal_type="sales").first()
            or Journal.objects.first()
        )
        if not journal:
            return Response({"detail": "No journal configured."}, status=400)

        from accounting.models.transaction_customer_inv import (
            CustomerInvoice as TxnInvoice,
        )

        original_invoice = None
        txn_invoice_number = ""
        if invoice_ref:
            original_invoice = Invoice.objects.filter(
                invoice_number=invoice_ref
            ).first()
            if TxnInvoice.objects.filter(number=invoice_ref).exists():
                txn_invoice_number = invoice_ref

        stored_notes = notes
        if txn_invoice_number:
            stored_notes = f"CINV:{txn_invoice_number}|{notes}" if notes else f"CINV:{txn_invoice_number}"

        credit_note = CreditNote.objects.create(
            customer=acc_customer,
            journal=journal,
            date=date,
            reason=reason or "Credit adjustment",
            total_amount=total_amount,
            status="draft",
            original_invoice=original_invoice,
            adjustment_type=adjustment_type,
            approval_route=approval_route,
            refund_reference=refund_reference,
            application_notes=stored_notes,
            created_by=request.user,
        )

        serializer = CreditNoteSerializer(credit_note)
        return Response(serializer.data, status=201)

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        """Mark a credit note as applied and reduce the linked CustomerInvoice balance."""
        from decimal import Decimal
        from accounting.models.transaction_customer_inv import (
            CustomerInvoice as TxnInvoice,
            CustomerInvoiceChatter,
        )

        credit_note = self.get_object()
        if credit_note.status not in ["draft", "posted"]:
            return Response({"detail": "Credit note cannot be applied."}, status=400)

        invoice_ref = request.data.get("invoice_ref", "")
        if not invoice_ref and credit_note.original_invoice:
            invoice_ref = credit_note.original_invoice.invoice_number
        if not invoice_ref:
            notes = credit_note.application_notes or ""
            if notes.startswith("CINV:"):
                pipe_pos = notes.index("|") if "|" in notes else len(notes)
                invoice_ref = notes[5:pipe_pos]

        if invoice_ref:
            try:
                inv = TxnInvoice.objects.get(number=invoice_ref)
                credit_amount = Decimal(str(credit_note.total_amount))
                inv.paid_amount = (inv.paid_amount or 0) + credit_amount
                if inv.paid_amount >= inv.total:
                    inv.status = "paid"
                elif inv.paid_amount > 0:
                    inv.status = "partial"
                inv.save(update_fields=["paid_amount", "balance_due", "status", "updated_at"])
                CustomerInvoiceChatter.objects.create(
                    invoice=inv,
                    author=request.user.get_username(),
                    message=(
                        f"Credit note {credit_note.credit_note_number} "
                        f"of {credit_amount:,.2f} applied."
                    ),
                    time_label=timezone.now().strftime("%d %b, %H:%M"),
                    message_type="payment",
                )
            except TxnInvoice.DoesNotExist:
                pass

        credit_note.status = "applied"
        credit_note.save(update_fields=["status"])

        # Create credit note journal entry (CREDIT: Customer Receivable, DEBIT: Revenue/Control)
        from accounting.models import Journal, JournalEntry, JournalItem
        credit_journal = credit_note.journal or Journal.objects.filter(journal_type="sales").first()
        if credit_journal:
            entry = JournalEntry.objects.create(
                journal=credit_journal,
                date=timezone.now().date(),
                reference=f"Credit Note: {credit_note.credit_note_number}",
                status="posted",
                total_debit=credit_note.total_amount,
                total_credit=credit_note.total_amount,
                posted_by=request.user,
                posted_at=timezone.now(),
            )
            # CREDIT: Customer Receivable (reducing what they owe)
            if credit_note.customer and credit_note.customer.receivable_account:
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=credit_note.customer.receivable_account,
                    label=f"Credit note {credit_note.credit_note_number}",
                    debit=0,
                    credit=credit_note.total_amount,
                )
                credit_note.customer.receivable_account.current_balance -= credit_note.total_amount
                credit_note.customer.receivable_account.save(update_fields=["current_balance"])
            # DEBIT: Revenue/Income control account (reducing revenue)
            revenue_account = credit_journal.default_credit_account
            if revenue_account:
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=revenue_account,
                    label=f"Credit note {credit_note.credit_note_number}",
                    debit=credit_note.total_amount,
                    credit=0,
                )
                revenue_account.current_balance += credit_note.total_amount
                revenue_account.save(update_fields=["current_balance"])

        serializer = CreditNoteSerializer(credit_note)
        return Response(serializer.data)
