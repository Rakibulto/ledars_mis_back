"""
Serializers for workspace transaction pages:
CustomerReceipt, BankDeposit, SupplierPayment
"""
from rest_framework import serializers
from accounting.models import (
    CustomerReceipt,
    CustomerReceiptAllocation,
    BankDeposit,
    SupplierPayment,
    Vendor,
    Bill,
    CashWorkspaceTransaction,
    ContraEntry,
    ExpenseEntry,
    PayrollEntry,
    InventoryEntry,
    Account,
)


def resolve_account(value):
    """Accept an integer (FK ID), a string (account name/code), or an Account instance and return Account or None."""
    if value is None or value == "":
        return None
    if isinstance(value, Account):
        return value
    if isinstance(value, int):
        return Account.objects.filter(pk=value).first()
    if isinstance(value, str) and value.isdigit():
        return Account.objects.filter(pk=int(value)).first()
    if isinstance(value, str):
        return (
            Account.objects.filter(name__iexact=value).first()
            or Account.objects.filter(code__iexact=value).first()
            or Account.objects.filter(name__icontains=value).first()
        )
    return None


# ── Customer Receipts ────────────────────────────────────────────────────────


class CustomerReceiptAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerReceiptAllocation
        fields = ["id", "invoice_number", "amount", "created_at"]


class CustomerReceiptListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    number = serializers.CharField(source="receipt_number", read_only=True)
    customer_id = serializers.IntegerField(source="customer.id", read_only=True)
    donor_name = serializers.CharField(source="donor.name", read_only=True, default="")
    bank_account_name_display = serializers.CharField(source="bank_account.name", read_only=True, default="")

    class Meta:
        model = CustomerReceipt
        fields = [
            "id",
            "number",
            "receipt_number",
            "customer",
            "customer_id",
            "customer_name",
            "donor",
            "donor_name",
            "date",
            "method",
            "bank_account_name",
            "bank_account",
            "bank_account_name_display",
            "amount",
            "unapplied_amount",
            "status",
            "allocation_status",
            "reference",
            "collection_owner",
            "remittance_advice",
            "notes",
            "created_at",
        ]


class CustomerReceiptDetailSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_id = serializers.IntegerField(source="customer.id", read_only=True)
    number = serializers.CharField(source="receipt_number", read_only=True)
    donor_name = serializers.CharField(source="donor.name", read_only=True, default="")
    allocations = CustomerReceiptAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerReceipt
        fields = "__all__"


class CustomerReceiptWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerReceipt
        fields = [
            "customer",
            "donor",
            "date",
            "method",
            "bank_account_name",
            "bank_account",
            "amount",
            "reference",
            "collection_owner",
            "remittance_advice",
            "notes",
        ]

    def validate_bank_account(self, value):
        return resolve_account(value)

    def create(self, validated_data):
        validated_data["unapplied_amount"] = validated_data["amount"]
        return super().create(validated_data)


# ── Bank Deposits ────────────────────────────────────────────────────────────


class BankDepositListSerializer(serializers.ModelSerializer):
    number = serializers.CharField(source="deposit_number", read_only=True)
    bank_account_name_display = serializers.CharField(source="bank_account.name", read_only=True, default="")

    class Meta:
        model = BankDeposit
        fields = [
            "id",
            "number",
            "deposit_number",
            "date",
            "bank_account_name",
            "bank_account",
            "bank_account_name_display",
            "source",
            "deposit_method",
            "deposit_slip_ref",
            "prepared_by",
            "amount",
            "description",
            "status",
            "reconciliation_status",
            "created_at",
        ]


class BankDepositWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankDeposit
        fields = [
            "date",
            "bank_account_name",
            "bank_account",
            "source",
            "deposit_method",
            "deposit_slip_ref",
            "prepared_by",
            "amount",
            "description",
        ]

    def validate_bank_account(self, value):
        return resolve_account(value)


# ── Supplier Payments ────────────────────────────────────────────────────────


class SupplierPaymentVendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["id", "name", "code", "email", "status"]


class SupplierPaymentListSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    number = serializers.CharField(source="payment_number", read_only=True)
    supplier_id = serializers.IntegerField(source="vendor.id", read_only=True)
    bank_account_name_display = serializers.CharField(source="bank_account.name", read_only=True, default="")

    class Meta:
        model = SupplierPayment
        fields = [
            "id",
            "number",
            "payment_number",
            "vendor",
            "supplier_id",
            "vendor_name",
            "date",
            "method",
            "bank_account_name",
            "bank_account",
            "bank_account_name_display",
            "amount",
            "status",
            "release_status",
            "payment_run",
            "bill_refs",
            "approval_route",
            "settlement_reference",
            "notes",
            "created_at",
        ]


class SupplierPaymentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierPayment
        fields = [
            "vendor",
            "date",
            "method",
            "bank_account_name",
            "bank_account",
            "amount",
            "payment_run",
            "bill_refs",
            "approval_route",
            "settlement_reference",
            "notes",
        ]

    def validate_bank_account(self, value):
        return resolve_account(value)


