import django_filters
from accounting.models import (
    Account,
    JournalEntry,
    JournalItem,
    Voucher,
    Bill,
    Invoice,
    Payment,
    BankTransaction,
    Budget,
    AuditLog,
)


class AccountFilter(django_filters.FilterSet):
    classification = django_filters.CharFilter(
        field_name="account_type__classification"
    )
    group = django_filters.NumberFilter(field_name="account_group")
    min_balance = django_filters.NumberFilter(
        field_name="current_balance", lookup_expr="gte"
    )
    max_balance = django_filters.NumberFilter(
        field_name="current_balance", lookup_expr="lte"
    )

    class Meta:
        model = Account
        fields = [
            "account_type",
            "account_group",
            "is_active",
            "is_reconcilable",
            "currency",
        ]


class JournalEntryFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    min_amount = django_filters.NumberFilter(
        field_name="total_debit", lookup_expr="gte"
    )

    class Meta:
        model = JournalEntry
        fields = ["journal", "status", "date"]


class JournalItemFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(
        field_name="journal_entry__date", lookup_expr="gte"
    )
    date_to = django_filters.DateFilter(
        field_name="journal_entry__date", lookup_expr="lte"
    )

    class Meta:
        model = JournalItem
        fields = [
            "account",
            "journal_entry",
            "cost_center",
            "analytic_account",
            "is_reconciled",
        ]


class VoucherFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="voucher_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="voucher_date", lookup_expr="lte")

    class Meta:
        model = Voucher
        fields = ["voucher_type", "status", "journal", "project", "cost_center"]


class BillFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="bill_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="bill_date", lookup_expr="lte")
    due_before = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    min_amount = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="gte"
    )

    class Meta:
        model = Bill
        fields = ["vendor", "status", "project", "cost_center"]


class InvoiceFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="invoice_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="invoice_date", lookup_expr="lte")
    due_before = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    min_amount = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="gte"
    )

    class Meta:
        model = Invoice
        fields = ["customer", "status", "project", "cost_center"]


class PaymentFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")

    class Meta:
        model = Payment
        fields = ["direction", "payment_method", "status"]


class BankTransactionFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = BankTransaction
        fields = ["bank_account", "transaction_type", "status"]


class BudgetFilter(django_filters.FilterSet):
    class Meta:
        model = Budget
        fields = ["fiscal_year", "status", "project", "department", "cost_center"]


class AuditLogFilter(django_filters.FilterSet):
    date_from = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="gte")
    date_to = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = ["model_name", "action", "user"]
