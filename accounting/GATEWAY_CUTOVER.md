# Accounts Gateway — Production Cutover Checklist

## Staging setup

1. `python manage.py migrate accounting`
2. `python manage.py seed_chart_of_accounts` (if CoA empty)
3. `python manage.py seed_accounting` (journals / settings / fiscal year)
4. Ensure at least one active NGO project exists (`/api/ngo-projects/`)
5. Create Bank/Cash under **Accounts (Tally) → Masters → Bank / Cash** with CoA link
6. Open Gateway → select project → post Payment + Receipt + Journal vouchers
7. Verify:
   - Day Book shows JE
   - Cash/Bank Book matches bank balance
   - Trial Balance / P&L / Balance Sheet / Project Statement load (no mock)
8. Reverse one posted voucher; bank balance restores
9. `python manage.py check_balance_integrity` → no drift
10. `python manage.py test accounting.tests`

## Production cutover

1. Deploy backend + frontend together
2. Run migrate
3. UAT sign-off with accountants (PV/RV/JV day)
4. After UAT: set `AccountingSettings.use_ngo_project_required = true` via API `/api/acc-settings/` or admin
5. Train users: daily books on **Accounts (Tally)**; advanced AP/AR/assets on **Accounting & Finance (Advanced)**
6. Schedule nightly: `python manage.py check_balance_integrity` (alert on drift; use `--fix` only after review)

## QA matrix

| Case | Expected |
|------|----------|
| Unbalanced voucher | Reject with clear message |
| Locked period / lock date | Reject |
| Double post | Reject `already_posted` |
| Active bank without CoA | Create/update rejected |
| Project filter | Reports isolate to selected NGO project |
| Payment post | Bank book ↓, expense ↑, TB updates |
| Receipt post | Bank book ↑ |
| Reverse posted | Status cancelled; bank restored; reverse JE created |

## বাংলা সংক্ষেপ

স্টেজিংয়ে migrate + seed করে Gateway-এ প্রজেক্ট সিলেক্ট করে voucher পোস্ট করুন। ব্যাংক বই ও রিপোর্ট মিলিয়ে দেখুন। UAT পরে `use_ngo_project_required` চালু করুন এবং রাতে `check_balance_integrity` চালান।
