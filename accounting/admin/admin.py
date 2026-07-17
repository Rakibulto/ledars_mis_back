from django.contrib import admin

from ..models.account_models import AccountType, AccountGroup, Account, AccountTag
from ..models.fiscal_models import FiscalYear, FiscalPeriod
from ..models.journal_models import (
    Journal,
    JournalEntry,
    JournalItem,
    RecurringJournalTemplate,
    RecurringJournalLine,
)
from ..models.voucher_models import (
    VoucherSequence,
    Voucher,
    VoucherLine,
    VoucherApproval,
    VoucherAttachment,
)
from ..models.payment_models import PaymentMethod, Payment, PaymentAllocation
from ..models.bank_models import (
    BankAccount,
    BankTransaction,
    BankReconciliation,
    BankReconciliationLine,
    CashRegister,
    CashTransaction,
)
from ..models.payable_models import (
    Vendor,
    Bill,
    BillLine,
    BillPayment,
    DebitNote,
    DebitNoteLine,
    VendorCredit,
)
from ..models.receivable_models import (
    Customer,
    Invoice,
    InvoiceLine,
    InvoicePayment,
    CreditNote,
    CreditNoteLine,
)
from ..models.budget_models import BudgetCategory, Budget, BudgetLine, BudgetTransfer
from ..models.tax_models import TaxGroup, Tax, TaxRule, WithholdingTax
from ..models.analytics_models import (
    CostCenter,
    AnalyticAccount,
    AnalyticLine,
    AnalyticTag,
)
from ..models.currency_models import Currency, ExchangeRate
from ..models.report_models import (
    FinancialReportTemplate,
    ReportLine,
    GeneratedReport,
    GeneratedReportData,
)
from ..models.settings_models import (
    AccountingSettings,
    NumberSequence,
    ApprovalRule,
    AuditLog,
)
from ..models.asset_models import (
    AssetCategory,
    Asset,
    AssetDepreciation,
    AssetDisposal,
)
from ..models.extended_models import (
    PaymentTerm,
    FiscalPosition,
    FiscalPositionTaxMapping,
    FiscalPositionAccountMapping,
    Incoterm,
    ReconciliationModel,
    BankStatement,
    BankStatementLine,
    Check,
    BankTransfer,
    DeferredRevenue,
    DeferredExpense,
)


# ══════════════════════════════════════════════════════════
# Chart of Accounts
# ══════════════════════════════════════════════════════════


@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "classification", "liquidity_type"]
    list_filter = ["classification", "liquidity_type"]
    search_fields = ["name"]


@admin.register(AccountGroup)
class AccountGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "code_prefix_start", "code_prefix_end", "parent"]
    list_filter = ["parent"]
    search_fields = ["name", "code_prefix_start"]


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "account_type", "current_balance", "is_active"]
    list_filter = ["account_type", "is_active", "is_reconcilable"]
    search_fields = ["code", "name"]
    list_editable = ["is_active"]


@admin.register(AccountTag)
class AccountTagAdmin(admin.ModelAdmin):
    list_display = ["name", "color"]
    search_fields = ["name"]


# ══════════════════════════════════════════════════════════
# Fiscal
# ══════════════════════════════════════════════════════════


class FiscalPeriodInline(admin.TabularInline):
    model = FiscalPeriod
    extra = 0
    fields = ["number", "name", "start_date", "end_date", "status"]


@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "start_date", "end_date", "status"]
    list_filter = ["status"]
    search_fields = ["name", "code"]
    inlines = [FiscalPeriodInline]


@admin.register(FiscalPeriod)
class FiscalPeriodAdmin(admin.ModelAdmin):
    list_display = ["name", "fiscal_year", "number", "start_date", "end_date", "status"]
    list_filter = ["status", "fiscal_year"]


# ══════════════════════════════════════════════════════════
# Journals
# ══════════════════════════════════════════════════════════


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "journal_type", "is_active"]
    list_filter = ["journal_type", "is_active"]
    search_fields = ["name", "code"]


