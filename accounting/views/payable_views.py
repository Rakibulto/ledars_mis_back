from collections import defaultdict
from decimal import Decimal

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.db.models import Count, Sum, Q, Prefetch, Value, DecimalField as DjangoDecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounting.models import (
    Vendor,
    Bill,
    BillLine,
    BillPayment,
    DebitNote,
    VendorCredit,
    Journal,
    SupplierPayment,
)
from accounting.serializers.payable_serializers import (
    VendorListSerializer,
    VendorDetailSerializer,
    BillListSerializer,
    BillDetailSerializer,
    BillWriteSerializer,
    DebitNoteSerializer,
    VendorCreditSerializer,
    SupplierLedgerSerializer,
)
from accounting.views.status_transition_mixin import StatusTransitionMixin


def _parse_id_list(value):
    """Accept list, comma-separated string, or JSON array string of ids."""
    import json

    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [int(v) for v in value if str(v).strip().isdigit()]
    if isinstance(value, (int, float)):
        return [int(value)]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = []
            if isinstance(parsed, list):
                return [int(v) for v in parsed if str(v).strip().isdigit()]
        return [int(v) for v in stripped.split(",") if v.strip().isdigit()]
    return []


def _find_cash_at_bank_account(bank_account=None):
    from accounting.models import Account

    if bank_account and bank_account.account_id:
        linked = Account.objects.filter(
            pk=bank_account.account_id, is_active=True, is_deprecated=False
        ).first()
        if linked:
            return linked

    bank_name = ""
    if bank_account:
        bank_name = (bank_account.bank_name or bank_account.name or "").lower()

    qs = Account.objects.filter(is_active=True, is_deprecated=False)
    if bank_name:
        token = next((part for part in bank_name.split() if len(part) > 2), None)
        if token:
            from django.db.models import Q

            named = qs.filter(
                Q(name__icontains="cash at bank") & Q(name__icontains=token)
            ).first()
            if named:
                return named

    return (
        qs.filter(name__icontains="cash at bank").first()
        or qs.filter(
            account_type__classification="asset",
            account_type__liquidity_type="bank_cash",
        )
        .exclude(code="1101")
        .first()
        or qs.filter(account_type__classification="asset", code__startswith="110")
        .exclude(code="1101")
        .first()
    )


def _find_cash_in_hand_account():
    from accounting.models import Account

    return (
        Account.objects.filter(code="1101", is_active=True, is_deprecated=False).first()
        or Account.objects.filter(
            name__iexact="cash in hand", is_active=True, is_deprecated=False
        ).first()
        or Account.objects.filter(
            name__icontains="cash in hand", is_active=True, is_deprecated=False
        ).first()
    )


def _resolve_bill_payment_account(
    *,
    payment_account_id=None,
    source_bank_account=None,
    source_cheque=None,
):
    from accounting.models import Account

    if payment_account_id:
        explicit = Account.objects.filter(
            pk=payment_account_id, is_active=True, is_deprecated=False
        ).first()
        if explicit:
            return explicit

    treasury_bank = source_bank_account
    if not treasury_bank and source_cheque:
        treasury_bank = source_cheque.bank_account

    if treasury_bank or source_cheque:
        cash_at_bank = _find_cash_at_bank_account(treasury_bank)
        if cash_at_bank:
            return cash_at_bank

    return _find_cash_in_hand_account()


