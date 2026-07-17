from decimal import Decimal

from rest_framework import serializers

from donor.models import Donor
from authentication.models import User
from accounting.models.transaction_customer_inv import (
    CustomerInvoice,
    CustomerInvoiceAllocation,
    CustomerInvoiceAttachment,
    CustomerInvoiceChatter,
    CustomerInvoiceLine,
)


# ── Sub-resource serializers ───────────────────────────────────────────────────


class CustomerInvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerInvoiceLine
        fields = ["id", "description", "quantity", "unit_price", "amount", "analytic", "account", "analytic_account", "cost_center"]
        read_only_fields = ["id", "amount"]


class CustomerInvoiceAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerInvoiceAllocation
        fields = ["id", "date", "amount", "method", "reference"]
        read_only_fields = ["id"]


class CustomerInvoiceAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerInvoiceAttachment
        fields = ["id", "name", "file_type", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


class CustomerInvoiceChatterSerializer(serializers.ModelSerializer):
    # `time` is the display alias the frontend expects
    time = serializers.CharField(source="time_label", read_only=True)

    class Meta:
        model = CustomerInvoiceChatter
        fields = ["id", "author", "message", "time", "time_label", "message_type", "created_at"]
        read_only_fields = ["id", "created_at"]


# ── Customer inline serializer (used inside the invoice response) ─────────────


class CustomerInvoiceCustomerSerializer(serializers.ModelSerializer):
    """Lightweight donor info returned nested inside the invoice response.

    Donors are used as customers for invoicing. `credit_limit` is not a
    Donor field so it is exposed as zero; `risk` defaults to 'medium'.
    """

    credit_limit = serializers.SerializerMethodField()
    risk = serializers.SerializerMethodField()

    class Meta:
        model = Donor
        fields = ["id", "name", "email", "credit_limit", "risk", "status"]

    def get_credit_limit(self, obj):
        return 0

    def get_risk(self, obj):
        return "medium"


# ── List serializer (returned for the /list/ action) ──────────────────────────


class CustomerInvoiceListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    customer_risk = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    dunning_display = serializers.CharField(
        source="get_dunning_stage_display", read_only=True
    )

    class Meta:
        model = CustomerInvoice
        fields = [
            "id",
            "number",
            "customer",
            "customer_name",
            "customer_email",
            "customer_risk",
            "date",
            "due_date",
            "status",
            "status_display",
            "dunning_stage",
            "dunning_display",
            "recurring",
            "recurring_label",
            "payment_terms",
            "service_period",
            "billing_owner",
            "billing_reference",
            "subtotal",
            "tax_amount",
            "total",
            "paid_amount",
            "balance_due",
            "credit_warning",
            "promise_to_pay",
            "linked_journals",
            "created_at",
        ]

    def get_customer_risk(self, obj):
        return "medium"


class CustomerInvoiceDetailSerializer(serializers.ModelSerializer):
    customer_detail = CustomerInvoiceCustomerSerializer(source="customer", read_only=True)
    lines = CustomerInvoiceLineSerializer(many=True, read_only=True)
    allocations = CustomerInvoiceAllocationSerializer(many=True, read_only=True)
    attachments = CustomerInvoiceAttachmentSerializer(many=True, read_only=True)
    chatter = CustomerInvoiceChatterSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    dunning_display = serializers.CharField(
        source="get_dunning_stage_display", read_only=True
    )
    customer_risk = serializers.SerializerMethodField()

    class Meta:
        model = CustomerInvoice
        fields = "__all__"

    def get_customer_risk(self, obj):
        return "medium"


# ── Write serializer (create / update) ────────────────────────────────────────


class CustomerInvoiceLineWriteSerializer(serializers.Serializer):
    """Single line-item shape accepted by the Create Invoice dialog."""

    description = serializers.CharField(max_length=500)
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal("1")
    )
    unit_price = serializers.DecimalField(max_digits=18, decimal_places=2)
    analytic = serializers.CharField(
        max_length=200, required=False, default="", allow_blank=True
    )
    account = serializers.IntegerField(required=False, allow_null=True)
    analytic_account = serializers.IntegerField(required=False, allow_null=True)
    cost_center = serializers.IntegerField(required=False, allow_null=True)


