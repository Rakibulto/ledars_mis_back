from rest_framework import serializers
from accounting.models import PaymentMethod, Payment, PaymentAllocation


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = "__all__"


class PaymentAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAllocation
        fields = "__all__"


class PaymentListSerializer(serializers.ModelSerializer):
    direction_display = serializers.CharField(
        source="get_direction_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_method_name = serializers.CharField(
        source="payment_method.name", read_only=True
    )
    journal_name = serializers.CharField(source="journal.name", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "reference",
            "direction",
            "direction_display",
            "payment_method",
            "payment_method_name",
            "journal",
            "journal_name",
            "partner_type",
            "partner_name",
            "amount",
            "date",
            "status",
            "status_display",
            "created_at",
        ]


class PaymentDetailSerializer(serializers.ModelSerializer):
    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    payment_method_detail = PaymentMethodSerializer(
        source="payment_method", read_only=True
    )
    direction_display = serializers.CharField(
        source="get_direction_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Payment
        fields = "__all__"


class PaymentWriteSerializer(serializers.ModelSerializer):
    """Create/update a Payment and auto-create journal entry on save."""

    class Meta:
        model = Payment
        exclude = ["created_by", "journal_entry"]

    def create(self, validated_data):
        from django.db import transaction as db_transaction
        from django.utils import timezone
        from decimal import Decimal
        from accounting.models import Journal, JournalEntry, JournalItem, Account

        with db_transaction.atomic():
            payment = Payment.objects.create(**validated_data)

            # Auto-create journal entry based on payment direction
            journal = payment.journal
            if not journal:
                if payment.direction == "inbound":
                    journal = Journal.objects.filter(journal_type="bank").first() or Journal.objects.filter(journal_type="cash").first()
                else:
                    journal = Journal.objects.filter(journal_type="bank").first() or Journal.objects.filter(journal_type="purchase").first()
            if not journal:
                journal = Journal.objects.first()

            if journal:
                entry = JournalEntry.objects.create(
                    journal=journal,
                    date=payment.date,
                    reference=f"Payment: {payment.reference}",
                    status="posted",
                    total_debit=payment.amount,
                    total_credit=payment.amount,
                    posted_by=validated_data.get("created_by"),
                    posted_at=timezone.now(),
                )

                bank_account = Account.objects.filter(name__icontains="bank").first() or Account.objects.filter(code__startswith="102").first() or Account.objects.filter(name__icontains="cash").first()

                if payment.direction == "inbound":
                    # DEBIT: Bank/Cash (money received)
                    if bank_account:
                        JournalItem.objects.create(
                            journal_entry=entry,
                            account=bank_account,
                            label=f"Receipt from {payment.partner_name}",
                            debit=payment.amount,
                            credit=0,
                        )
                    # CREDIT: Receivable
                    receivable = Account.objects.filter(account_type__classification="receivable").first() or Account.objects.filter(code__startswith="110").first()
                    if receivable:
                        JournalItem.objects.create(
                            journal_entry=entry,
                            account=receivable,
                            label=f"Payment received: {payment.reference}",
                            debit=0,
                            credit=payment.amount,
                        )
                else:
                    # DEBIT: Payable
                    payable = Account.objects.filter(account_type__classification="liability", account_type__liquidity_type="payable").first() or Account.objects.filter(code__startswith="210").first()
                    if payable:
                        JournalItem.objects.create(
                            journal_entry=entry,
                            account=payable,
                            label=f"Payment to {payment.partner_name}",
                            debit=payment.amount,
                            credit=0,
                        )
                    # CREDIT: Bank/Cash (money leaving)
                    if bank_account:
                        JournalItem.objects.create(
                            journal_entry=entry,
                            account=bank_account,
                            label=f"Payment: {payment.reference}",
                            debit=0,
                            credit=payment.amount,
                        )

                payment.journal_entry = entry
                payment.save(update_fields=["journal_entry"])

        return payment