class JournalItemInline(admin.TabularInline):
    model = JournalItem
    extra = 0
    fields = ["account", "description", "debit", "credit", "cost_center"]


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "journal",
        "date",
        "status",
        "total_debit",
        "total_credit",
    ]
    list_filter = ["status", "journal", "date"]
    search_fields = ["reference"]
    inlines = [JournalItemInline]
    date_hierarchy = "date"


@admin.register(JournalItem)
class JournalItemAdmin(admin.ModelAdmin):
    list_display = ["journal_entry", "account", "debit", "credit", "is_reconciled"]
    list_filter = ["is_reconciled", "account"]
    search_fields = ["description", "account__name"]


class RecurringJournalLineInline(admin.TabularInline):
    model = RecurringJournalLine
    extra = 0


@admin.register(RecurringJournalTemplate)
class RecurringJournalTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "journal", "frequency", "is_active", "next_run_date"]
    list_filter = ["frequency", "is_active"]
    search_fields = ["name"]
    inlines = [RecurringJournalLineInline]


# ══════════════════════════════════════════════════════════
# Vouchers
# ══════════════════════════════════════════════════════════


@admin.register(VoucherSequence)
class VoucherSequenceAdmin(admin.ModelAdmin):
    list_display = ["voucher_type", "year", "last_number"]


class VoucherLineInline(admin.TabularInline):
    model = VoucherLine
    extra = 0
    fields = ["account", "description", "debit", "credit"]


class VoucherApprovalInline(admin.TabularInline):
    model = VoucherApproval
    extra = 0
    readonly_fields = ["acted_at"]


class VoucherAttachmentInline(admin.TabularInline):
    model = VoucherAttachment
    extra = 0


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = [
        "voucher_number",
        "voucher_type",
        "date",
        "status",
        "total_amount",
    ]
    list_filter = ["voucher_type", "status", "date"]
    search_fields = ["voucher_number", "narration"]
    inlines = [VoucherLineInline, VoucherApprovalInline, VoucherAttachmentInline]
    date_hierarchy = "date"


@admin.register(VoucherApproval)
class VoucherApprovalAdmin(admin.ModelAdmin):
    list_display = ["voucher", "approver", "status", "acted_at"]
    list_filter = ["status"]


# ══════════════════════════════════════════════════════════
# Payments
# ══════════════════════════════════════════════════════════


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ["name", "payment_type", "is_active"]
    list_filter = ["payment_type", "is_active"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "direction",
        "payment_method",
        "amount",
        "date",
        "status",
    ]
    list_filter = ["direction", "status", "payment_method"]
    search_fields = ["reference"]
    date_hierarchy = "date"


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ["payment", "allocated_amount"]


# ══════════════════════════════════════════════════════════
# Banking
# ══════════════════════════════════════════════════════════


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ["name", "bank_name", "account_number", "current_balance", "status"]
    list_filter = ["status"]
    search_fields = ["name", "bank_name", "account_number"]


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ["bank_account", "date", "transaction_type", "amount", "status"]
    list_filter = ["transaction_type", "status", "bank_account"]
    date_hierarchy = "date"


class BankReconciliationLineInline(admin.TabularInline):
    model = BankReconciliationLine
    extra = 0


@admin.register(BankReconciliation)
class BankReconciliationAdmin(admin.ModelAdmin):
    list_display = [
        "bank_account",
        "statement_date",
        "statement_balance",
        "status",
        "reconciled_by",
    ]
    list_filter = ["status", "bank_account"]
    inlines = [BankReconciliationLineInline]


@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = ["name", "custodian", "current_balance", "is_active"]
    list_filter = ["is_active"]


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    list_display = ["cash_register", "date", "transaction_type", "amount"]
    list_filter = ["transaction_type", "cash_register"]
    date_hierarchy = "date"


# ══════════════════════════════════════════════════════════
# Accounts Payable
# ══════════════════════════════════════════════════════════


@admin.register(Vendor)
class AccVendorAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "total_payable", "status"]
    list_filter = ["status"]
    search_fields = ["name", "email"]