# ── Cash Workspace Transactions ──────────────────────────────────────────────

class CashWorkspaceTransactionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    number = serializers.CharField(source="transaction_number", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True, default="")

    class Meta:
        model = CashWorkspaceTransaction
        fields = [
            "id", "number", "transaction_number",
            "date", "account", "account_name", "counterparty",
            "direction", "amount", "status",
            "payment_method", "reference", "description",
            "created_by", "created_by_name", "created_at",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email or obj.created_by.username
        return ""


class CashWorkspaceTransactionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashWorkspaceTransaction
        fields = [
            "date", "account", "counterparty",
            "direction", "amount", "payment_method",
            "reference", "description",
        ]

    def validate_account(self, value):
        return resolve_account(value)


# ── Contra Entries ───────────────────────────────────────────────────────────

class ContraEntrySerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    number = serializers.CharField(source="entry_number", read_only=True)
    from_account_name = serializers.CharField(source="from_account.name", read_only=True, default="")
    to_account_name = serializers.CharField(source="to_account.name", read_only=True, default="")

    class Meta:
        model = ContraEntry
        fields = [
            "id", "number", "entry_number",
            "date", "from_account", "from_account_name",
            "to_account", "to_account_name",
            "transfer_channel", "treasury_owner",
            "reference", "amount", "description",
            "status", "created_by", "created_by_name", "created_at",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email or obj.created_by.username
        return ""


class ContraEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContraEntry
        fields = [
            "date", "from_account", "to_account",
            "transfer_channel", "treasury_owner",
            "reference", "amount", "description",
        ]

    def validate_from_account(self, value):
        return resolve_account(value)

    def validate_to_account(self, value):
        return resolve_account(value)


# ── Expense Entries ──────────────────────────────────────────────────────────

class ExpenseEntrySerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    number = serializers.CharField(source="entry_number", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True, default="")

    class Meta:
        model = ExpenseEntry
        fields = [
            "id", "number", "entry_number",
            "date", "category", "category_name", "employee",
            "cost_center", "approval_route", "reference",
            "amount", "description", "status",
            "created_by", "created_by_name", "created_at",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email or obj.created_by.username
        return ""


class ExpenseEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseEntry
        fields = [
            "date", "category", "employee",
            "cost_center", "approval_route", "reference",
            "amount", "description",
        ]

    def validate_category(self, value):
        return resolve_account(value)


# ── Payroll Entries ──────────────────────────────────────────────────────────

class PayrollEntrySerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    number = serializers.CharField(source="entry_number", read_only=True)
    expense_account_name = serializers.CharField(source="expense_account.name", read_only=True, default="")
    bank_account_name = serializers.CharField(source="bank_account.name", read_only=True, default="")
    liability_account_name = serializers.CharField(source="liability_account.name", read_only=True, default="")

    class Meta:
        model = PayrollEntry
        fields = [
            "id", "number", "entry_number",
            "payroll_cycle", "date",
            "period_start", "period_end",
            "employee_count", "gross_amount", "net_amount",
            "liability_amount",
            "expense_account", "expense_account_name",
            "bank_account", "bank_account_name",
            "liability_account", "liability_account_name",
            "approval_route",
            "funding_source", "description", "status",
            "created_by", "created_by_name", "created_at",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email or obj.created_by.username
        return ""


class PayrollEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollEntry
        fields = [
            "payroll_cycle", "date",
            "period_start", "period_end",
            "employee_count", "gross_amount", "net_amount",
            "expense_account", "bank_account", "liability_account",
            "approval_route", "funding_source", "description",
        ]

    def validate_expense_account(self, value):
        return resolve_account(value)

    def validate_bank_account(self, value):
        return resolve_account(value)

    def validate_liability_account(self, value):
        return resolve_account(value)


# ── Inventory Entries ────────────────────────────────────────────────────────

class InventoryEntrySerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    number = serializers.CharField(source="entry_number", read_only=True)
    inventory_account_name = serializers.CharField(source="inventory_account.name", read_only=True, default="")
    cogs_account_name = serializers.CharField(source="cogs_account.name", read_only=True, default="")

    class Meta:
        model = InventoryEntry
        fields = [
            "id", "number", "entry_number",
            "date", "warehouse", "category",
            "movement_type", "item_reference",
            "quantity", "unit_cost", "amount",
            "inventory_account", "inventory_account_name",
            "cogs_account", "cogs_account_name",
            "procurement_reference", "description",
            "status", "created_by", "created_by_name", "created_at",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email or obj.created_by.username
        return ""


class InventoryEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryEntry
        fields = [
            "date", "warehouse", "category",
            "movement_type", "item_reference",
            "quantity", "unit_cost",
            "inventory_account", "cogs_account",
            "procurement_reference", "description",
        ]

    def validate_inventory_account(self, value):
        return resolve_account(value)

    def validate_cogs_account(self, value):
        return resolve_account(value)
