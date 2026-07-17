from rest_framework import serializers
from accounting.models import (
    Customer,
    Invoice,
    InvoiceLine,
    InvoicePayment,
    CreditNote,
    CreditNoteLine,
)


class CustomerListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "code",
            "email",
            "phone",
            "payment_terms_days",
            "total_receivable",
            "status",
            "created_at",
        ]


class CustomerDetailSerializer(serializers.ModelSerializer):
    receivable_account_name = serializers.CharField(
        source="receivable_account.name", read_only=True, default=""
    )
    unpaid_invoices = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = "__all__"

    def get_unpaid_invoices(self, obj):
        return obj.invoices.exclude(status__in=["paid", "cancelled"]).count()


class InvoiceLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = InvoiceLine
        fields = "__all__"


class InvoicePaymentSerializer(serializers.ModelSerializer):
    payment_reference = serializers.CharField(
        source="payment.reference", read_only=True
    )

    class Meta:
        model = InvoicePayment
        fields = "__all__"


class InvoiceListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    project_name = serializers.CharField(
        source="project.name", read_only=True, default=""
    )

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "customer",
            "customer_name",
            "invoice_date",
            "due_date",
            "total_amount",
            "subtotal",
            "tax_amount",
            "amount_paid",
            "amount_due",
            "status",
            "status_display",
            "project_name",
            "created_at",
        ]


class InvoiceDetailSerializer(serializers.ModelSerializer):
    customer_detail = CustomerListSerializer(source="customer", read_only=True)
    lines = InvoiceLineSerializer(many=True, read_only=True)
    invoice_payments = InvoicePaymentSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Invoice
        fields = "__all__"


class InvoiceWriteSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True)

    class Meta:
        model = Invoice
        exclude = ["created_by", "journal_entry"]

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        invoice = Invoice.objects.create(**validated_data)
        for line_data in lines_data:
            InvoiceLine.objects.create(invoice=invoice, **line_data)
        return invoice

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                InvoiceLine.objects.create(invoice=instance, **line_data)
        return instance


class CreditNoteLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditNoteLine
        fields = "__all__"


class CreditNoteSerializer(serializers.ModelSerializer):
    lines = CreditNoteLineSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    # Frontend alias fields
    number = serializers.CharField(source="credit_note_number", read_only=True)
    customer_id = serializers.IntegerField(source="customer.id", read_only=True)
    amount = serializers.DecimalField(source="total_amount", max_digits=18, decimal_places=2, read_only=True)
    invoice_ref = serializers.SerializerMethodField()
    application_status = serializers.SerializerMethodField()

    class Meta:
        model = CreditNote
        fields = "__all__"

    def get_invoice_ref(self, obj):
        if obj.original_invoice:
            return obj.original_invoice.invoice_number
        notes = obj.application_notes or ""
        if notes.startswith("CINV:"):
            pipe_pos = notes.index("|") if "|" in notes else len(notes)
            return notes[5:pipe_pos]
        return ""

    def get_application_status(self, obj):
        if obj.status == "applied":
            return "applied"
        if obj.status == "draft":
            return "pending"
        return obj.status

    def update(self, instance, validated_data):
        notes = validated_data.pop("application_notes", None)
        if notes is not None:
            existing = instance.application_notes or ""
            if existing.startswith("CINV:"):
                pipe_pos = existing.index("|") if "|" in existing else len(existing)
                prefix = existing[:pipe_pos]
                notes = f"{prefix}|{notes}" if notes else existing
            instance.application_notes = notes
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
