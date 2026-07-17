# Donor Ledger Synchronization System

## Overview

The Donor Ledger Synchronization System automatically tracks all donor-related financial transactions across the LEDARS platform. This system maintains a complete audit trail of all donor activity including contributions, allocations, and distributions.

## Architecture

### 1. Real-Time Signal Handlers (`donor/signals.py`)

Signal handlers automatically create or update `DonorLedger` entries when related transactions are created or deleted:

- **CustomerInvoice** (Accounting Module)
  - Triggered when: Invoice is created with a donor FK
  - Ledger Entry Type: `donation`
  - Amount: `invoice.total_amount`
  - Reference: `Invoice-{invoice_number}`

- **MaterialRequisition** (Procurement Module)
  - Triggered when: Requisition is created with a donor FK
  - Ledger Entry Type: `donation`
  - Amount: Sum of estimated costs from approval steps
  - Reference: `MatReq-{requisition_id}`

- **DistributionPlan** (Beneficiary Module)
  - Triggered when: Distribution plan is created for a project with donor FK
  - Ledger Entry Type: `donation`
  - Amount: `total_quantity × unit_cost`
  - Reference: `DistPlan-{plan_id}`

### 2. Management Command (`donor/management/commands/generate_donor_ledgers.py`)

One-time command to generate ledger entries for existing transactions. Useful when:
- Setting up the system for the first time
- Recovering deleted ledger entries
- Recalculating balances

**Usage:**

```bash
# Generate ledgers for all donors
python manage.py generate_donor_ledgers

# Generate for a specific donor
python manage.py generate_donor_ledgers --donor-id 5

# Clear and regenerate (be careful!)
python manage.py generate_donor_ledgers --clean
```

### 3. Signal Registration (`donor/apps.py`)

Signals are registered automatically when the Django app starts:

```python
def ready(self):
    from .signals import register_signals
    register_signals()
```

This approach avoids circular imports by dynamically importing related models from other apps.

## Data Flow

### Creating a New Transaction

```
1. User creates CustomerInvoice/MaterialRequisition/DistributionPlan with donor FK
        ↓
2. Model is saved to database
        ↓
3. post_save signal is triggered (registered in donor/signals.py)
        ↓
4. Signal handler extracts donor and transaction details
        ↓
5. DonorLedger.objects.update_or_create() is called
        ↓
6. New ledger entry appears in Donor Collection tab (frontend)
```

### Deleting a Transaction

```
1. User deletes CustomerInvoice/MaterialRequisition/DistributionPlan
        ↓
2. post_delete signal is triggered
        ↓
3. Signal handler deletes corresponding DonorLedger entry (using reference)
        ↓
4. Ledger entry removed from Donor Collection tab
```

## Ledger Entry Fields

Each `DonorLedger` entry contains:

| Field | Source | Example |
|-------|--------|---------|
| `donor` | FK to Donor | Donor ID |
| `ledger_code` | Auto-generated | DL-2024-001 |
| `transaction_type` | Predefined | 'donation', 'refund', 'adjustment', 'credit', 'debit' |
| `transaction_date` | From related model | Invoice date, requisition date, etc. |
| `amount` | From related model | Total invoice amount, requisition cost, etc. |
| `currency` | From Donor.currency | USD, GBP, etc. |
| `reference` | Generated | `Invoice-12345`, `MatReq-67890`, `DistPlan-11111` |
| `description` | From related model | "Customer Invoice", "Material Requisition", etc. |
| `related_project` | Optional | Project name if available |
| `balance` | Calculated | Running total (can be computed from query aggregation) |
| `is_reconciled` | Manual | Whether ledger has been verified |

## Cross-Module Integration

### Accounting Module
- **Model**: `accounting.models.CustomerInvoice`
- **Connection**: FK `donor` field
- **Ledger Impact**: Creates `donation` entry when invoice total is > 0

### Procurement Module
- **Model**: `procurement.models.MaterialRequisition`
- **Connection**: FK `donor` field
- **Ledger Impact**: Creates `donation` entry for sum of estimated approval costs

### Beneficiary Module
- **Model**: `beneficiary.models.DistributionPlan`
- **Connection**: Indirect via `project.donor` FK
- **Ledger Impact**: Creates `donation` entry for plan quantity × unit cost

### Inventory Module
- **Models**: `DonorFundedInventory`, `CommodityTracking`
- **Connection**: Text field `donor_name` (not FK, so no signal integration)
- **Ledger Impact**: Would require manual entry or command-line batch processing

### Project Management Module
- **Model**: `project_managements.models.ProjectManagementExpense`
- **Connection**: FK `donor` field
- **Ledger Impact**: Creates `donation` entries for expense items

## Calculation Logic

### Balance Calculation

Frontend component queries:
```sql
SELECT *, SUM(amount) OVER (ORDER BY transaction_date, id) as running_balance
FROM donor_donorledger
WHERE donor_id = ?
ORDER BY transaction_date DESC
```

### Amount Extraction by Model Type