class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.select_related("payable_account").all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["name", "email", "phone"]
    ordering_fields = ["name", "total_payable", "created_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return VendorListSerializer
        return VendorDetailSerializer

    @action(detail=True)
    def outstanding(self, request, pk=None):
        vendor = self.get_object()
        bills = Bill.objects.filter(
            vendor=vendor, status__in=["approved", "partial"]
        ).values("id", "bill_number", "due_date", "total_amount", "amount_paid")
        return Response(list(bills))


class BillViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = Bill.objects.select_related(
        "vendor",
        "project",
        "cost_center",
        "payment_account",
        "work_order",
        "primary_grn",
        "source_bank_account",
        "source_cheque",
    ).prefetch_related("grns").all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["vendor", "status", "project", "bill_date"]
    search_fields = ["bill_number", "reference", "vendor__name"]
    ordering_fields = ["bill_date", "due_date", "total_amount"]

    def get_serializer_class(self):
        if self.action == "list":
            return BillListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return BillWriteSerializer
        return BillDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"])
    def vendors(self, request):
        """Return active vendors for the supplier dropdown."""
        vendors = Vendor.objects.filter(status="active").order_by("name")
        serializer = VendorListSerializer(vendors, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="create-draft")
    def create_draft(self, request):
        """Create a bill draft from the workspace UI with auto-assigned journal and line."""
        from decimal import Decimal
        from accounting.models import Journal, Account, CostCenter, Currency, FiscalPeriod, AnalyticAccount, BankAccount, Check
        from procurement.models import WorkOrder, GoodsReceiptNote
        from projects.models import Project

        vendor_id = request.data.get("vendor")
        bill_date = request.data.get("date") or request.data.get("bill_date")
        due_date = request.data.get("due_date")
        description = request.data.get("description", "Draft bill line")
        amount = Decimal(str(request.data.get("amount") or request.data.get("total_amount") or 0))
        vendor_reference = request.data.get("supplierInvoiceRef") or request.data.get("vendor_reference", "")
        goods_receipt_ref = request.data.get("goodsReceiptRef") or request.data.get("goods_receipt_ref", "")
        match_status = request.data.get("match_status", "Awaiting receipt")
        dispute_flag = bool(request.data.get("dispute_flag", False))
        payment_proposal = request.data.get("payment_proposal", "")
        approval_route = request.data.get("approval_route", "")
        notes = request.data.get("notes", "")
        requested_total_amount = amount
        requested_tax_amount = Decimal(str(request.data.get("tax_amount", 0) or 0))

        # New optional FK fields
        journal_id = request.data.get("journal")
        project_id = request.data.get("project")
        cost_center_id = request.data.get("cost_center")
        currency_id = request.data.get("currency")
        fiscal_period_id = request.data.get("fiscal_period")
        payment_account_id = request.data.get("payment_account")
        work_order_id = request.data.get("work_order") or request.data.get("workOrder")
        grn_ids = (
            _parse_id_list(request.data.get("grns"))
            or _parse_id_list(request.data.get("grn_ids"))
            or _parse_id_list(request.data.get("grnSelections"))
        )
        source_bank_account_id = (
            request.data.get("source_bank_account")
            or request.data.get("bank_account")
            or request.data.get("bankAccountId")
        )
        source_cheque_id = (
            request.data.get("source_cheque")
            or request.data.get("cheque")
            or request.data.get("chequeId")
        )
        invoice_file = request.FILES.get("invoice_file")
        mushuk_file = request.FILES.get("mushuk_file")
        lines_data = request.data.get("lines")
        if isinstance(lines_data, str):
            import json
            try:
                lines_data = json.loads(lines_data)
            except json.JSONDecodeError:
                lines_data = None

        if not vendor_id or not bill_date:
            return Response({"detail": "vendor and date are required."}, status=400)

        # ── Resolve vendor_id to an accounting.Vendor ──────────────────────
        try:
            from vendorportal.models.models import VendorProfile
            vp = VendorProfile.objects.filter(pk=vendor_id).first()
        except Exception:
            vp = None

        if vp is None:
            return Response(
                {"detail": f"Vendor with id {vendor_id} not found."},
                status=400,
            )

        vp_code = f"VP-{vp.pk}"
        vp_name = vp.name or vp.legal_name or f"Vendor-{vp.pk}"
        vp_email = getattr(vp, "email", "") or ""

        acc_vendor, _ = Vendor.objects.get_or_create(
            code=vp_code,
            defaults={"name": vp_name, "email": vp_email},
        )
        # Ensure vendor has a payable_account (Accounts Payable — code 2101)
        if not acc_vendor.payable_account:
            default_payable = (
                Account.objects.filter(code="2101").first()
                or Account.objects.filter(account_type__classification="liability", account_type__liquidity_type="payable").first()
            )
            if default_payable:
                acc_vendor.payable_account = default_payable
        if acc_vendor.name != vp_name:
            acc_vendor.name = vp_name
            acc_vendor.email = vp_email
        acc_vendor.save()

        # Resolve journal
        journal = None
        if journal_id:
            journal = Journal.objects.filter(pk=journal_id).first()
        if not journal:
            journal = (
                Journal.objects.filter(journal_type="purchase").first()
                or Journal.objects.first()
            )
        if not journal:
            return Response({"detail": "No purchase journal configured."}, status=400)

        # Resolve optional FK fields
        project = Project.objects.filter(pk=project_id).first() if project_id else None
        cost_center = CostCenter.objects.filter(pk=cost_center_id).first() if cost_center_id else None
        currency = Currency.objects.filter(pk=currency_id).first() if currency_id else None
        fiscal_period = FiscalPeriod.objects.filter(pk=fiscal_period_id).first() if fiscal_period_id else None

        work_order = WorkOrder.objects.filter(pk=work_order_id).first() if work_order_id else None
        grn_records = list(GoodsReceiptNote.objects.filter(pk__in=grn_ids)) if grn_ids else []
        primary_grn = grn_records[0] if grn_records else None
        if not work_order and primary_grn and primary_grn.work_order_id:
            work_order = primary_grn.work_order
        if not goods_receipt_ref and grn_records:
            goods_receipt_ref = ", ".join(
                grn.grn_number for grn in grn_records if grn.grn_number
            )

        source_bank_account = (
            BankAccount.objects.filter(pk=source_bank_account_id).first()
            if source_bank_account_id
            else None
        )
        source_cheque = (
            Check.objects.select_related("bank_account")
            .filter(pk=source_cheque_id)
            .first()
            if source_cheque_id
            else None
        )
        if source_bank_account and source_cheque:
            source_cheque = None

        # Resolve payment account (Cash/Bank COA for the payment side)
        payment_account = _resolve_bill_payment_account(
            payment_account_id=payment_account_id,
            source_bank_account=source_bank_account,
            source_cheque=source_cheque,
        )
        if not payment_account:
            # Legacy fallback when chart of accounts is sparse
            payment_account = (
                Account.objects.filter(
                    account_type__classification="asset",
                    account_type__liquidity_type="bank_cash",
                    is_active=True,
                ).first()
                or Account.objects.filter(
                    account_type__classification="asset",
                    code__startswith="10",
                    is_active=True,
                ).first()
                or Account.objects.filter(
                    account_type__classification="asset",
                    code__startswith="11",
                    is_active=True,
                ).first()
            )

        with transaction.atomic():
            bill = Bill.objects.create(
                vendor=acc_vendor,
                journal=journal,
                bill_date=bill_date,
                due_date=due_date,
                vendor_reference=vendor_reference,
                goods_receipt_ref=goods_receipt_ref,
                match_status=match_status,
                dispute_flag=dispute_flag,
                payment_proposal=payment_proposal,
                approval_route=approval_route,
                subtotal=amount,
                tax_amount=requested_tax_amount,
                total_amount=amount,
                amount_paid=Decimal("0"),
                amount_due=amount,
                status="draft",
                notes=notes,
                created_by=request.user,
                project=project,
                cost_center=cost_center,
                currency=currency,
                fiscal_period=fiscal_period,
                payment_account=payment_account,
                work_order=work_order,
                primary_grn=primary_grn,
                source_bank_account=source_bank_account,
                source_cheque=source_cheque,
                invoice_file=invoice_file,
                mushuk_file=mushuk_file,
            )

            if grn_records:
                bill.grns.set(grn_records)

            if lines_data and isinstance(lines_data, list):
                for line in lines_data:
                    line_account_id = line.get("account")
                    line_account = Account.objects.filter(pk=line_account_id).first() if line_account_id else None
                    if not line_account:
                        # Find the first general expense account (not tax/VAT adjustment)
                        line_account = (
                            Account.objects.filter(
                                account_type__classification="expense",
                                name__icontains="expense"
                            ).exclude(name__icontains="vat").exclude(name__icontains="tax").first()
                            or Account.objects.filter(account_type__classification="expense").first()
                        )
                    line_analytic_account_id = line.get("analytic_account")
                    line_cost_center_id = line.get("cost_center")
                    line_qty = Decimal(str(line.get("quantity", 1)))
                    line_price = Decimal(str(line.get("unit_price", 0)))
                    line_subtotal = line_qty * line_price
                    line_tax_amount = Decimal(str(line.get("tax_amount", 0) or 0))

                    BillLine.objects.create(
                        bill=bill,
                        account=line_account,
                        description=line.get("description", description),
                        quantity=line_qty,
                        unit_price=line_price,
                        subtotal=line_subtotal,
                        tax_amount=line_tax_amount,
                        analytic_account=AnalyticAccount.objects.filter(pk=line_analytic_account_id).first() if line_analytic_account_id else None,
                    )
            else:
                default_account = (
                    Account.objects.filter(
                        account_type__classification="expense",
                        name__icontains="expense"
                    ).exclude(name__icontains="vat").exclude(name__icontains="tax").first()
                    or Account.objects.filter(account_type__classification="expense").first()
                )
                if default_account:
                    BillLine.objects.create(
                        bill=bill,
                        account=default_account,
                        description=description,
                        quantity=1,
                        unit_price=amount,
                        subtotal=amount,
                    )

            # Recalculate totals from lines if any exist
            if lines_data and isinstance(lines_data, list) and len(lines_data) >= 1:
                all_lines = bill.lines.all()
                new_subtotal = sum(l.subtotal for l in all_lines)
                bill.subtotal = new_subtotal
                # Preserve tax from the original request; if none sent, derive it
                if requested_tax_amount > 0:
                    bill.tax_amount = requested_tax_amount
                elif requested_total_amount > new_subtotal:
                    bill.tax_amount = requested_total_amount - new_subtotal
                bill.total_amount = new_subtotal + bill.tax_amount
                bill.amount_due = bill.total_amount
                bill.save(update_fields=["subtotal", "tax_amount", "total_amount", "amount_due"])

        serializer = BillDetailSerializer(bill)
        return Response(serializer.data, status=201)

    @action(detail=False, methods=["get"])
    def unpaid(self, request):
        """Return bills with outstanding balance for the payables workspace."""
        today = timezone.now().date()
        bills = self.get_queryset().filter(
            amount_due__gt=0,
        ).exclude(
            status__in=["paid", "cancelled"]
        ).prefetch_related(
            "lines", "bill_payments__payment"
        ).order_by("due_date")

        from accounting.serializers.payable_serializers import BillDetailSerializer

        page = self.paginate_queryset(bills)
        if page is not None:
            serializer = BillDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = BillDetailSerializer(bills, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        bill = self.get_object()
        if bill.status != "pending":
            return Response({"detail": "Bill must be pending approval."}, status=400)
        bill.status = "approved"
        bill.save(update_fields=["status", "updated_at"])
        return Response({"detail": "Bill approved."})

    @action(detail=True, methods=["post"], url_path="post-bill")
    def post_bill(self, request, pk=None):
        """Post bill to journal - creates a journal entry."""
        bill = self.get_object()
        if bill.status not in ["approved", "overdue"]:
            return Response({"detail": "Bill must be approved first."}, status=400)

        from accounting.models import JournalEntry, JournalItem, Journal, Account

        with transaction.atomic():
            # Use bill's selected journal, fallback to first purchase journal
            journal = bill.journal or Journal.objects.filter(journal_type="purchase").first()
            if not journal:
                return Response(
                    {"detail": "No purchase journal configured."}, status=400
                )

            entry = JournalEntry.objects.create(
                journal=journal,
                date=bill.bill_date,
                reference=f"Bill: {bill.bill_number}",
                status="posted",
                total_debit=bill.total_amount,
                total_credit=bill.total_amount,
                posted_by=request.user,
                posted_at=timezone.now(),
            )

            for line in bill.lines.all():
                # DR: Expense account (subtotal)
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=line.account,
                    label=line.description,
                    debit=line.subtotal,
                    credit=0,
                    analytic_account=line.analytic_account,
                    tax=line.tax,
                    cost_center=getattr(line, 'cost_center', None),
                )
                if line.account:
                    line.account.current_balance += line.subtotal
                    line.account.save(update_fields=["current_balance"])

                # DR: Tax account (tax_amount) — balances the JE when tax exists
                if line.tax_amount:
                    tax_account = None
                    if line.tax and line.tax.account:
                        tax_account = line.tax.account
                    else:
                        # Fallback: find Input VAT account (code 7001) or first VAT/tax asset account
                        tax_account = (
                            Account.objects.filter(code="7001").first()
                            or Account.objects.filter(name__icontains="input vat").first()
                            or Account.objects.filter(name__icontains="vat receivable").first()
                        )
                    if tax_account:
                        JournalItem.objects.create(
                            journal_entry=entry,
                            account=tax_account,
                            label=f"Tax: {line.tax.name if line.tax else 'VAT'}",
                            debit=line.tax_amount,
                            credit=0,
                            tax=line.tax,
                        )
                        tax_account.current_balance += line.tax_amount
                        tax_account.save(update_fields=["current_balance"])

            if bill.vendor and bill.vendor.payable_account:
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=bill.vendor.payable_account,
                    label=f"Payable: {bill.vendor.name}",
                    debit=0,
                    credit=bill.total_amount,
                )
                bill.vendor.payable_account.current_balance -= bill.total_amount
                bill.vendor.payable_account.save(update_fields=["current_balance"])
            elif bill.vendor:
                # Fallback: find the Accounts Payable account (code 2101 or first payable-type)
                fallback_payable = (
                    Account.objects.filter(code="2101").first()
                    or Account.objects.filter(account_type__classification="liability", account_type__liquidity_type="payable").first()
                    or Account.objects.filter(account_type__classification="liability").first()
                )
                if fallback_payable:
                    JournalItem.objects.create(
                        journal_entry=entry,
                        account=fallback_payable,
                        label=f"Payable: {bill.vendor.name}",
                        debit=0,
                        credit=bill.total_amount,
                    )
                    fallback_payable.current_balance -= bill.total_amount
                    fallback_payable.save(update_fields=["current_balance"])

            bill.journal_entry = entry
            bill.status = "posted"
            bill.save(update_fields=["journal_entry", "status"])

        return Response({"detail": "Bill posted to journal."})

    @action(detail=True, methods=["post"], url_path="register-payment")
    def register_payment(self, request, pk=None):
        bill = self.get_object()
        raw_amount = request.data.get("amount")
        if not raw_amount:
            return Response({"detail": "Amount required."}, status=400)

        from decimal import Decimal
        from accounting.models import Payment, PaymentMethod, Journal, SupplierPayment

        amount = Decimal(str(raw_amount))
        remaining = bill.total_amount - bill.amount_paid
        if amount > remaining:
            return Response(
                {"detail": f"Amount exceeds remaining {remaining}."}, status=400
            )

        with transaction.atomic():
            payment_method = PaymentMethod.objects.first()
            if not payment_method:
                return Response({"detail": "No payment method configured. Please add one in Configuration."}, status=400)
            journal = bill.journal or Journal.objects.filter(journal_type="bank").first() or Journal.objects.first()
            payment = Payment.objects.create(
                reference=f"PMT-{bill.bill_number or bill.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                direction="outbound",
                payment_method=payment_method,
                journal=journal,
                amount=amount,
                date=timezone.now().date(),
                partner_type="vendor",
                partner_id=bill.vendor_id,
                partner_name=bill.vendor.name if bill.vendor else "",
                status="posted",
                created_by=request.user,
                memo=f"Payment for bill {bill.bill_number}",
            )
            BillPayment.objects.create(
                bill=bill,
                payment=payment,
                amount=amount,
                date=timezone.now().date(),
            )
            SupplierPayment.objects.create(
                vendor=bill.vendor,
                date=timezone.now().date(),
                method=payment_method.name if payment_method else "",
                amount=amount,
                status="posted",
                release_status="released",
                bill_refs=[bill.bill_number],
                created_by=request.user,
            )

            # Create payment journal entry (DEBIT: Vendor Payable, CREDIT: Bank)
            from accounting.models import JournalEntry, JournalItem, Account
            payment_journal = Journal.objects.filter(journal_type="bank").first() or journal
            if payment_journal:
                entry = JournalEntry.objects.create(
                    journal=payment_journal,
                    date=timezone.now().date(),
                    reference=f"Payment: {bill.bill_number}",
                    status="posted",
                    total_debit=amount,
                    total_credit=amount,
                    posted_by=request.user,
                    posted_at=timezone.now(),
                )
                # DEBIT: Vendor Payable (reducing what you owe)
                if bill.vendor and bill.vendor.payable_account:
                    JournalItem.objects.create(
                        journal_entry=entry,
                        account=bill.vendor.payable_account,
                        label=f"Payment for {bill.bill_number}",
                        debit=amount,
                        credit=0,
                    )
                    bill.vendor.payable_account.current_balance += amount
                    bill.vendor.payable_account.save(update_fields=["current_balance"])
                elif bill.vendor:
                    fallback_payable = (
                        Account.objects.filter(code="2101").first()
                        or Account.objects.filter(account_type__classification="liability", account_type__liquidity_type="payable").first()
                        or Account.objects.filter(account_type__classification="liability").first()
                    )
                    if fallback_payable:
                        JournalItem.objects.create(
                            journal_entry=entry,
                            account=fallback_payable,
                            label=f"Payment for {bill.bill_number}",
                            debit=amount,
                            credit=0,
                        )
                        fallback_payable.current_balance += amount
                        fallback_payable.save(update_fields=["current_balance"])
                # CREDIT: Use the same account from the bill line (mirrors the posting JE)
                bill_line_account = bill.lines.first().account if bill.lines.exists() else None
                if bill_line_account:
                    JournalItem.objects.create(
                        journal_entry=entry,
                        account=bill_line_account,
                        label=f"Payment for {bill.bill_number}",
                        debit=0,
                        credit=amount,
                    )
                    bill_line_account.current_balance -= amount
                    bill_line_account.save(update_fields=["current_balance"])

            bill.amount_paid += amount
            if bill.amount_paid >= bill.total_amount:
                bill.status = "paid"
            else:
                bill.status = "partial"
            bill.save(update_fields=["amount_paid", "status", "amount_due"])

        return Response({"detail": f"Payment of {amount} registered."})


class DebitNoteViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = DebitNote.objects.select_related("vendor", "original_bill").all()
    serializer_class = DebitNoteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["vendor", "status"]
    search_fields = ["debit_note_number", "reason"]

    @action(detail=False, methods=["get"])
    def vendors(self, request):
        """Return active vendors for the supplier dropdown."""
        vendors = Vendor.objects.filter(status="active").order_by("name")
        serializer = VendorListSerializer(vendors, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="create-draft")
    def create_draft(self, request):
        """Create a debit note draft from the workspace UI."""
        from decimal import Decimal

        vendor_id = request.data.get("vendor")
        date = request.data.get("date")
        reason = request.data.get("reason", "")
        total_amount = Decimal(str(request.data.get("amount", 0)))
        bill_ref = request.data.get("bill_ref", "")
        adjustment_type = request.data.get("adjustment_type", "")
        approval_route = request.data.get("approval_route", "")
        dispute_reference = request.data.get("dispute_reference", "")
        notes = request.data.get("notes", "")

        if not vendor_id or not date:
            return Response({"detail": "vendor and date are required."}, status=400)

        # Resolve vendor_id to an accounting.Vendor (frontend sends VendorProfile PK)
        try:
            from vendorportal.models.models import VendorProfile
            vp = VendorProfile.objects.filter(pk=vendor_id).first()
        except Exception:
            vp = None

        if vp is None:
            return Response(
                {"detail": f"Vendor with id {vendor_id} not found."},
                status=400,
            )

        vp_code = f"VP-{vp.pk}"
        vp_name = vp.name or vp.legal_name or f"Vendor-{vp.pk}"
        vp_email = getattr(vp, "email", "") or ""

        acc_vendor, _ = Vendor.objects.get_or_create(
            code=vp_code,
            defaults={"name": vp_name, "email": vp_email},
        )
        if acc_vendor.name != vp_name:
            acc_vendor.name = vp_name
            acc_vendor.email = vp_email
            acc_vendor.save(update_fields=["name", "email"])

        journal = (
            Journal.objects.filter(journal_type="purchase").first()
            or Journal.objects.first()
        )
        if not journal:
            return Response({"detail": "No purchase journal configured."}, status=400)

        original_bill = None
        if bill_ref:
            original_bill = Bill.objects.filter(bill_number=bill_ref).first()

        debit_note = DebitNote.objects.create(
            vendor=acc_vendor,
            journal=journal,
            date=date,
            reason=reason or "Debit adjustment",
            total_amount=total_amount,
            status="draft",
            original_bill=original_bill,
            bill_ref=bill_ref,
            adjustment_type=adjustment_type,
            approval_route=approval_route,
            dispute_reference=dispute_reference,
            application_notes=notes,
            created_by=request.user,
        )
        serializer = DebitNoteSerializer(debit_note)
        return Response(serializer.data, status=201)

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        """Apply a debit note: reduce the bill amount, create JournalEntry, update VendorCredit."""
        debit_note = self.get_object()
        if debit_note.status not in ["draft", "posted"]:
            return Response({"detail": "Debit note cannot be applied."}, status=400)
        if not debit_note.original_bill:
            return Response({"detail": "Debit note must reference an original bill to apply."}, status=400)

        from accounting.models import JournalEntry, JournalItem, Account

        bill = debit_note.original_bill
        amount = debit_note.total_amount

        with transaction.atomic():
            entry = JournalEntry.objects.create(
                journal=debit_note.journal,
                date=debit_note.date,
                reference=f"Debit Note: {debit_note.debit_note_number}",
                status="posted",
                total_debit=amount,
                total_credit=amount,
                posted_by=request.user,
                posted_at=timezone.now(),
            )

            if bill.vendor and bill.vendor.payable_account:
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=bill.vendor.payable_account,
                    label=f"AP reduction: {debit_note.reason[:100]}",
                    debit=amount,
                    credit=0,
                )
                bill.vendor.payable_account.current_balance += amount
                bill.vendor.payable_account.save(update_fields=["current_balance"])

            credit_account = bill.lines.first().account if bill.lines.exists() else (
                Account.objects.filter(account_type__classification="expense").first()
                or Account.objects.first()
            )
            if credit_account:
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=credit_account,
                    label=debit_note.reason[:100],
                    debit=0,
                    credit=amount,
                )
                credit_account.current_balance -= amount
                credit_account.save(update_fields=["current_balance"])

            bill.total_amount -= amount
            if bill.total_amount < 0:
                bill.total_amount = 0
            bill.save(update_fields=["total_amount", "amount_due"])

            vendor_credit, created = VendorCredit.objects.get_or_create(
                vendor=bill.vendor,
                defaults={"credit_balance": amount},
            )
            if not created:
                vendor_credit.credit_balance += amount
                vendor_credit.save(update_fields=["credit_balance"])

            debit_note.journal_entry = entry
            debit_note.status = "applied"
            debit_note.save(update_fields=["journal_entry", "status"])

        serializer = DebitNoteSerializer(debit_note)
        return Response(serializer.data)


