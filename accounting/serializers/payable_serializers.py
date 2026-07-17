from rest_framework import serializers
from accounting.models import (
    Vendor,
    Bill,
    BillLine,
    BillPayment,
    DebitNote,
    DebitNoteLine,
    VendorCredit,
)


class VendorListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            "id",
            "name",
            "code",
            "email",
            "phone",
            "payment_terms_days",
            "total_payable",
            "status",
            "created_at",
        ]


class VendorDetailSerializer(serializers.ModelSerializer):
    payable_account_name = serializers.CharField(
        source="payable_account.name", read_only=True, default=""
    )
    unpaid_bills = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = "__all__"

    def get_unpaid_bills(self, obj):
        return obj.bills.exclude(status__in=["paid", "cancelled"]).count()


class BillLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = BillLine
        fields = "__all__"


class BillPaymentSerializer(serializers.ModelSerializer):
    payment_reference = serializers.CharField(
        source="payment.reference", read_only=True
    )

    class Meta:
        model = BillPayment
        fields = "__all__"


class BillListSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    project_name = serializers.CharField(
        source="project.name", read_only=True, default=""
    )
    # Frontend alias fields
    number = serializers.CharField(source="bill_number", read_only=True)
    supplier_id = serializers.IntegerField(source="vendor.id", read_only=True)
    total = serializers.DecimalField(source="total_amount", max_digits=18, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(source="amount_due", max_digits=18, decimal_places=2, read_only=True)
    paid_amount = serializers.DecimalField(source="amount_paid", max_digits=18, decimal_places=2, read_only=True)
    supplier_invoice_ref = serializers.CharField(source="vendor_reference", read_only=True)

    class Meta:
        model = Bill
        fields = [
            "id",
            "number",
            "bill_number",
            "vendor",
            "vendor_name",
            "supplier_id",
            "vendor_reference",
            "supplier_invoice_ref",
            "bill_date",
            "due_date",
            "total_amount",
            "subtotal",
            "tax_amount",
            "amount_paid",
            "amount_due",
            "total",
            "balance_due",
            "paid_amount",
            "status",
            "status_display",
            "project_name",
            "dispute_flag",
            "match_status",
            "payment_proposal",
            "approval_route",
            "goods_receipt_ref",
            "payment_account",
            "created_at",
        ]


class BillDetailSerializer(serializers.ModelSerializer):
    vendor_detail = VendorListSerializer(source="vendor", read_only=True)
    lines = BillLineSerializer(many=True, read_only=True)
    bill_payments = BillPaymentSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    number = serializers.CharField(source="bill_number", read_only=True)
    supplier_id = serializers.IntegerField(source="vendor.id", read_only=True)
    total = serializers.DecimalField(source="total_amount", max_digits=18, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(source="amount_due", max_digits=18, decimal_places=2, read_only=True)
    paid_amount_alias = serializers.DecimalField(source="amount_paid", max_digits=18, decimal_places=2, read_only=True)
    supplier_invoice_ref = serializers.CharField(source="vendor_reference", read_only=True)
    payment_account_detail = serializers.SerializerMethodField()
    journal_entry_items = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = "__all__"

    def get_payment_account_detail(self, obj):
        if obj.payment_account:
            return {
                "id": obj.payment_account.id,
                "code": obj.payment_account.code,
                "name": obj.payment_account.name,
            }
        return None

    def get_journal_entry_items(self, obj):
        """Return journal entry line items when the bill has been posted or paid."""
        from accounting.serializers.journal_serializers import JournalItemSerializer
        if not obj.journal_entry_id:
            return []
        return JournalItemSerializer(
            obj.journal_entry.items.all(), many=True
        ).data


class BillWriteSerializer(serializers.ModelSerializer):
    lines = BillLineSerializer(many=True)

    class Meta:
        model = Bill
        exclude = ["created_by", "journal_entry"]

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        bill = Bill.objects.create(**validated_data)
        for line_data in lines_data:
            BillLine.objects.create(bill=bill, **line_data)
        return bill

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                BillLine.objects.create(bill=instance, **line_data)
        return instance


class DebitNoteLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = DebitNoteLine
        fields = "__all__"


class DebitNoteSerializer(serializers.ModelSerializer):
    lines = DebitNoteLineSerializer(many=True, read_only=True)
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    # Frontend alias fields
    number = serializers.CharField(source="debit_note_number", read_only=True)
    supplier_id = serializers.IntegerField(source="vendor.id", read_only=True)
    amount = serializers.DecimalField(
        source="total_amount", max_digits=18, decimal_places=2, read_only=True
    )
    bill_ref = serializers.SerializerMethodField()
    application_status = serializers.SerializerMethodField()

    class Meta:
        model = DebitNote
        fields = "__all__"

    def get_bill_ref(self, obj):
        if obj.original_bill:
            return obj.original_bill.bill_number
        return obj.bill_ref or ""

    def get_application_status(self, obj):
        return "applied" if obj.status == "applied" else "pending"


class VendorCreditSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)

    class Meta:
        model = VendorCredit
        fields = "__all__"


class SupplierLedgerSerializer(serializers.ModelSerializer):
    """Read-only aggregated per-vendor ledger — bills + latest payment."""

    outstanding = serializers.DecimalField(
        source="outstanding_total", max_digits=18, decimal_places=2, read_only=True, default=0
    )
    bill_count = serializers.IntegerField(source="open_bill_count", read_only=True, default=0)
    overdue_bills = serializers.IntegerField(source="overdue_bill_count", read_only=True, default=0)
    disputed_bills = serializers.IntegerField(source="disputed_bill_count", read_only=True, default=0)
    pending_approvals = serializers.IntegerField(source="pending_approval_count", read_only=True, default=0)
    hold_flags = serializers.IntegerField(source="hold_flag_count", read_only=True, default=0)
    oldest_days = serializers.SerializerMethodField()
    risk_level = serializers.SerializerMethodField()
    risk_flags = serializers.SerializerMethodField()
    bills = serializers.SerializerMethodField()
    last_payment_date = serializers.SerializerMethodField()
    payment_history_count = serializers.SerializerMethodField()
    latest_payment_id = serializers.SerializerMethodField()
    latest_payment_reference = serializers.SerializerMethodField()
    latest_payment_amount = serializers.SerializerMethodField()
    latest_payment_release_status = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = [
            "id", "name", "code", "email", "phone", "status",
            "owner",
            "outstanding", "bill_count", "overdue_bills", "disputed_bills",
            "pending_approvals", "hold_flags", "oldest_days",
            "risk_level", "risk_flags", "bills",
            "last_payment_date", "payment_history_count",
            "latest_payment_id", "latest_payment_reference",
            "latest_payment_amount", "latest_payment_release_status",
            "payment_terms_days",
        ]

    # ── internal helpers ─────────────────────────────────────────────────────

    def _vendor_bills(self, obj):
        return getattr(obj, "open_bills_prefetched", [])

    def _vendor_payments(self, obj):
        return self.context.get("payments_by_vendor", {}).get(obj.id, [])

    # ── computed fields ──────────────────────────────────────────────────────

    def get_oldest_days(self, obj):
        from django.utils import timezone
        today = timezone.now().date()
        max_days = 0
        for bill in self._vendor_bills(obj):
            if bill.due_date < today and bill.amount_due > 0:
                days = (today - bill.due_date).days
                if days > max_days:
                    max_days = days
        return max_days

    def get_risk_level(self, obj):
        if getattr(obj, "disputed_bill_count", 0) > 0 or self.get_oldest_days(obj) > 60:
            return "high"
        if getattr(obj, "overdue_bill_count", 0) > 0 or float(getattr(obj, "outstanding_total", 0) or 0) > 0:
            return "medium"
        return "low"

    def get_risk_flags(self, obj):
        flags = []
        if getattr(obj, "disputed_bill_count", 0) > 0:
            flags.append("Dispute open")
        if getattr(obj, "hold_flag_count", 0) > 0:
            flags.append("Payment on hold")
        if getattr(obj, "overdue_bill_count", 0) > 0:
            flags.append("Overdue exposure")
        return flags

    def get_bills(self, obj):
        from django.utils import timezone
        today = timezone.now().date()
        result = []
        for bill in self._vendor_bills(obj):
            if bill.amount_due <= 0:
                continue
            if bill.due_date >= today:
                overdue_days = 0
                bucket_id = "current"
            else:
                overdue_days = (today - bill.due_date).days
                if overdue_days <= 30:
                    bucket_id = "1-30"
                elif overdue_days <= 60:
                    bucket_id = "31-60"
                elif overdue_days <= 90:
                    bucket_id = "61-90"
                else:
                    bucket_id = "90-plus"
            result.append({
                "balanceDue": float(bill.amount_due),
                "overdueDays": overdue_days,
                "bucketId": bucket_id,
            })
        return result

    def get_last_payment_date(self, obj):
        payments = self._vendor_payments(obj)
        return str(payments[0].date) if payments else None

    def get_payment_history_count(self, obj):
        return len(self._vendor_payments(obj))

    def get_latest_payment_id(self, obj):
        payments = self._vendor_payments(obj)
        return payments[0].id if payments else None

    def get_latest_payment_reference(self, obj):
        payments = self._vendor_payments(obj)
        return payments[0].payment_number if payments else None

    def get_latest_payment_amount(self, obj):
        payments = self._vendor_payments(obj)
        return float(payments[0].amount) if payments else None

    def get_latest_payment_release_status(self, obj):
        payments = self._vendor_payments(obj)
        return payments[0].release_status if payments else None

    def get_owner(self, obj):
        if getattr(obj, "supplier", None):
            supplier = obj.supplier
            name = getattr(supplier, "name", "") or str(supplier)
            return name.strip()
        return ""