class BillLineInline(admin.TabularInline):
    model = BillLine
    extra = 0
    fields = ["account", "description", "quantity", "unit_price", "subtotal"]
    readonly_fields = ["subtotal"]


class BillPaymentInline(admin.TabularInline):
    model = BillPayment
    extra = 0
    readonly_fields = ["date"]


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = [
        "bill_number",
        "vendor",
        "bill_date",
        "due_date",
        "total_amount",
        "amount_paid",
        "status",
    ]
    list_filter = ["status", "vendor"]
    search_fields = ["bill_number", "reference", "vendor__name"]
    inlines = [BillLineInline, BillPaymentInline]
    date_hierarchy = "bill_date"


class DebitNoteLineInline(admin.TabularInline):
    model = DebitNoteLine
    extra = 0


@admin.register(DebitNote)
class DebitNoteAdmin(admin.ModelAdmin):
    list_display = ["debit_note_number", "vendor", "date", "total_amount", "status"]
    list_filter = ["status"]
    inlines = [DebitNoteLineInline]


@admin.register(VendorCredit)
class VendorCreditAdmin(admin.ModelAdmin):
    list_display = ["vendor", "credit_balance", "last_updated"]


# ══════════════════════════════════════════════════════════
# Accounts Receivable
# ══════════════════════════════════════════════════════════


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "total_receivable", "status"]
    list_filter = ["status"]
    search_fields = ["name", "email"]


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    fields = ["account", "description", "quantity", "unit_price", "subtotal"]
    readonly_fields = ["subtotal"]


class InvoicePaymentInline(admin.TabularInline):
    model = InvoicePayment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "invoice_number",
        "customer",
        "invoice_date",
        "due_date",
        "total_amount",
        "amount_paid",
        "status",
    ]
    list_filter = ["status", "customer"]
    search_fields = ["invoice_number", "reference", "customer__name"]
    inlines = [InvoiceLineInline, InvoicePaymentInline]
    date_hierarchy = "invoice_date"


class CreditNoteLineInline(admin.TabularInline):
    model = CreditNoteLine
    extra = 0


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ["credit_note_number", "customer", "date", "total_amount", "status"]
    list_filter = ["status"]
    inlines = [CreditNoteLineInline]


# ══════════════════════════════════════════════════════════
# Budgets
# ══════════════════════════════════════════════════════════


@admin.register(BudgetCategory)
class BudgetCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "parent"]
    search_fields = ["name", "code"]


class BudgetLineInline(admin.TabularInline):
    model = BudgetLine
    extra = 0
    fields = [
        "account",
        "category",
        "planned_amount",
        "actual_amount",
        "available_amount",
    ]
    readonly_fields = ["actual_amount", "available_amount"]


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "fiscal_year",
        "status",
        "total_planned",
        "total_actual",
    ]
    list_filter = ["status", "fiscal_year"]
    search_fields = ["name", "code"]
    inlines = [BudgetLineInline]


@admin.register(BudgetTransfer)
class BudgetTransferAdmin(admin.ModelAdmin):
    list_display = [
        "from_line",
        "to_line",
        "amount",
        "status",
        "requested_by",
        "approved_by",
    ]
    list_filter = ["status"]


# ══════════════════════════════════════════════════════════
# Tax
# ══════════════════════════════════════════════════════════


@admin.register(TaxGroup)
class TaxGroupAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(Tax)
class TaxAdmin(admin.ModelAdmin):
    list_display = ["name", "tax_type", "rate", "scope", "is_active"]
    list_filter = ["tax_type", "scope", "is_active", "tax_group"]
    search_fields = ["name"]


@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display = ["tax", "partner_type", "is_active"]
    list_filter = ["is_active"]


@admin.register(WithholdingTax)
class WithholdingTaxAdmin(admin.ModelAdmin):
    list_display = ["name", "rate", "is_active"]
    list_filter = ["is_active"]


# ══════════════════════════════════════════════════════════
# Analytics
# ══════════════════════════════════════════════════════════


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "parent", "department", "is_active"]
    list_filter = ["is_active", "department"]
    search_fields = ["name", "code"]


