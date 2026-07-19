from rest_framework import serializers
from accounting.models import (
    BankAccount,
    BankTransaction,
    BankReconciliation,
    BankReconciliationLine,
    CashRegister,
    CashTransaction,
)


class BankAccountSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(
        source="account.code", read_only=True, default=""
    )
    account_name = serializers.CharField(
        source="account.name", read_only=True, default=""
    )
    currency_code = serializers.CharField(
        source="currency.code", read_only=True, default="BDT"
    )

    class Meta:
        model = BankAccount
        fields = "__all__"

    def validate(self, attrs):
        status_val = attrs.get(
            "status", getattr(self.instance, "status", None) or "active"
        )
        account = attrs.get(
            "account", getattr(self.instance, "account", None) if self.instance else None
        )
        if status_val == "active" and not account:
            raise serializers.ValidationError(
                {"account": "Active bank/cash accounts must be linked to a CoA account."}
            )
        if account is not None and getattr(account, "ngo_project_id", None) is not None:
            raise serializers.ValidationError(
                {
                    "account": (
                        "Bank/cash must link to a global CoA account "
                        "(not a project-scoped ledger)."
                    )
                }
            )
        return attrs


class BankTransactionSerializer(serializers.ModelSerializer):
    bank_account_name = serializers.CharField(
        source="bank_account.name", read_only=True
    )
    type_display = serializers.CharField(
        source="get_transaction_type_display", read_only=True
    )
    ngo_project_title = serializers.CharField(
        source="ngo_project.title", read_only=True, default=""
    )

    class Meta:
        model = BankTransaction
        fields = "__all__"


class BankReconciliationLineSerializer(serializers.ModelSerializer):
    transaction_detail = BankTransactionSerializer(
        source="bank_transaction", read_only=True
    )

    class Meta:
        model = BankReconciliationLine
        fields = "__all__"


class BankReconciliationListSerializer(serializers.ModelSerializer):
    bank_account_name = serializers.CharField(
        source="bank_account.name", read_only=True
    )
    reconciled_by_name = serializers.CharField(
        source="reconciled_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = BankReconciliation
        fields = [
            "id",
            "bank_account",
            "bank_account_name",
            "statement_date",
            "statement_balance",
            "book_balance",
            "difference",
            "status",
            "reconciled_by_name",
            "completed_at",
            "created_at",
        ]


class BankReconciliationDetailSerializer(serializers.ModelSerializer):
    bank_account_detail = BankAccountSerializer(source="bank_account", read_only=True)
    lines = BankReconciliationLineSerializer(many=True, read_only=True)

    class Meta:
        model = BankReconciliation
        fields = "__all__"


class CashRegisterSerializer(serializers.ModelSerializer):
    custodian_name = serializers.CharField(
        source="custodian.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = CashRegister
        fields = "__all__"


class CashTransactionSerializer(serializers.ModelSerializer):
    register_name = serializers.CharField(source="cash_register.name", read_only=True)
    type_display = serializers.CharField(
        source="get_transaction_type_display", read_only=True
    )

    class Meta:
        model = CashTransaction
        fields = "__all__"