class CustomerInvoiceWriteSerializer(serializers.ModelSerializer):
    """Accepts the full Create Invoice dialog payload including multiple line items."""

    lines = CustomerInvoiceLineWriteSerializer(many=True, write_only=True, required=True)
    tax_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, write_only=True, required=False, default=0
    )

    class Meta:
        model = CustomerInvoice
        fields = [
            "customer",
            "date",
            "due_date",
            "status",
            "dunning_stage",
            "promise_to_pay",
            "credit_warning",
            "payment_terms",
            "service_period",
            "billing_owner",
            "billing_reference",
            "recurring",
            "recurring_label",
            "linked_journals",
            "journal",
            "project",
            "cost_center",
            "currency",
            "fiscal_period",
            # write-only fields
            "lines",
            "tax_rate",
        ]

    def validate(self, data):
        # Ensure the customer FK references a real Donor row
        customer = data.get("customer")
        if customer is not None:
            pk = customer.pk if hasattr(customer, "pk") else customer
            if not Donor.objects.filter(pk=pk).exists():
                raise serializers.ValidationError(
                    {"customer": "Referenced customer (Donor) does not exist."}
                )
        return data

    def create(self, validated_data):
        from django.db import transaction as db_transaction
        from accounting.models import Journal, JournalEntry, JournalItem, Account

        lines_data = validated_data.pop("lines", [])
        tax_rate = validated_data.pop("tax_rate", Decimal("0"))

        # ── Safe FK: created_by ────────────────────────────────────────────
        created_by = validated_data.pop("created_by", None)
        if created_by is not None:
            user_pk = getattr(created_by, "pk", None)
            if user_pk and User.objects.filter(pk=user_pk).exists():
                validated_data["created_by"] = created_by

        subtotal = sum(
            Decimal(str(line["unit_price"])) * Decimal(str(line.get("quantity", 1)))
            for line in lines_data
        )
        tax_amount = round(subtotal * Decimal(str(tax_rate)) / Decimal("100"), 2)

        with db_transaction.atomic():
            invoice = CustomerInvoice.objects.create(
                **validated_data,
                subtotal=subtotal,
                tax_amount=tax_amount,
            )

            # Save line items and collect amounts per account
            account_totals = {}
            for line in lines_data:
                qty = Decimal(str(line.get("quantity", 1)))
                price = Decimal(str(line["unit_price"]))
                line_total = qty * price
                line_kwargs = {
                    "invoice": invoice,
                    "description": line["description"],
                    "quantity": qty,
                    "unit_price": price,
                    "amount": line_total,
                    "analytic": line.get("analytic", ""),
                }
                account_id = line.get("account")
                acct = None
                if account_id:
                    acct = Account.objects.filter(pk=account_id).first()
                    if acct:
                        line_kwargs["account"] = acct
                analytic_account_id = line.get("analytic_account")
                if analytic_account_id:
                    from accounting.models import AnalyticAccount
                    aa = AnalyticAccount.objects.filter(pk=analytic_account_id).first()
                    if aa:
                        line_kwargs["analytic_account"] = aa
                cost_center_id = line.get("cost_center")
                if cost_center_id:
                    from accounting.models import CostCenter
                    cc = CostCenter.objects.filter(pk=cost_center_id).first()
                    if cc:
                        line_kwargs["cost_center"] = cc
                CustomerInvoiceLine.objects.create(**line_kwargs)

                if acct:
                    account_totals[acct.id] = account_totals.get(acct.id, Decimal("0")) + line_total

        return invoice

    def update(self, instance, validated_data):
        validated_data.pop("lines", None)
        validated_data.pop("tax_rate", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
