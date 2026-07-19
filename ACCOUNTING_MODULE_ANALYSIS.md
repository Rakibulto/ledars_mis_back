# Accounting Module — Comprehensive Analysis

> **Generated from source code inspection** (no assumptions).  
> **Repositories analyzed:**
> - Backend: `Z:/noushin/Documents/ledars_mis_back/accounting/`
> - Frontend: `Z:/noushin/Documents/ledars_mis_front/src/app/dashboard/(modules)/accounting-finance/`
>
> **Date:** 2026-07-19

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Backend — Step-by-Step Analysis](#2-backend--step-by-step-analysis)
3. [Frontend — Step-by-Step Analysis](#3-frontend--step-by-step-analysis)
4. [Frontend ↔ Backend API Mapping](#4-frontend--backend-api-mapping)
5. [Cross-Module Integrations](#5-cross-module-integrations)
6. [Key Business Flows](#6-key-business-flows)
7. [Authentication & Permissions](#7-authentication--permissions)
8. [Legacy / Parallel Codebases](#8-legacy--parallel-codebases)
9. [Verified File Counts](#9-verified-file-counts)
10. [বাংলা সারাংশ](#10-বাংলা-সারাংশ)

---

## 1. Executive Summary

The accounting system is an **Odoo-style double-entry ERP module** spanning:

| Layer | Location | Scale (verified) |
|-------|----------|------------------|
| Django app | `ledars_mis_back/accounting/` | 78 files, ~101 model classes across 18 model files |
| REST API | `/api/acc-*` via `core/urls.py` | 70 router registrations + 3 non-router paths |
| React/Next.js UI | `ledars_mis_front/.../accounting-finance/` | 177 `page.jsx` routes, 180 `_components` JSX files, 37 API hooks |

**Architecture pattern:**
- Backend: Django REST Framework ViewSets + serializers; business logic in views, model `save()`, and signals (no dedicated `services/` layer).
- Frontend: Thin Next.js App Router pages → domain components in `_components/` → SWR + axios hooks → `/api/acc-*` endpoints.

---

## 2. Backend — Step-by-Step Analysis

### Step 1: App Registration & Boot

| Item | Source |
|------|--------|
| Installed app | `core/settings.py` → `"accounting.apps.AccountingConfig"` |
| URL mount | `core/urls.py` → `path("api/", include("accounting.urls"))` |
| Signals loaded | `accounting/apps.py` → `ready()` imports `accounting.signals` |

### Step 2: Directory Structure

```
accounting/
├── admin/admin.py
├── apps.py
├── filters/filters.py
├── management/commands/          # 8 seed commands
├── migrations/                   # 0001–0005
├── models/                       # 18 model files
├── serializers/                  # 20 serializer modules
├── signals.py
├── urls/urls.py                  # DRF router + 3 extra paths
└── views/                        # 22 view modules + status_transition_mixin.py
```

**Verified:** 78 total files under `accounting/`.

### Step 3: Data Model Domains

Models are grouped into 18 files. Below is the verified inventory from `accounting/models/__init__.py` and individual model files.

#### 3.1 Chart of Accounts — `models/account_models.py`

| Model | Purpose |
|-------|---------|
| `AccountType` | Classification: asset, liability, equity, income, expense |
| `AccountGroup` | Hierarchical grouping with code prefix ranges |
| `Account` | Core GL account; auto-generates `ACC-####` code on `save()` |
| `AccountTag` | Tags for account categorization |

#### 3.2 Fiscal — `models/fiscal_models.py`

| Model | Purpose |
|-------|---------|
| `FiscalYear` | Annual period with status: draft, open, closed |
| `FiscalPeriod` | Sub-periods within a fiscal year |

#### 3.3 Journals — `models/journal_models.py`

| Model | Purpose |
|-------|---------|
| `Journal` | Journal types: sales, purchase, bank, cash, general |
| `JournalEntry` | Header; auto-generates reference `{prefix}/{year}/{count}` |
| `JournalItem` | Debit/credit lines |
| `JournalEntryAttachment` | File attachments |
| `RecurringJournalTemplate` | Scheduled recurring entries |
| `RecurringJournalLine` | Lines for recurring templates |

#### 3.4 Vouchers — `models/voucher_models.py`

| Model | Purpose |
|-------|---------|
| `VoucherSequence` | Atomic numbering via `select_for_update()` |
| `Voucher` | Payment/receipt/journal/contra vouchers; FK to `projects.Project` |
| `VoucherLine` | Line items |
| `VoucherApproval` | Multi-level approval |
| `VoucherAttachment` | File attachments |

Voucher numbers: `PV/RV/JV/CV-{year}-{#####}`.

#### 3.5 Payments — `models/payment_models.py`

| Model | Purpose |
|-------|---------|
| `PaymentMethod` | cash, bank, cheque, mobile |
| `Payment` | inbound/outbound/internal |
| `PaymentAllocation` | Links payments to documents |

#### 3.6 Banking — `models/bank_models.py`

| Model | Purpose |
|-------|---------|
| `BankAccount` | Linked to COA account |
| `BankTransaction` | Bank-side transactions |
| `BankReconciliation` | Statement vs book reconciliation |
| `BankReconciliationLine` | Matched lines |
| `CashRegister` | Cash drawer with custodian |
| `CashTransaction` | Receipt/payment/replenishment |

#### 3.7 Accounts Payable — `models/payable_models.py`

| Model | Cross-module FKs (verified) |
|-------|----------------------------|
| `Vendor` | `vendorportal.VendorProfile` (as `supplier`), COA `payable_account` |
| `Bill` | `projects.Project`, `procurement.PurchaseOrder`, `procurement.WorkOrder`, `procurement.GoodsReceiptNote` (FK + M2M), `Check`, `BankAccount` |
| `BillLine` | COA `Account`, tax, analytic account |
| `BillPayment` | Links bill to `Payment` |
| `DebitNote` | Vendor, original bill, journal entry |
| `DebitNoteLine` | Line items |
| `VendorCredit` | One-to-one with Vendor |

`Bill.save()` auto-numbers `BILL-{year}-{#####}` and computes `amount_due`.

#### 3.8 Accounts Receivable — `models/receivable_models.py`

| Model | Cross-module FKs |
|-------|-----------------|
| `Customer` | COA `receivable_account` |
| `Invoice` | `projects.Project`, `CostCenter`, journal entry |
| `InvoiceLine` | Line items with tax/discount |
| `InvoicePayment` | Links invoice to payment |
| `CreditNote` | Customer, original invoice |
| `CreditNoteLine` | Line items |

#### 3.9 Customer Invoice (Workspace) — `models/transaction_customer_inv.py`

Separate from core `Invoice` model. Designed to mirror the frontend workspace UI.

| Model | Notable FK |
|-------|-----------|
| `CustomerInvoice` | **`donor.Donor`** (as `customer`) |
| `CustomerInvoiceLine` | Line items |
| `CustomerInvoiceAllocation` | Payment allocations |
| `CustomerInvoiceAttachment` | Files |
| `CustomerInvoiceChatter` | Activity log |

Status choices: `draft`, `sent`, `partial`, `paid`, `overdue`, `cancelled`.

#### 3.10 Budget — `models/budget_models.py`

| Model | Cross-module FKs |
|-------|-----------------|
| `BudgetCategory` | Self-referential parent |
| `Budget` | `employee.Department`, `projects.Project`, `CostCenter` |
| `BudgetLine` | Account, category; computes `available_amount` |
| `BudgetTransfer` | Between budget lines |
| `BudgetAmendment` | Budget amendments |

#### 3.11 Tax — `models/tax_models.py`

`TaxGroup`, `Tax`, `TaxRule`, `WithholdingTax`

#### 3.12 Analytics — `models/analytics_models.py`

| Model | Cross-module FKs |
|-------|-----------------|
| `CostCenter` | `employee.Department`, `projects.Project` |
| `AnalyticPlan` | Hierarchical plans |
| `AnalyticAccount` | `project`; partner_type includes `"donor"` |
| `AnalyticLine` | Journal item linkage |
| `AnalyticTag` | Tagging |

#### 3.13 Currency — `models/currency_models.py`

`Currency` (with `is_base`), `ExchangeRate` (auto `inverse_rate` on save)

#### 3.14 Reports — `models/report_models.py`

`FinancialReportTemplate`, `ReportLine`, `GeneratedReport`, `GeneratedReportData`

#### 3.15 Settings — `models/settings_models.py`

| Model | Purpose |
|-------|---------|
| `AccountingSettings` | Singleton (pk=1): base currency, default accounts, lock dates |
| `NumberSequence` | Auto-numbering |
| `ApprovalRule` | Amount-band approval rules |
| `ApprovalWorkflow` | Multi-level JSON workflows |
| `PostingRule` | Conditional debit/credit routing |
| `IntegrationRule` | Cross-module sync metadata |
| `AuditLog` | Audit trail |
| `LockDate` | Period lock dates |

#### 3.16 Assets — `models/asset_models.py`

`AssetCategory`, `Asset`, `AssetDepreciation`, `AssetDisposal`, `AssetImpairment`, `AssetTransfer`

#### 3.17 Extended (Odoo-style) — `models/extended_models.py`

`PaymentTerm`, `FiscalPosition` (+ tax/account mappings), `Incoterm`, `ReconciliationModel`, `BankStatement`, `BankStatementLine`, `Check`, `BankTransfer`, `DeferredRevenue`, `DeferredExpense`

#### 3.18 Workspace Transactions — `models/workspace_models.py`

| Model | Purpose |
|-------|---------|
| `CustomerReceipt` | Customer receipts; FK to `donor.Donor` |
| `CustomerReceiptAllocation` | Generic FK allocations |
| `BankDeposit` | Bank deposit entries |
| `SupplierPayment` | Supplier payment workspace |
| `CashWorkspaceTransaction` | Cash transactions |
| `ContraEntry` | Account-to-account transfers |
| `ExpenseEntry` | Expense postings |
| `PayrollEntry` | Payroll postings |
| `InventoryEntry` | Inventory postings; `procurement_reference` (string field) |

#### 3.19 Perdium — `models/perdium_models.py`, `models/perdium_claim_models.py`

| Model | Notes |
|-------|-------|
| `Perdium` | Grade/area meal rate configuration |
| `PerdiumClaim` | Employee travel claim with signature JSON |

> **Note:** `Perdium` is registered in URLs/viewsets but is **not** exported in `models/__init__.py`. Only `PerdiumClaim` is imported there.

### Step 4: Serializers

20 serializer modules under `accounting/serializers/`. Pattern: **List / Detail / Write** split for complex resources.

| File | Resources |
|------|-----------|
| `account_serializers.py` | AccountType, AccountGroup, Account, AccountTag |
| `fiscal_serializers.py` | FiscalYear, FiscalPeriod |
| `journal_serializers.py` | Journal, JournalEntry, JournalItem, attachments, recurring |
| `voucher_serializers.py` | Voucher, lines, approvals, attachments |
| `payment_serializers.py` | PaymentMethod, Payment, PaymentAllocation |
| `bank_serializers.py` | BankAccount, transactions, reconciliation, cash |
| `payable_serializers.py` | Vendor, Bill, DebitNote, VendorCredit, SupplierLedger |
| `receivable_serializers.py` | Customer, Invoice, CreditNote |
| `customer_invoice_serializers.py` | CustomerInvoice (with JE creation on post) |
| `budget_serializers.py` | Budget, lines, transfers, amendments |
| `tax_serializers.py` | TaxGroup, Tax, TaxRule, WithholdingTax |
| `analytics_serializers.py` | CostCenter, AnalyticPlan, Account, Line, Tag |
| `currency_serializers.py` | Currency, ExchangeRate |
| `report_serializers.py` | Templates, generated reports |
| `settings_serializers.py` | Settings, sequences, approval, audit, posting, integration, lock |
| `asset_serializers.py` | Asset categories, assets, depreciation, disposal, impairment, transfer |
| `extended_serializers.py` | PaymentTerm, FiscalPosition, Incoterm, reconciliation, bank statements, checks, transfers, deferred |
| `workspace_serializers.py` | All workspace transaction models |
| `perdium_serializers.py` | Perdium |
| `perdium_claim_serializers.py` | PerdiumClaim |

### Step 5: Views & API Endpoints

**Router file:** `accounting/urls/urls.py`  
**Base URL:** `/api/` (all endpoints prefixed with `/api/acc-`)

#### 5.1 Complete Router Registry (70 resources)

| URL Prefix | ViewSet | View File |
|------------|---------|-----------|
| `/api/acc-account-types/` | AccountTypeViewSet | `account_views.py` |
| `/api/acc-account-groups/` | AccountGroupViewSet | `account_views.py` |
| `/api/acc-accounts/` | AccountViewSet | `account_views.py` |
| `/api/acc-account-tags/` | AccountTagViewSet | `account_views.py` |
| `/api/acc-fiscal-years/` | FiscalYearViewSet | `fiscal_views.py` |
| `/api/acc-fiscal-periods/` | FiscalPeriodViewSet | `fiscal_views.py` |
| `/api/acc-journals/` | JournalViewSet | `journal_views.py` |
| `/api/acc-journal-entries/` | JournalEntryViewSet | `journal_views.py` |
| `/api/acc-journal-items/` | JournalItemViewSet | `journal_views.py` |
| `/api/acc-journal-attachments/` | JournalEntryAttachmentViewSet | `journal_views.py` |
| `/api/acc-recurring-journals/` | RecurringJournalTemplateViewSet | `journal_views.py` |
| `/api/acc-vouchers/` | VoucherViewSet | `voucher_views.py` |
| `/api/acc-voucher-approvals/` | VoucherApprovalViewSet | `voucher_views.py` |
| `/api/acc-voucher-attachments/` | VoucherAttachmentViewSet | `voucher_views.py` |
| `/api/acc-payment-methods/` | PaymentMethodViewSet | `payment_views.py` |
| `/api/acc-payments/` | PaymentViewSet | `payment_views.py` |
| `/api/acc-payment-allocations/` | PaymentAllocationViewSet | `payment_views.py` |
| `/api/acc-bank-accounts/` | BankAccountViewSet | `bank_views.py` |
| `/api/acc-bank-transactions/` | BankTransactionViewSet | `bank_views.py` |
| `/api/acc-bank-reconciliations/` | BankReconciliationViewSet | `bank_views.py` |
| `/api/acc-cash-registers/` | CashRegisterViewSet | `bank_views.py` |
| `/api/acc-cash-transactions/` | CashTransactionViewSet | `bank_views.py` |
| `/api/acc-vendors/` | VendorViewSet | `payable_views.py` |
| `/api/acc-bills/` | BillViewSet | `payable_views.py` |
| `/api/acc-debit-notes/` | DebitNoteViewSet | `payable_views.py` |
| `/api/acc-vendor-credits/` | VendorCreditViewSet | `payable_views.py` |
| `/api/acc-supplier-ledger/` | SupplierLedgerViewSet (read-only) | `payable_views.py` |
| `/api/acc-customers/` | CustomerViewSet | `receivable_views.py` |
| `/api/acc-invoices/` | InvoiceViewSet | `receivable_views.py` |
| `/api/acc-credit-notes/` | CreditNoteViewSet | `receivable_views.py` |
| `/api/acc-budget-categories/` | BudgetCategoryViewSet | `budget_views.py` |
| `/api/acc-budgets/` | BudgetViewSet | `budget_views.py` |
| `/api/acc-budget-lines/` | BudgetLineViewSet | `budget_views.py` |
| `/api/acc-budget-transfers/` | BudgetTransferViewSet | `budget_views.py` |
| `/api/acc-budget-amendments/` | BudgetAmendmentViewSet (read-only) | `budget_views.py` |
| `/api/acc-tax-groups/` | TaxGroupViewSet | `tax_views.py` |
| `/api/acc-taxes/` | TaxViewSet | `tax_views.py` |
| `/api/acc-tax-rules/` | TaxRuleViewSet | `tax_views.py` |
| `/api/acc-withholding-taxes/` | WithholdingTaxViewSet | `tax_views.py` |
| `/api/acc-cost-centers/` | CostCenterViewSet | `analytics_views.py` |
| `/api/acc-analytic-plans/` | AnalyticPlanViewSet | `analytics_views.py` |
| `/api/acc-analytic-accounts/` | AnalyticAccountViewSet | `analytics_views.py` |
| `/api/acc-analytic-lines/` | AnalyticLineViewSet | `analytics_views.py` |
| `/api/acc-analytic-tags/` | AnalyticTagViewSet | `analytics_views.py` |
| `/api/acc-currencies/` | CurrencyViewSet | `currency_views.py` |
| `/api/acc-exchange-rates/` | ExchangeRateViewSet | `currency_views.py` |
| `/api/acc-report-templates/` | FinancialReportTemplateViewSet | `report_views.py` |
| `/api/acc-generated-reports/` | GeneratedReportViewSet | `report_views.py` |
| `/api/acc-number-sequences/` | NumberSequenceViewSet | `settings_views.py` |
| `/api/acc-approval-rules/` | ApprovalRuleViewSet | `settings_views.py` |
| `/api/acc-audit-logs/` | AuditLogViewSet (read-only) | `settings_views.py` |
| `/api/acc-posting-rules/` | PostingRuleViewSet | `settings_views.py` |
| `/api/acc-integration-rules/` | IntegrationRuleViewSet | `settings_views.py` |
| `/api/acc-approval-workflows/` | ApprovalWorkflowViewSet | `settings_views.py` |
| `/api/acc-lock-dates/` | LockDateViewSet | `settings_views.py` |
| `/api/acc-asset-categories/` | AssetCategoryViewSet | `asset_views.py` |
| `/api/acc-assets/` | AssetViewSet | `asset_views.py` |
| `/api/acc-asset-depreciations/` | AssetDepreciationViewSet | `asset_views.py` |
| `/api/acc-asset-disposals/` | AssetDisposalViewSet | `asset_views.py` |
| `/api/acc-asset-impairments/` | AssetImpairmentViewSet | `asset_views.py` |
| `/api/acc-asset-transfers/` | AssetTransferViewSet | `asset_views.py` |
| `/api/acc-perdium/` | PerdiumViewSet | `perdium_views.py` |
| `/api/acc-perdium-claims/` | PerdiumClaimViewSet | `perdium_claim_views.py` |
| `/api/acc-payment-terms/` | PaymentTermViewSet | `extended_views.py` |
| `/api/acc-fiscal-positions/` | FiscalPositionViewSet | `extended_views.py` |
| `/api/acc-incoterms/` | IncotermViewSet | `extended_views.py` |
| `/api/acc-reconciliation-models/` | ReconciliationModelViewSet | `extended_views.py` |
| `/api/acc-bank-statements/` | BankStatementViewSet | `extended_views.py` |
| `/api/acc-bank-statement-lines/` | BankStatementLineViewSet | `extended_views.py` |
| `/api/acc-checks/` | CheckViewSet | `extended_views.py` |
| `/api/acc-bank-transfers/` | BankTransferViewSet | `extended_views.py` |
| `/api/acc-deferred-revenue/` | DeferredRevenueViewSet | `extended_views.py` |
| `/api/acc-deferred-expenses/` | DeferredExpenseViewSet | `extended_views.py` |
| `/api/acc-customer-invoices/` | CustomerInvoiceViewSet | `customer_invoice_views.py` |
| `/api/acc-customer-receipts/` | CustomerReceiptViewSet | `workspace_views.py` |
| `/api/acc-bank-deposits/` | BankDepositViewSet | `workspace_views.py` |
| `/api/acc-supplier-payments/` | SupplierPaymentViewSet | `workspace_views.py` |
| `/api/acc-workspace-cash-transactions/` | CashWorkspaceTransactionViewSet | `workspace_views.py` |
| `/api/acc-workspace-contra-entries/` | ContraEntryViewSet | `workspace_views.py` |
| `/api/acc-workspace-expense-entries/` | ExpenseEntryViewSet | `workspace_views.py` |
| `/api/acc-workspace-payroll-entries/` | PayrollEntryViewSet | `workspace_views.py` |
| `/api/acc-workspace-inventory-entries/` | InventoryEntryViewSet | `workspace_views.py` |

#### 5.2 Non-Router Paths

| URL | View | Methods |
|-----|------|---------|
| `/api/acc-settings/` | `AccountingSettingsView` | GET, PATCH |
| `/api/acc-settings/1/` | `AccountingSettingsView` (alias) | GET, PATCH |
| `/api/acc-dashboard/` | `AccountingDashboardView` | GET |

#### 5.3 Custom Actions (verified via `@action` decorators)

| Endpoint | Method | View File |
|----------|--------|-----------|
| `/api/acc-accounts/tree/` | GET | `account_views.py` |
| `/api/acc-accounts/summary/` | GET | `account_views.py` |
| `/api/acc-accounts/seed/` | POST | `account_views.py` |
| `/api/acc-journals/seed/` | POST | `journal_views.py` |
| `/api/acc-journal-entries/{id}/post-entry/` | POST | `journal_views.py` |
| `/api/acc-journal-entries/{id}/cancel/` | POST | `journal_views.py` |
| `/api/acc-vouchers/{id}/submit-voucher/` | POST | `voucher_views.py` |
| `/api/acc-vouchers/{id}/approve-voucher/` | POST | `voucher_views.py` |
| `/api/acc-vouchers/{id}/reject-voucher/` | POST | `voucher_views.py` |
| `/api/acc-vouchers/{id}/post-voucher/` | POST | `voucher_views.py` |
| `/api/acc-bills/create-draft/` | POST | `payable_views.py` |
| `/api/acc-bills/{id}/post-bill/` | POST | `payable_views.py` |
| `/api/acc-bills/{id}/register-payment/` | POST | `payable_views.py` |
| `/api/acc-invoices/{id}/post-invoice/` | POST | `receivable_views.py` |
| `/api/acc-customer-invoices/{id}/register-payment/` | POST | `customer_invoice_views.py` |
| `/api/acc-fiscal-years/{id}/close/` | POST | `fiscal_views.py` |
| `/api/acc-budgets/{id}/validate-budget/` | POST | `budget_views.py` |
| `/api/acc-assets/{id}/run-depreciation/` | POST | `asset_views.py` |
| `/api/acc-bank-statements/{id}/auto-match/` | POST | `extended_views.py` |
| `/api/acc-workspace-*/create/` | POST | `workspace_views.py` |
| `/api/acc-workspace-*/{id}/post/` | POST | `workspace_views.py` |
| `PATCH /api/acc-{resource}/{id}/status/` | PATCH | `status_transition_mixin.py` |

### Step 6: Signals — `accounting/signals.py`

| Signal | Sender | Behavior |
|--------|--------|----------|
| `post_save` | `Voucher` | Audit log on create |
| `post_save` | `VoucherApproval` | Audit log when status = approved |
| `post_save` | `JournalEntry` | Audit log on create/post |
| `pre_save` | `Bill` | Auto-set `status=overdue` if past due date and status is `approved` or `partial` |
| `pre_save` | `Invoice` | Auto-set `status=overdue` if past due date and status is `sent` or `partial` |

### Step 7: Status Workflow — `views/status_transition_mixin.py`

Reusable `PATCH .../status/` endpoint with document-specific transition rules:

- **Bill:** `draft` → `pending`/`cancelled`; `pending` → `draft`/`approved`/`cancelled`; `overdue` → `approved`/`cancelled`; terminal: `paid`, `cancelled`
- **CustomerInvoice:** `draft` → `sent`/`cancelled`; `sent` → `posted`/`cancelled`; `posted`/`partial` → `paid`/`cancelled`; terminal: `paid`, `cancelled`
- Generic fallback for other models based on `STATUS_CHOICES` ordering

### Step 8: Journal Posting Pattern

Used across `journal_views.py`, `voucher_views.py`, `payable_views.py`, `receivable_views.py`, `workspace_views.py`:

1. Create `JournalEntry` (status = `posted`)
2. Create `JournalItem` lines (DR expense/tax, CR payable — or mirror for AR)
3. Update `Account.current_balance` per line
4. Link source document (`bill.journal_entry`, `voucher.journal_entry`, etc.)

### Step 9: Management Commands

| Command | File |
|---------|------|
| `seed_chart_of_accounts` | `management/commands/seed_chart_of_accounts.py` |
| `seed_accounting` | `management/commands/seed_accounting.py` |
| `seed_workspace` | `management/commands/seed_workspace.py` |
| `seed_new_workspace` | `management/commands/seed_new_workspace.py` |
| `seed_budgets_workspace` | `management/commands/seed_budgets_workspace.py` |
| `seed_assets_workspace` | `management/commands/seed_assets_workspace.py` |
| `seed_customer_invoices` | `management/commands/seed_customer_invoices.py` |

### Step 10: Filters

`accounting/filters/filters.py` defines FilterSets (`AccountFilter`, `JournalEntryFilter`, `BillFilter`, `InvoiceFilter`, etc.). Not all viewsets wire these; many use inline `filterset_fields` instead.

---

## 3. Frontend — Step-by-Step Analysis

### Step 1: Module Location & Layout

| Item | Path |
|------|------|
| Primary module | `src/app/dashboard/(modules)/accounting-finance/` |
| Route prefix | `/dashboard/accounting-finance` |
| Layout | `layout.jsx` wraps all pages in `CurrencyProvider` |

```jsx
// layout.jsx
import { CurrencyProvider } from './_components/currency-context';

export default function AccountingFinanceLayout({ children }) {
  return <CurrencyProvider>{children}</CurrencyProvider>;
}
```

### Step 2: Page Architecture Pattern

Every route is a **thin wrapper** that imports one component from `_components/`:

```jsx
// Example: dashboard/page.jsx
import AccountingDashboard from '../_components/dashboard';

export default function Page() {
  return <AccountingDashboard />;
}
```

**Verified page count:** 177 `page.jsx` files under `(modules)/accounting-finance/`.

### Step 3: Route Structure — `src/routes/paths.js`

Path constants defined at lines 755–991 under `paths.dashboard.accountingFinance`:

| Section | Route Base | Key Sub-routes |
|---------|-----------|----------------|
| Dashboard | `/accounting-finance/dashboard` | — |
| Configuration | `/accounting-finance/configuration/*` | COA, journals, fiscal, taxes, currencies, cost centers, budget setup, asset categories, bank/cash accounts, fiscal positions, reconciliation models, payment methods, incoterms, exchange rates, lock dates, perdium |
| Transactions | `/accounting-finance/transactions/*` | Journal entries, vouchers, GL posting, customer invoices, credit/debit notes, vendor bills, receipts, supplier payments, bank deposits, cash/contra/expense/payroll/inventory entries, journal items, deferred revenue/expenses |
| Banking | `/accounting-finance/banking/*` | Bank accounts, statements, reconciliation, transfers, check management |
| Receivables | `/accounting-finance/receivables/*` | Customer ledger, due invoices, aging, collection follow-up, statements |
| Payables | `/accounting-finance/payables/*` | Supplier ledger, unpaid bills, aging, payment schedule, statements, money receipt |
| Assets | `/accounting-finance/assets/*` | Register, acquisition, depreciation, disposal, reports |
| Budgets | `/accounting-finance/budgets/*` | Plans, lines, vs-actual, tracking |
| Reports | `/accounting-finance/reports/*` | Trial balance, balance sheet, P&L, cash flow, GL, journal report, ledgers, tax, expense, cost center, asset, budget, executive, analytic, partner, tax audit, consolidated |
| Analytic Accounting | `/accounting-finance/analytic-accounting/*` | Accounts, plans, items |
| Year-End | `/accounting-finance/year-end/*` | Closing, period lock, opening entries |
| Settings | `/accounting-finance/settings/*` | Posting rules, integration rules, approval workflow, number series, role permissions, audit log, currency rates |
| Provident Fund | `/accounting-finance/provident-fund/*` | List, create, detail |

Dynamic segments: `[id]`, `[bucket]`, `[itemId]` for detail/edit views.

### Step 4: Navigation — `src/layouts/config-nav-dashboard.jsx`

Accounting section starts at **line 1184** with title `"Accounting & Finance"` and icon `ICONS.accounting` (`solar:calculator-bold-duotone`).

**Nav groups (verified):**

1. Dashboard
2. Configuration (18 items; Account Types is commented out)
3. Transactions (17 items)
4. Banking (5 items)
5. Receivables (5 items)
6. Payables (6 items including Money Receipts)
7. Assets (5 items)
8. Budgets (5 items)
9. Reports (subset visible; many report routes exist in `paths.js` but are commented out in nav)
10. Analytic Accounting (4 items)
11. Year-End (4 items)
12. Settings (8 items)
13. Provident Fund (2 items)

**Not in nav but routable:** Travel Expense (`/transactions/travel-expence/*` — commented out in nav), several report pages, Account Types page.

### Step 5: Component Structure — `_components/`

**12 subdomain folders** (verified: 180 `.jsx` files total):

```
_components/
├── analytic-accounting/     (6 components)
├── assets/                  (7 components)
├── banking/                 (14 components)
├── budgets/                 (7 components)
├── configuration/           (47 components + 19 API hooks)
├── money-receipt/           (3 components)
├── payables/                (7 components)
├── receivables/             (7 components)
├── reports/                 (20 components)
├── settings/                (8 components)
├── shared/                  (4 components)
├── transactions/            (48 components + 17 API hooks)
├── year-end/                (5 components)
├── dashboard.jsx
├── currency-context.jsx
├── demo-data.js
└── utils.js
```

**Key large forms (verified line counts):**
- `vendor-bill-new-form.jsx` — ~1690 lines
- `customer-invoice-new-form.jsx`
- `expense-entry-new-form.jsx`

**Shared utilities:**
- `utils.js` — `formatCurrency`, date helpers, global currency sync
- `shared/status-workflow.jsx` — Status badge/step UI
- `shared/status-action-menu.jsx` — Post/approve/cancel actions
- `shared/print-layout.jsx`, `pdf-print-layout.jsx` — Print/PDF

### Step 6: API Hooks

#### 6.1 Domain API Hooks — 37 `use-*-api.js` files

| Domain | Hooks |
|--------|-------|
| **Configuration (19)** | `use-chart-of-accounts-api`, `use-account-types-api`, `use-journals-api`, `use-fiscal-year-api`, `use-fiscal-periods-api`, `use-payment-terms-api`, `use-taxes-api`, `use-currencies-api`, `use-exchange-rates-api`, `use-cost-centers-api`, `use-budget-setup-api`, `use-bank-cash-accounts-api`, `use-fiscal-positions-api`, `use-reconciliation-models-api`, `use-payment-methods-api`, `use-incoterms-api`, `use-lock-dates-api`, `use-perdium-api`, `use-perdium-claim-api` |
| **Transactions (17)** | `use-journal-entries-api`, `use-vouchers-api`, `use-vendor-bills-api`, `use-customer-invoices-api`, `use-credit-notes-api`, `use-debit-notes-api`, `use-customer-receipts-api`, `use-supplier-payments-api`, `use-bank-deposits-api`, `use-deferred-revenue-api`, `use-deferred-expenses-api`, `use-workspace-cash-api`, `use-workspace-contra-api`, `use-workspace-expense-api`, `use-workspace-payroll-api`, `use-workspace-inventory-api` |
| **Payables (1)** | `use-supplier-ledger-api` |
| **Shared (1)** | `use-transaction-status-api` |

#### 6.2 Workspace Hooks — 12 `use-*-workspace.js` files

`use-banking-workspace`, `use-budgets-workspace`, `use-assets-workspace`, `use-analytic-workspace`, `use-year-end-workspace`, `use-payables-workspace`, `use-receivables-workspace`, `use-core-ledger-config-workspace`, `use-foundational-config-workspace`, `use-planning-config-workspace`, `use-policy-config-workspace`, `use-reference-config-workspace`

### Step 7: API Integration — `src/utils/axios.js`

All accounting endpoints defined in `endpoints.accounting` (lines 1039–1356).

**Pattern:**
```js
const { data } = useSWR(endpoints.accounting.bills, fetcher);
// Mutations via axiosInstance + mutate() cache invalidation
```

**Enrichment:** Hooks like `use-vendor-bills-api.js` normalize snake_case → camelCase (`enrichBill`, `enrichBillDetail`).

**Status transitions:** `use-transaction-status-api` PATCHes `/api/acc-{resource}/{id}/status/` and revalidates SWR keys.

### Step 8: State Management

| Pattern | Where Used |
|---------|-----------|
| **SWR** | All list/detail views — server cache with `mutate` on CUD |
| **React Context** | `CurrencyProvider` in `layout.jsx` — active currency, exchange rates, `localStorage` persistence |
| **Local `useState`** | Forms, dialogs, filters — draft objects |
| **`useMemo` / `useCallback`** | Derived lists, handlers in large forms |
| **`useGetRequest`** | Some settings screens with optional `mockKey` fallback |

**Not used:** Redux, Zustand, React Query.

### Step 9: Forms & Validation

**No centralized schema library** (no Zod/Yup/react-hook-form) in the main `(modules)/accounting-finance` module.

| Approach | Examples |
|----------|----------|
| Controlled `useState` drafts | `vendor-bill-new-form.jsx`, `expense-entry-new-form.jsx` |
| MUI `TextField required` | HTML-level required props |
| Inline guards + `toast.error` | Submit handlers; API errors via `err?.response?.data?.detail` |
| API-driven selects | SWR for accounts, journals, vendors, projects, GRNs |

**Exceptions (outside main module):**
- `travel-expence/_components/TravelExpenseForm.jsx` — uses react-hook-form
- `provident-fund/_components/ProvidentFundForm.jsx` — uses react-hook-form

### Step 10: Mock / Demo Data Fallbacks

Several hooks fall back to local mock data when API returns empty:

| File | Mock data for |
|------|--------------|
| `transactions/mock-data.js` | Vouchers, debit notes, deferred expenses, cash transactions, bank deposits, journal items |
| `reports/mock-data.js` | Report data |
| `payables/mock-data.js` | Payables data |
| `receivables/mock-data.js` | Receivables data |
| `demo-data.js` | Shared `ACCOUNTING_MOCK_*` constants for config workspaces |

> **Note:** `use-vendor-bills-api.js` does **not** contain mock fallbacks (verified via grep). Vendor bills use real API integration.

---

## 4. Frontend ↔ Backend API Mapping

| Frontend Hook / Component | Backend Endpoint | Backend View |
|----------------------------|------------------|--------------|
| `use-chart-of-accounts-api` | `/api/acc-accounts/` | `AccountViewSet` |
| `use-journals-api` | `/api/acc-journals/` | `JournalViewSet` |
| `use-journal-entries-api` | `/api/acc-journal-entries/` | `JournalEntryViewSet` |
| `use-vouchers-api` | `/api/acc-vouchers/` | `VoucherViewSet` |
| `use-vendor-bills-api` | `/api/acc-bills/` | `BillViewSet` |
| `use-customer-invoices-api` | `/api/acc-customer-invoices/` | `CustomerInvoiceViewSet` |
| `use-credit-notes-api` | `/api/acc-credit-notes/` | `CreditNoteViewSet` |
| `use-debit-notes-api` | `/api/acc-debit-notes/` | `DebitNoteViewSet` |
| `use-customer-receipts-api` | `/api/acc-customer-receipts/` | `CustomerReceiptViewSet` |
| `use-supplier-payments-api` | `/api/acc-supplier-payments/` | `SupplierPaymentViewSet` |
| `use-bank-deposits-api` | `/api/acc-bank-deposits/` | `BankDepositViewSet` |
| `use-workspace-cash-api` | `/api/acc-workspace-cash-transactions/` | `CashWorkspaceTransactionViewSet` |
| `use-workspace-contra-api` | `/api/acc-workspace-contra-entries/` | `ContraEntryViewSet` |
| `use-workspace-expense-api` | `/api/acc-workspace-expense-entries/` | `ExpenseEntryViewSet` |
| `use-workspace-payroll-api` | `/api/acc-workspace-payroll-entries/` | `PayrollEntryViewSet` |
| `use-workspace-inventory-api` | `/api/acc-workspace-inventory-entries/` | `InventoryEntryViewSet` |
| `use-supplier-ledger-api` | `/api/acc-supplier-ledger/` | `SupplierLedgerViewSet` |
| `use-transaction-status-api` | `PATCH /api/acc-{resource}/{id}/status/` | `StatusTransitionMixin` |
| Dashboard component | `/api/acc-dashboard/` | `AccountingDashboardView` |
| Settings screens | `/api/acc-settings/` | `AccountingSettingsView` |

### Dual Invoice Models

| Frontend Screen | Backend Model | Customer FK |
|----------------|---------------|-------------|
| Customer Invoices (transactions workspace) | `CustomerInvoice` | `donor.Donor` |
| Core AR Invoices (if used) | `Invoice` | `accounting.Customer` |

The frontend **customer invoices workspace** maps to `CustomerInvoice`, not the core `Invoice` model.

---

## 5. Cross-Module Integrations

### 5.1 Projects

| Backend Model | FK to `projects.Project` |
|--------------|-------------------------|
| `Bill` | `project` |
| `Invoice` | `project` |
| `Voucher` | `project` |
| `Budget` | `project` |
| `CostCenter` | `project` |
| `AnalyticAccount` | `project` |
| `GeneratedReport` | `project` |

| Frontend Component | Endpoint Used |
|-------------------|---------------|
| `vendor-bill-new-form.jsx` | `endpoints.projectManagements.projects` |
| Customer invoice form | `endpoints.projects.simple_projects` |
| Vouchers | `endpoints.projectManagements.projects` |
| Perdium claim form | `endpoints.projects.projects` |

### 5.2 Procurement

| Backend Model | FK |
|--------------|-----|
| `Bill` | `procurement.PurchaseOrder`, `procurement.WorkOrder`, `procurement.GoodsReceiptNote` (FK + M2M) |

| Frontend Component | Endpoint Used |
|-------------------|---------------|
| `vendor-bill-new-form.jsx` | `endpoints.procurement_management.work_orders`, `.grns`, `.work_order_by_id(id)` |
| Debit notes API | `endpoints.procurement_management.vendors_management`, `.rfqs` |
| Supplier payments API | `endpoints.procurement_management.vendors_management`, `.rfqs` |
| Supplier ledger API | `endpoints.procurement_management.vendors_management` |

### 5.3 Donor

| Backend | Integration |
|---------|-------------|
| `CustomerInvoice.customer` | FK to `donor.Donor` |
| `CustomerReceipt` | FK to `donor.Donor` |
| `donor/signals.py` | `post_save`/`post_delete` on `CustomerInvoice` → syncs to `DonorLedger` |

Verified in `donor/signals.py`:
```python
# CustomerInvoice → DonorLedger
# post_save → sync_customer_invoice_to_donor_ledger
# post_delete → removes matching DonorLedger entries
```

### 5.4 Vendor Portal

| Backend Model | FK |
|--------------|-----|
| `Vendor.supplier` | `vendorportal.VendorProfile` |

### 5.5 Employee / HR

| Backend Model | FK |
|--------------|-----|
| `Budget.department` | `employee.Department` |
| `CostCenter.department` | `employee.Department` |
| `PerdiumClaimViewSet` | Imports `employee.models.Employee` for lookups |

### 5.6 Central Dashboard

`src/sections/central-dashboard/components/module-overview-widgets.jsx` links to `/dashboard/accounting-finance/dashboard/`.

Backend `central_dashboard` imports `accounting.Account` for balance aggregation.

---

## 6. Key Business Flows

### 6.1 Vendor Bill Lifecycle

```
┌─────────────┐    create-draft    ┌─────────┐    post-bill    ┌─────────┐
│  Frontend   │ ─────────────────► │  Bill   │ ──────────────► │ Posted  │
│  Form       │                    │ (draft) │                 │ + JE    │
└─────────────┘                    └─────────┘                 └─────────┘
                                        │
                                        │ register-payment
                                        ▼
                                   ┌─────────┐
                                   │  Paid   │
                                   │ + JE    │
                                   └─────────┘
```

1. **Create draft:** `POST /api/acc-bills/create-draft/` — links procurement PO/WO/GRN
2. **Post bill:** `POST /api/acc-bills/{id}/post-bill/` — creates journal entry (DR expense, CR payable)
3. **Register payment:** `POST /api/acc-bills/{id}/register-payment/` — creates payment + JE + SupplierPayment

### 6.2 Customer Invoice Lifecycle

```
┌─────────┐    create    ┌─────────┐    post    ┌─────────┐    register-payment    ┌─────────┐
│  Draft  │ ──────────► │  Sent   │ ────────► │ Posted  │ ─────────────────────► │  Paid   │
└─────────┘             └─────────┘           └─────────┘                          └─────────┘
```

Status transitions via `PATCH /api/acc-customer-invoices/{id}/status/` or dedicated actions.

Donor ledger sync happens on `post_save` signal.

### 6.3 Voucher Workflow

```
┌─────────┐   submit-voucher   ┌─────────┐   approve-voucher   ┌──────────┐   post-voucher   ┌─────────┐
│  Draft  │ ─────────────────► │ Pending │ ──────────────────► │ Approved │ ───────────────► │ Posted  │
└─────────┘                    └─────────┘                     └──────────┘                  │ + JE    │
                                                                                              └─────────┘
```

### 6.4 Journal Entry Posting

```
┌─────────┐   post-entry   ┌─────────┐
│  Draft  │ ─────────────► │ Posted  │
└─────────┘                │ + update│
                           │ balances│
                           └─────────┘
```

Updates `Account.current_balance` for each `JournalItem` line.

### 6.5 Workspace Transaction Posting

Pattern for cash/contra/expense/payroll/inventory entries:

1. `POST /api/acc-workspace-{type}/create/` — create draft
2. `POST /api/acc-workspace-{type}/{id}/post/` — post to journal

---

## 7. Authentication & Permissions

### Backend

| Setting | Value | Source |
|---------|-------|--------|
| `DEFAULT_AUTHENTICATION_CLASSES` | `JWTAuthentication`, `SessionAuthentication` | `core/settings.py:148-150` |
| `DEFAULT_PERMISSION_CLASSES` | `AllowAny` | `core/settings.py:152-154` |
| Accounting viewsets | `permission_classes = [IsAuthenticated]` | All 21 view files (verified via grep) |

**Implications:**
- All `/api/acc-*` endpoints require a valid JWT or session token
- No role-based or object-level permissions in accounting views
- `AuditLogViewSet`, `SupplierLedgerViewSet`, `BudgetAmendmentViewSet` are read-only

### Frontend

Authentication handled at app level via JWT tokens in axios interceptors (not module-specific).

---

## 8. Legacy / Parallel Codebases

### 8.1 Legacy Routes (outside `(modules)`)

| Path | File | Component Source |
|------|------|-----------------|
| `/dashboard/accounting` | `src/app/dashboard/accounting/page.jsx` | `sections/mis-accounting` |
| `/dashboard/accounting/chart-of-accounts` | `.../chart-of-accounts/page.jsx` | `sections/accounting/chart-of-accounts` |
| `/dashboard/accounting/financial-reports` | `.../financial-reports/page.jsx` | Legacy section |
| `/dashboard/accounting/voucher-management` | `.../voucher-management/page.jsx` | Legacy section |
| `/dashboard/accounting/accounts-payable` | `.../accounts-payable/page.jsx` | Legacy section |
| `/dashboard/accounting/bank-reconciliation` | `.../bank-reconciliation/page.jsx` | Legacy section |

### 8.2 Legacy Sections — `src/sections/accounting/`

6 files:
- `accounting-dashboard/accounting-dashboard-main.jsx`
- `chart-of-accounts/chart-of-accounts-main.jsx`
- `financial-reports/financial-reports-main.jsx`
- `voucher-management/voucher-management-main.jsx`
- `accounts-payable/accounts-payable-main.jsx`
- `bank-reconciliation/bank-reconciliation-main.jsx`

### 8.3 Standalone Forms

| Path | Re-exports From |
|------|----------------|
| `/accounting-finance/transactions/customer-invoices/new` | `(standalone-forms)/...` → main `_components` |
| `/accounting-finance/transactions/expense-entries/new` | `(standalone-forms)/...` → main `_components` |

### 8.4 Self-Contained Sub-modules (outside `(modules)`)

| Module | Path | Own `_components` |
|--------|------|----------------|
| Provident Fund | `/dashboard/accounting-finance/provident-fund/*` | Yes |
| Travel Expense | `/dashboard/accounting-finance/transactions/travel-expence/*` | Yes (commented out in nav) |

**Recommendation:** Use `(modules)/accounting-finance` for new development.

---

## 9. Verified File Counts

| Category | Count | Location |
|----------|-------|----------|
| Backend total files | 78 | `accounting/` |
| Backend model classes | 101 | `accounting/models/*.py` |
| Backend view files | 22 + mixin | `accounting/views/` |
| Backend serializer files | 20 | `accounting/serializers/` |
| Backend router registrations | 70 | `accounting/urls/urls.py` |
| Backend non-router paths | 3 | `accounting/urls/urls.py` |
| Frontend pages | 177 | `(modules)/accounting-finance/**/page.jsx` |
| Frontend components | 180 | `(modules)/accounting-finance/_components/**/*.jsx` |
| Frontend API hooks | 37 | `use-*-api.js` |
| Frontend workspace hooks | 12 | `use-*-workspace.js` |
| Frontend axios endpoints | ~150+ | `endpoints.accounting` in `axios.js` |
| Legacy section files | 6 | `src/sections/accounting/` |

---

## 10. বাংলা সারাংশ

### ব্যাকএন্ড

`accounting` একটি বড় Odoo-স্টাইল Django অ্যাপ (~১০১ মডেল ক্লাস, ৭৮ ফাইল) যা `/api/acc-*` URL-এ মাউন্ট করা। মূল অংশগুলো:

- **চার্ট অফ অ্যাকাউন্টস** — AccountType, AccountGroup, Account, AccountTag
- **জার্নাল/ভাউচার** — Journal, JournalEntry, Voucher
- **AP/AR** — Bill, Invoice, CustomerInvoice (আলাদা workspace মডেল)
- **ব্যাংকিং** — BankAccount, reconciliation, cash registers
- **বাজেট** — Budget, BudgetLine, transfers
- **ট্যাক্স, অ্যানালিটিক্স, অ্যাসেট, ওয়ার্কস্পেস ট্রানজেকশন**

সব ভিউতে `IsAuthenticated` আছে; গ্লোবালি `AllowAny`। ব্যবসায়িক লজিক মূলত ভিউ `@action`, মডেল `save()`, এবং `signals.py`-তে। আলাদা `services/` লেয়ার নেই।

### ফ্রন্টএন্ড

অ্যাকাউন্টিং মডিউল মূলত `src/app/dashboard/(modules)/accounting-finance/` এ আছে:

- **১৭৭টি** `page.jsx` রুট
- **১৮০টি** `_components` JSX ফাইল
- **৩৭টি** API হুক (SWR + axios)
- **১২টি** workspace হুক

রুট প্রিফিক্স: `/dashboard/accounting-finance/...`

স্টেট ম্যানেজমেন্ট: SWR, লোকাল `useState`, `CurrencyProvider` — Redux/Zustand নেই।

ভ্যালিডেশন: মূলত ম্যানুয়াল; Zod/Yup নেই (travel expense/provident fund ছাড়া)।

### অন্যান্য মডিউলের সাথে সংযোগ

| মডিউল | সংযোগ |
|-------|-------|
| **Projects** | Bill, Invoice, Budget, CostCenter এ FK |
| **Procurement** | Bill এ PO/WO/GRN লিংক; vendor bill form এ API কল |
| **Donor** | CustomerInvoice → DonorLedger সিগন্যাল সিঙ্ক |
| **Vendor Portal** | Vendor.supplier FK |
| **Employee** | Budget/CostCenter এ Department FK |

### পুরনো কোডবেস

`src/app/dashboard/accounting/*` এবং `src/sections/accounting/` এখনও আছে — নতুন কাজের জন্য `(modules)/accounting-finance` ব্যবহার করুন।

---

*End of document.*
