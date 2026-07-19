from django.urls import path, include
from rest_framework.routers import DefaultRouter

from ..views.account_views import (
    AccountTypeViewSet,
    AccountGroupViewSet,
    AccountViewSet,
    AccountTagViewSet,
)
from ..views.fiscal_views import FiscalYearViewSet, FiscalPeriodViewSet
from ..views.journal_views import (
    JournalViewSet,
    JournalEntryViewSet,
    JournalItemViewSet,
    JournalEntryAttachmentViewSet,
    RecurringJournalTemplateViewSet,
)
from ..views.voucher_views import (
    VoucherViewSet,
    VoucherApprovalViewSet,
    VoucherAttachmentViewSet,
)
from ..views.payment_views import (
    PaymentMethodViewSet,
    PaymentViewSet,
    PaymentAllocationViewSet,
)
from ..views.bank_views import (
    BankAccountViewSet,
    BankTransactionViewSet,
    BankReconciliationViewSet,
    CashRegisterViewSet,
    CashTransactionViewSet,
)
from ..views.payable_views import (
    VendorViewSet,
    BillViewSet,
    DebitNoteViewSet,
    VendorCreditViewSet,
    SupplierLedgerViewSet,
)
from ..views.receivable_views import (
    CustomerViewSet,
    InvoiceViewSet,
    CreditNoteViewSet,
)
from ..views.budget_views import (
    BudgetCategoryViewSet,
    BudgetViewSet,
    BudgetLineViewSet,
    BudgetTransferViewSet,
    BudgetAmendmentViewSet,
)
from ..views.tax_views import (
    TaxGroupViewSet,
    TaxViewSet,
    TaxRuleViewSet,
    WithholdingTaxViewSet,
)
from ..views.analytics_views import (
    CostCenterViewSet,
    AnalyticPlanViewSet,
    AnalyticAccountViewSet,
    AnalyticLineViewSet,
    AnalyticTagViewSet,
)
from ..views.currency_views import CurrencyViewSet, ExchangeRateViewSet
from ..views.report_views import (
    FinancialReportTemplateViewSet,
    GeneratedReportViewSet,
)
from ..views.settings_views import (
    AccountingSettingsView,
    NumberSequenceViewSet,
    ApprovalRuleViewSet,
    ApprovalWorkflowViewSet,
    AuditLogViewSet,
    PostingRuleViewSet,
    IntegrationRuleViewSet,
    LockDateViewSet,
)
from ..views.dashboard_views import AccountingDashboardView
from ..views.gateway_views import (
    DayBookView,
    CashBankBookView,
    AccountLedgerView,
    ProfitAndLossView,
    BalanceSheetView,
    ProjectStatementView,
)
from ..views.asset_views import (
    AssetCategoryViewSet,
    AssetViewSet,
    AssetDepreciationViewSet,
    AssetDisposalViewSet,
    AssetImpairmentViewSet,
    AssetTransferViewSet,
)
from ..views.extended_views import (
    PaymentTermViewSet,
    FiscalPositionViewSet,
    IncotermViewSet,
    ReconciliationModelViewSet,
    BankStatementViewSet,
    BankStatementLineViewSet,
    CheckViewSet,
    BankTransferViewSet,
    DeferredRevenueViewSet,
    DeferredExpenseViewSet,
)
from ..views.perdium_views import PerdiumViewSet
from ..views.perdium_claim_views import PerdiumClaimViewSet
from ..views.customer_invoice_views import CustomerInvoiceViewSet
from ..views.workspace_views import (
    CustomerReceiptViewSet,
    BankDepositViewSet,
    SupplierPaymentViewSet,
    CashWorkspaceTransactionViewSet,
    ContraEntryViewSet,
    ExpenseEntryViewSet,
    PayrollEntryViewSet,
    InventoryEntryViewSet,
)

router = DefaultRouter()

# ── Chart of Accounts ──
router.register(r"acc-account-types", AccountTypeViewSet, basename="acc-account-types")
router.register(
    r"acc-account-groups", AccountGroupViewSet, basename="acc-account-groups"
)
router.register(r"acc-accounts", AccountViewSet, basename="acc-accounts")
router.register(r"acc-account-tags", AccountTagViewSet, basename="acc-account-tags")

# ── Fiscal ──
router.register(r"acc-fiscal-years", FiscalYearViewSet, basename="acc-fiscal-years")
router.register(
    r"acc-fiscal-periods", FiscalPeriodViewSet, basename="acc-fiscal-periods"
)

# ── Journals ──
router.register(r"acc-journals", JournalViewSet, basename="acc-journals")
router.register(
    r"acc-journal-entries", JournalEntryViewSet, basename="acc-journal-entries"
)
router.register(r"acc-journal-items", JournalItemViewSet, basename="acc-journal-items")
router.register(
    r"acc-journal-attachments",
    JournalEntryAttachmentViewSet,
    basename="acc-journal-attachments",
)
router.register(
    r"acc-recurring-journals",
    RecurringJournalTemplateViewSet,
    basename="acc-recurring-journals",
)