class VendorCreditViewSet(viewsets.ModelViewSet):
    queryset = VendorCredit.objects.select_related("vendor").all()
    serializer_class = VendorCreditSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["vendor"]

   
class SupplierLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Aggregated read-only supplier ledger.
    Returns one row per Vendor with live bill counts, aging exposure,
    and the latest SupplierPayment linked by the FK on SupplierPayment.vendor.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = SupplierLedgerSerializer
    filter_backends = [SearchFilter]
    search_fields = ["name", "email", "code"]

    def get_queryset(self):
        open_statuses = ["approved", "partial", "posted", "overdue"]
        today = timezone.now().date()
        return (
            Vendor.objects
            .select_related("payable_account", "currency", "supplier")
            .prefetch_related(
                Prefetch(
                    "bills",
                    queryset=Bill.objects.filter(status__in=open_statuses),
                    to_attr="open_bills_prefetched",
                )
            )
            .annotate(
                outstanding_total=Coalesce(
                    Sum(
                        "bills__amount_due",
                        filter=Q(bills__status__in=open_statuses),
                    ),
                    Value(Decimal("0")),
                    output_field=DjangoDecimalField(max_digits=18, decimal_places=2),
                ),
                open_bill_count=Count(
                    "bills", filter=Q(bills__status__in=open_statuses)
                ),
                overdue_bill_count=Count(
                    "bills",
                    filter=Q(bills__status__in=open_statuses, bills__due_date__lt=today),
                ),
                disputed_bill_count=Count(
                    "bills",
                    filter=Q(bills__status__in=open_statuses, bills__dispute_flag=True),
                ),
                pending_approval_count=Count(
                    "bills", filter=Q(bills__status="pending")
                ),
                hold_flag_count=Count(
                    "bills",
                    filter=Q(
                        bills__status__in=open_statuses,
                        bills__payment_proposal__icontains="hold",
                    ),
                ),
            )
            .order_by("name")
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        # Batch-fetch all supplier payments — one query, no N+1
        vendor_ids = list(queryset.values_list("id", flat=True))
        all_payments = SupplierPayment.objects.filter(
            vendor_id__in=vendor_ids
        ).order_by("vendor_id", "-date", "-id")
        payments_by_vendor = defaultdict(list)
        for p in all_payments:
            payments_by_vendor[p.vendor_id].append(p)
        serializer = self.get_serializer(
            queryset,
            many=True,
            context={**self.get_serializer_context(), "payments_by_vendor": payments_by_vendor},
        )
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        vendor_payments = list(
            SupplierPayment.objects.filter(vendor_id=instance.id).order_by("-date", "-id")
        )
        context = {
            **self.get_serializer_context(),
            "payments_by_vendor": {instance.id: vendor_payments},
        }
        serializer = self.get_serializer(instance, context=context)
        return Response(serializer.data)