@admin.register(AnalyticAccount)
class AnalyticAccountAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "group", "balance", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "code"]


@admin.register(AnalyticLine)
class AnalyticLineAdmin(admin.ModelAdmin):
    list_display = ["analytic_account", "date", "amount", "name"]
    list_filter = ["analytic_account", "cost_center"]
    date_hierarchy = "date"


@admin.register(AnalyticTag)
class AnalyticTagAdmin(admin.ModelAdmin):
    list_display = ["name", "color"]
    search_fields = ["name"]


# ══════════════════════════════════════════════════════════
# Multi-Currency
# ══════════════════════════════════════════════════════════


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "symbol", "is_base", "is_active"]
    list_filter = ["is_active", "is_base"]
    search_fields = ["name", "code"]


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ["currency", "date", "rate", "inverse_rate"]
    list_filter = ["currency"]
    date_hierarchy = "date"


# ══════════════════════════════════════════════════════════
# Financial Reports
# ══════════════════════════════════════════════════════════


class ReportLineInline(admin.TabularInline):
    model = ReportLine
    extra = 0
    fields = ["name", "sequence", "computation_type", "account_codes"]


@admin.register(FinancialReportTemplate)
class FinancialReportTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "report_type", "is_active"]
    list_filter = ["report_type", "is_active"]
    search_fields = ["name"]
    inlines = [ReportLineInline]


class GeneratedReportDataInline(admin.TabularInline):
    model = GeneratedReportData
    extra = 0
    readonly_fields = ["label", "current_amount", "sequence"]


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = [
        "template",
        "period_from",
        "period_to",
        "status",
        "generated_by",
        "generated_at",
    ]
    list_filter = ["status", "template"]
    inlines = [GeneratedReportDataInline]


# ══════════════════════════════════════════════════════════
# Settings
# ══════════════════════════════════════════════════════════


@admin.register(AccountingSettings)
class AccountingSettingsAdmin(admin.ModelAdmin):
    list_display = ["base_currency", "lock_date"]

    def has_add_permission(self, request):
        return not AccountingSettings.objects.exists()


@admin.register(NumberSequence)
class NumberSequenceAdmin(admin.ModelAdmin):
    list_display = ["document_type", "prefix", "next_number", "padding"]
    list_filter = ["document_type"]


@admin.register(ApprovalRule)
class ApprovalRuleAdmin(admin.ModelAdmin):
    list_display = ["document_type", "min_amount", "max_amount", "is_active"]
    list_filter = ["document_type", "is_active"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["model_name", "object_id", "action", "user", "created_at"]
    list_filter = ["model_name", "action"]
    search_fields = ["model_name", "description"]
    readonly_fields = [
        "model_name",
        "object_id",
        "description",
        "action",
        "user",
        "changes",
        "created_at",
    ]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# --- Register remaining models that don't have custom ModelAdmin ---

# Line-item / child models (already imported above)
admin.site.register(RecurringJournalLine)
admin.site.register(VoucherLine)
admin.site.register(VoucherAttachment)
admin.site.register(BankReconciliationLine)
admin.site.register(BillLine)
admin.site.register(BillPayment)
admin.site.register(DebitNoteLine)
admin.site.register(InvoiceLine)
admin.site.register(InvoicePayment)
admin.site.register(CreditNoteLine)
admin.site.register(BudgetLine)
admin.site.register(ReportLine)
admin.site.register(GeneratedReportData)

# Asset models
admin.site.register(AssetCategory)
admin.site.register(Asset)
admin.site.register(AssetDepreciation)
admin.site.register(AssetDisposal)

# Extended models
admin.site.register(PaymentTerm)
admin.site.register(FiscalPosition)
admin.site.register(FiscalPositionTaxMapping)
admin.site.register(FiscalPositionAccountMapping)
admin.site.register(Incoterm)
admin.site.register(ReconciliationModel)
admin.site.register(BankStatement)
admin.site.register(BankStatementLine)
admin.site.register(Check)
admin.site.register(BankTransfer)
admin.site.register(DeferredRevenue)
admin.site.register(DeferredExpense)