# ── Vouchers ──
router.register(r"acc-vouchers", VoucherViewSet, basename="acc-vouchers")
router.register(
    r"acc-voucher-approvals", VoucherApprovalViewSet, basename="acc-voucher-approvals"
)
router.register(
    r"acc-voucher-attachments",
    VoucherAttachmentViewSet,
    basename="acc-voucher-attachments",
)

# ── Payments ──
router.register(
    r"acc-payment-methods", PaymentMethodViewSet, basename="acc-payment-methods"
)
router.register(r"acc-payments", PaymentViewSet, basename="acc-payments")
router.register(
    r"acc-payment-allocations",
    PaymentAllocationViewSet,
    basename="acc-payment-allocations",
)

# ── Banking ──
router.register(r"acc-bank-accounts", BankAccountViewSet, basename="acc-bank-accounts")
router.register(
    r"acc-bank-transactions", BankTransactionViewSet, basename="acc-bank-transactions"
)
router.register(
    r"acc-bank-reconciliations",
    BankReconciliationViewSet,
    basename="acc-bank-reconciliations",
)
router.register(
    r"acc-cash-registers", CashRegisterViewSet, basename="acc-cash-registers"
)
router.register(
    r"acc-cash-transactions", CashTransactionViewSet, basename="acc-cash-transactions"
)

# ── Payables (AP) ──
router.register(r"acc-vendors", VendorViewSet, basename="acc-vendors")
router.register(r"acc-bills", BillViewSet, basename="acc-bills")
router.register(r"acc-debit-notes", DebitNoteViewSet, basename="acc-debit-notes")
router.register(
    r"acc-vendor-credits", VendorCreditViewSet, basename="acc-vendor-credits"
)
router.register(
    r"acc-supplier-ledger", SupplierLedgerViewSet, basename="acc-supplier-ledger"
)

# ── Receivables (AR) ──
router.register(r"acc-customers", CustomerViewSet, basename="acc-customers")
router.register(r"acc-invoices", InvoiceViewSet, basename="acc-invoices")
router.register(r"acc-credit-notes", CreditNoteViewSet, basename="acc-credit-notes")

# ── Budgets ──
router.register(
    r"acc-budget-categories", BudgetCategoryViewSet, basename="acc-budget-categories"
)
router.register(r"acc-budgets", BudgetViewSet, basename="acc-budgets")
router.register(r"acc-budget-lines", BudgetLineViewSet, basename="acc-budget-lines")
router.register(
    r"acc-budget-transfers", BudgetTransferViewSet, basename="acc-budget-transfers"
)
router.register(
    r"acc-budget-amendments", BudgetAmendmentViewSet, basename="acc-budget-amendments"
)

# ── Tax ──
router.register(r"acc-tax-groups", TaxGroupViewSet, basename="acc-tax-groups")
router.register(r"acc-taxes", TaxViewSet, basename="acc-taxes")
router.register(r"acc-tax-rules", TaxRuleViewSet, basename="acc-tax-rules")
router.register(
    r"acc-withholding-taxes", WithholdingTaxViewSet, basename="acc-withholding-taxes"
)

# ── Analytics ──
router.register(r"acc-cost-centers", CostCenterViewSet, basename="acc-cost-centers")
router.register(
    r"acc-analytic-plans", AnalyticPlanViewSet, basename="acc-analytic-plans"
)
router.register(
    r"acc-analytic-accounts", AnalyticAccountViewSet, basename="acc-analytic-accounts"
)
router.register(
    r"acc-analytic-lines", AnalyticLineViewSet, basename="acc-analytic-lines"
)
router.register(r"acc-analytic-tags", AnalyticTagViewSet, basename="acc-analytic-tags")

# ── Multi-Currency ──
router.register(r"acc-currencies", CurrencyViewSet, basename="acc-currencies")
router.register(
    r"acc-exchange-rates", ExchangeRateViewSet, basename="acc-exchange-rates"
)

# ── Reports ──
router.register(
    r"acc-report-templates",
    FinancialReportTemplateViewSet,
    basename="acc-report-templates",
)
router.register(
    r"acc-generated-reports", GeneratedReportViewSet, basename="acc-generated-reports"
)

# ── Settings ──
# Accounting settings are handled by a dedicated APIView (singleton)
router.register(
    r"acc-number-sequences", NumberSequenceViewSet, basename="acc-number-sequences"
)
router.register(
    r"acc-approval-rules", ApprovalRuleViewSet, basename="acc-approval-rules"
)
router.register(r"acc-audit-logs", AuditLogViewSet, basename="acc-audit-logs")
router.register(
    r"acc-posting-rules", PostingRuleViewSet, basename="acc-posting-rules"
)
router.register(
    r"acc-integration-rules", IntegrationRuleViewSet, basename="acc-integration-rules"
)
router.register(
    r"acc-approval-workflows", ApprovalWorkflowViewSet, basename="acc-approval-workflows"
)
router.register(r"acc-lock-dates", LockDateViewSet, basename="acc-lock-dates")