| Model | Amount Calculation |
|-------|-------------------|
| CustomerInvoice | `invoice.total_amount` |
| MaterialRequisition | `SUM(approval_step.estimated_cost)` |
| DistributionPlan | `plan.total_quantity × plan.unit_cost` |
| ProjectManagementExpense | `SUM(item.amount)` |

## Avoiding Duplicates

The signal handlers use `DonorLedger.objects.update_or_create()` with a unique `(donor, reference)` constraint to ensure:
- Multiple saves of the same transaction update the entry rather than creating duplicates
- Each transaction has exactly one ledger entry
- Changes to transaction amount/description are reflected in the ledger

## Error Handling

All signal handlers include try-except blocks to:
- Gracefully handle missing related models (ImportError)
- Continue execution even if a ledger entry creation fails
- Prevent signals from breaking the main transaction workflow

## Performance Considerations

### Signal Performance
- Signals execute synchronously within the transaction
- For bulk operations (e.g., importing 1000 invoices), consider using `bulk_create()` with `post_save` disabled
- For very large datasets, use the management command instead of signals

### Optimization Tips

1. **Disable signals during bulk imports:**
   ```python
   from django.db.models.signals import post_save
   from django.dispatch import receiver
   
   # In bulk import code
   post_save.disconnect(sync_customer_invoice_to_donor_ledger, sender=CustomerInvoice)
   # ... bulk create ...
   post_save.connect(sync_customer_invoice_to_donor_ledger, sender=CustomerInvoice, weak=False)
   ```

2. **Run management command for non-urgent bulk population:**
   ```bash
   python manage.py generate_donor_ledgers
   ```

3. **Periodic reconciliation:**
   ```bash
   # Recalculate ledgers monthly
   python manage.py generate_donor_ledgers --clean
   ```

## Frontend Integration

The Donor Detail page Collection tab (`src/app/dashboard/projects/donors/[id]/page.jsx`) displays:

1. **Ledger Table** with columns:
   - Transaction Date
   - Transaction Type
   - Reference
   - Description
   - Amount
   - Balance (calculated)
   - Project

2. **Filters** (optional enhancements):
   - Date range filter
   - Transaction type filter
   - Search by reference

3. **Totals** (footer):
   - Total Received
   - Total Distributed
   - Net Balance

## Troubleshooting

### Issue: Ledger entries not appearing

**Solution 1**: Check if signals are registered
```bash
python manage.py shell
>>> from django.db.models.signals import receivers
>>> from accounting.models import CustomerInvoice
>>> receivers(CustomerInvoice)  # Should show sync handlers
```

**Solution 2**: Manually run generation command
```bash
python manage.py generate_donor_ledgers --donor-id 5
```

### Issue: Duplicate ledger entries

**Solution**: Delete and regenerate
```bash
python manage.py generate_donor_ledgers --donor-id 5 --clean
```

### Issue: Signal not triggering for new transactions

**Check**: Does the transaction model have a `donor` FK field?
```python
# In models.py
donor = models.ForeignKey(Donor, on_delete=models.PROTECT, null=True, blank=True)
```

## Future Enhancements

1. **Batch Processing**: Implement Celery tasks for high-volume ledger generation
2. **Audit Trail**: Track who created/modified ledger entries
3. **Reconciliation Workflow**: Add approval/rejection states for ledger entries
4. **Export**: Generate financial reports (PDF, Excel) from ledger data
5. **Analytics**: Dashboard showing donor contribution trends
6. **Text Field Integration**: Create ledger entries from `donor_name` text fields (DonorFundedInventory, CommodityTracking)

## Testing

### Unit Tests

```python
# In donor/tests.py
from django.test import TestCase
from accounting.models import CustomerInvoice
from donor.models import Donor, DonorLedger

class DonorLedgerSignalTest(TestCase):
    def test_ledger_created_on_invoice_save(self):
        donor = Donor.objects.create(name='Test Donor')
        invoice = CustomerInvoice.objects.create(
            donor=donor,
            total_amount=1000,
            invoice_number='INV-001'
        )
        
        ledger = DonorLedger.objects.get(reference='Invoice-INV-001')
        self.assertEqual(ledger.donor, donor)
        self.assertEqual(ledger.amount, 1000)
```

### Integration Tests

Use the management command to validate cross-module data:
```bash
python manage.py generate_donor_ledgers --donor-id 5
# Verify ledger entries created for each transaction type
```

## API Reference

### List Donor Ledgers

```bash
GET /api/donor-ledgers/?donor=5
```

### Filter Ledgers

```bash
GET /api/donor-ledgers/?donor=5&transaction_type=donation&start_date=2024-01-01&end_date=2024-12-31
```

### Calculate Balance

```python
from django.db.models import Sum
from donor.models import DonorLedger

total = DonorLedger.objects.filter(donor_id=5).aggregate(Sum('amount'))['amount__sum'] or 0
```

## References

- Django Signals Documentation: https://docs.djangoproject.com/en/stable/topics/signals/
- Donor Model: `donor/models.py`
- Signal Handlers: `donor/signals.py`
- Management Command: `donor/management/commands/generate_donor_ledgers.py`