# ── Assets ──
router.register(
    r"acc-asset-categories", AssetCategoryViewSet, basename="acc-asset-categories"
)
router.register(r"acc-assets", AssetViewSet, basename="acc-assets")
router.register(
    r"acc-asset-depreciations",
    AssetDepreciationViewSet,
    basename="acc-asset-depreciations",
)
router.register(
    r"acc-asset-disposals", AssetDisposalViewSet, basename="acc-asset-disposals"
)
router.register(
    r"acc-asset-impairments", AssetImpairmentViewSet, basename="acc-asset-impairments"
)
router.register(
    r"acc-asset-transfers", AssetTransferViewSet, basename="acc-asset-transfers"
)

# ── Perdium ──
router.register(r"acc-perdium", PerdiumViewSet, basename="acc-perdium")
router.register(r"acc-perdium-claims", PerdiumClaimViewSet, basename="acc-perdium-claims")

# ── Extended (Odoo-style) ──
router.register(r"acc-payment-terms", PaymentTermViewSet, basename="acc-payment-terms")
router.register(
    r"acc-fiscal-positions", FiscalPositionViewSet, basename="acc-fiscal-positions"
)
router.register(r"acc-incoterms", IncotermViewSet, basename="acc-incoterms")
router.register(
    r"acc-reconciliation-models",
    ReconciliationModelViewSet,
    basename="acc-reconciliation-models",
)
router.register(
    r"acc-bank-statements", BankStatementViewSet, basename="acc-bank-statements"
)
router.register(
    r"acc-bank-statement-lines", BankStatementLineViewSet, basename="acc-bank-statement-lines"
)
router.register(r"acc-checks", CheckViewSet, basename="acc-checks")
router.register(
    r"acc-bank-transfers", BankTransferViewSet, basename="acc-bank-transfers"
)
router.register(
    r"acc-deferred-revenue", DeferredRevenueViewSet, basename="acc-deferred-revenue"
)
router.register(
    r"acc-deferred-expenses", DeferredExpenseViewSet, basename="acc-deferred-expenses"
)

# ── Customer Invoices (Transaction workspace) ──
router.register(
    r"acc-customer-invoices",
    CustomerInvoiceViewSet,
    basename="acc-customer-invoices",
)

# ── Workspace transaction pages ──
router.register(
    r"acc-customer-receipts",
    CustomerReceiptViewSet,
    basename="acc-customer-receipts",
)
router.register(
    r"acc-bank-deposits",
    BankDepositViewSet,
    basename="acc-bank-deposits",
)
router.register(
    r"acc-supplier-payments",
    SupplierPaymentViewSet,
    basename="acc-supplier-payments",
)
router.register(
    r"acc-workspace-cash-transactions",
    CashWorkspaceTransactionViewSet,
    basename="acc-workspace-cash-transactions",
)
router.register(
    r"acc-workspace-contra-entries",
    ContraEntryViewSet,
    basename="acc-workspace-contra-entries",
)
router.register(
    r"acc-workspace-expense-entries",
    ExpenseEntryViewSet,
    basename="acc-workspace-expense-entries",
)
router.register(
    r"acc-workspace-payroll-entries",
    PayrollEntryViewSet,
    basename="acc-workspace-payroll-entries",
)
router.register(
    r"acc-workspace-inventory-entries",
    InventoryEntryViewSet,
    basename="acc-workspace-inventory-entries",
)


urlpatterns = [
    path("", include(router.urls)),
    path("acc-settings/", AccountingSettingsView.as_view()),
    path("acc-settings/1/", AccountingSettingsView.as_view()),
    # Dashboard
    path("acc-dashboard/", AccountingDashboardView.as_view(), name="acc-dashboard"),
    # Tally Gateway display & essential reports
    path("acc-gateway/day-book/", DayBookView.as_view(), name="acc-gateway-day-book"),
    path(
        "acc-gateway/cash-bank-book/",
        CashBankBookView.as_view(),
        name="acc-gateway-cash-bank-book",
    ),
    path(
        "acc-gateway/account-ledger/",
        AccountLedgerView.as_view(),
        name="acc-gateway-account-ledger",
    ),
    path(
        "acc-gateway/profit-and-loss/",
        ProfitAndLossView.as_view(),
        name="acc-gateway-profit-and-loss",
    ),
    path(
        "acc-gateway/balance-sheet/",
        BalanceSheetView.as_view(),
        name="acc-gateway-balance-sheet",
    ),
    path(
        "acc-gateway/project-statement/",
        ProjectStatementView.as_view(),
        name="acc-gateway-project-statement",
    ),
]
