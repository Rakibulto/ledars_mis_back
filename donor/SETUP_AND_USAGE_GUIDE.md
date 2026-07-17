# Donor Ledger Integration - Setup and Usage Guide

## Quick Start

### 1. Verify Installation
The donor ledger synchronization system is fully integrated. Just verify:

```bash
# Check Django configuration
python manage.py check

# You should see:
# System check identified no issues (0 silenced).
```

### 2. Enable Signal Handlers
Signals are automatically enabled when the Django app starts. No additional configuration needed!

The app's `ready()` method in `donor/apps.py` automatically calls `register_signals()` which connects:
- `accounting.CustomerInvoice` post_save/post_delete signals
- `procurement.MaterialRequisition` post_save/post_delete signals  
- `beneficiary.DistributionPlan` post_save/post_delete signals

### 3. Test the System
Run the test suite to verify signals work:

```bash
# Run all donor tests
python manage.py test donor

# Run only ledger signal tests
python manage.py test donor.tests.DonorLedgerSignalTests

# Or run the custom test script
python test_ledger_sync.py
```

### 4. Generate Initial Ledgers (First Time Setup)
If you have existing transactions before signals were activated:

```bash
# Generate ledgers for all donors
python manage.py generate_donor_ledgers

# Generate for specific donor
python manage.py generate_donor_ledgers --donor-id 5

# Regenerate from scratch (delete and recreate)
python manage.py generate_donor_ledgers --clean
```

## How It Works

### Automatic Ledger Generation
When a user creates a transaction with a donor, the system automatically creates a ledger entry:

```
User creates CustomerInvoice with donor FK
    ↓
Django post_save signal triggered
    ↓
Signal handler in donor/signals.py catches it
    ↓
Extracts donor, amount, and transaction details
    ↓
Creates DonorLedger entry (or updates if exists)
    ↓
Ledger appears in Donor detail page Collection tab
```

### Supported Transaction Types

| Transaction | Module | Reference Format | Amount |
|-----------|--------|------------------|---------|
| Customer Invoice | Accounting | `Invoice-{invoice_number}` | `invoice.total_amount` |
| Material Requisition | Procurement | `MatReq-{requisition_id}` | Sum of approval step estimated costs |
| Distribution Plan | Beneficiary | `DistPlan-{plan_id}` | `quantity × unit_cost` |
| Project Management Expense | Project Management | `ProjectExp-{expense_id}` | Sum of expense items |

### API Endpoints

```bash
# List all ledger entries
GET /api/donor-ledgers/

# List ledger entries for a specific donor
GET /api/donor-ledgers/?donor=5

# Filter by transaction type
GET /api/donor-ledgers/?donor=5&transaction_type=donation

# Get single ledger entry
GET /api/donor-ledgers/123/

# Create ledger entry (manual)
POST /api/donor-ledgers/
{
  "donor": 5,
  "transaction_type": "donation",
  "amount": "5000.00",
  "currency": "USD",
  "description": "Test entry",
  "transaction_date": "2024-01-15"
}
```

## Frontend Integration

The frontend automatically displays ledger data in the Donor Detail page:

**Path**: `/dashboard/projects/donors/[id]/page.jsx`

**Collection Tab shows:**
1. Ledger entries table with:
   - Transaction date
   - Type (donation, refund, adjustment, etc.)
   - Reference (Invoice-123, MatReq-456, etc.)
   - Description
   - Amount
   - Running balance
   - Related project

2. Summary section with:
   - Total received
   - Total distributed  
   - Net balance

## Management Commands

### Generate Donor Ledgers

```bash
# Full syntax
python manage.py generate_donor_ledgers [options]

# Options:
#   --donor-id ID     Process only donor with ID
#   --clean           Delete existing ledgers before generating
#   -v VERBOSITY      Set verbosity (0=quiet, 3=very verbose)
```

**Examples:**

```bash
# Generate for all donors
python manage.py generate_donor_ledgers -v 2

# Generate for one donor
python manage.py generate_donor_ledgers --donor-id 5 -v 2

# Regenerate from scratch (careful!)
python manage.py generate_donor_ledgers --clean

# Regenerate for one donor from scratch
python manage.py generate_donor_ledgers --donor-id 5 --clean
```

## Troubleshooting

### Issue: Ledger entries not appearing for new transactions
**Solution**: 
1. Check signals are registered:
```python
python manage.py shell
>>> from django.db.models import signals
>>> from accounting.models import CustomerInvoice
>>> receivers = signals.post_save._live_receivers(CustomerInvoice)
>>> print(len(receivers))  # Should be > 0
```

2. Check database:
```sql
SELECT * FROM donor_donorledger WHERE donor_id = 5;
```

3. Manually trigger generation:
```bash
python manage.py generate_donor_ledgers --donor-id 5
```

### Issue: Duplicate ledger entries
**Solution**:
```bash
# The system uses update_or_create with (donor, reference) key
# So duplicates shouldn't happen, but if they do:

python manage.py generate_donor_ledgers --donor-id 5 --clean
```

### Issue: Ledger amount doesn't match transaction
**Possible causes:**
- Amount field is null in transaction model
- Calculation logic doesn't match (check signals.py)
- Related approval steps/items not created yet

**Solution:**
```bash
# Regenerate ledger for affected donor
python manage.py generate_donor_ledgers --donor-id 5
```

### Issue: "ModuleNotFoundError" or "ImportError" when signals run
**Cause**: One of the related modules (accounting, procurement, beneficiary) isn't installed

**Solution**: 
- Check settings.py INSTALLED_APPS includes all required apps
- Check no circular imports in those modules
- See signal registration in donor/apps.py - it has try-except for safety

## Development Guide

### Understanding the Code

**donor/signals.py**: Contains signal handlers
- `sync_customer_invoice_to_donor_ledger()` - Watches accounting.CustomerInvoice
- `sync_material_requisition_to_donor_ledger()` - Watches procurement.MaterialRequisition
- `sync_distribution_plan_to_donor_ledger()` - Watches beneficiary.DistributionPlan
- `register_signals()` - Dynamically registers all signal handlers

**donor/apps.py**: Registers signals when app is ready
- Calls `register_signals()` in `ready()` method
- Avoids circular imports by using try-except

**donor/management/commands/generate_donor_ledgers.py**: One-time bulk generation
- Scans related models for existing transactions
- Creates ledger entries for missing references
- Supports --clean flag to regenerate

### Adding Support for New Transaction Types

To add ledger support for a new transaction type:

1. **Add signal handler in `donor/signals.py`:**
```python
@receiver(post_save, sender=None)
def sync_new_model_to_donor_ledger(sender, instance, created, **kwargs):
    if sender.__name__ != 'NewModel':
        return
    
    donor = getattr(instance, 'donor', None)
    if not donor:
        return
    
    amount = getattr(instance, 'amount_field', Decimal('0.00'))
    
    DonorLedger.objects.update_or_create(
        donor=donor,
        reference=f'NewModel-{instance.id}',
        defaults={
            'transaction_type': 'donation',
            'amount': amount,
            'currency': donor.currency or 'USD',
            'description': 'Description',
            'transaction_date': instance.created_at,
        }
    )
```

2. **Register in `register_signals()` function:**
```python
def register_signals():
    # ... existing code ...
    try:
        from newmodule.models import NewModel
        post_save.connect(
            sync_new_model_to_donor_ledger,
            sender=NewModel,
            weak=False,
            dispatch_uid='sync_new_model_to_donor_ledger',
        )
    except ImportError:
        pass
```

3. **Add to management command `generate_donor_ledgers.py`:**
```python
def generate_ledger_from_new_model(self, donor):
    """Generate ledger entries from new model."""
    try:
        from newmodule.models import NewModel
    except ImportError:
        return
    
    items = NewModel.objects.filter(donor=donor)
    for item in items:
        self._create_or_update_ledger(
            donor=donor,
            transaction_type='donation',
            amount=item.amount,
            reference=f'NewModel-{item.id}',
            description=f'New Model: {item.description}',
            related_project=getattr(item, 'project_name', ''),
            transaction_date=item.created_at,
        )
```

### Testing New Features

```python
# In donor/tests.py or test_ledger_sync.py
def test_new_model_creates_ledger(self):
    from newmodule.models import NewModel
    
    item = NewModel.objects.create(
        donor=self.donor,
        amount=Decimal('1000.00'),
        # ... other fields ...
    )
    
    ledger = DonorLedger.objects.get(reference=f'NewModel-{item.id}')
    self.assertEqual(ledger.donor, self.donor)
    self.assertEqual(ledger.amount, Decimal('1000.00'))
```

## Performance Optimization

### For Bulk Imports
If importing thousands of transactions, disable signals temporarily:

```python
from django.db.models.signals import post_save
from accounting.models import CustomerInvoice

# Disable signals
post_save.disconnect(dispatch_uid='sync_customer_invoice_to_donor_ledger')

# ... bulk import code ...

# Reconnect signals
post_save.connect(
    sync_customer_invoice_to_donor_ledger,
    sender=CustomerInvoice,
    weak=False,
    dispatch_uid='sync_customer_invoice_to_donor_ledger',
)

# Generate ledgers in batch
call_command('generate_donor_ledgers', '--clean')
```

### For Large Databases
Running `generate_donor_ledgers` on millions of transactions:

```bash
# Add --donor-id to process one donor at a time
for id in {1..1000}; do
    python manage.py generate_donor_ledgers --donor-id $id --clean
done
```

## Configuration

No configuration required! The system works out of the box.

Optional environment variables (if needed):
```bash
# None currently - all settings are hardcoded in models
```

## Monitoring

### Check Signal Health
```python
from django.db.models.signals import receivers
from accounting.models import CustomerInvoice
from donor.signals import sync_customer_invoice_to_donor_ledger

# List all receivers for CustomerInvoice post_save
receivers = receivers(CustomerInvoice, signal=post_save)
print(f"Active receivers: {len(receivers)}")
for receiver in receivers:
    print(f"  - {receiver.__name__}")
```

### Verify Ledger Consistency
```python
from django.db.models import Count
from accounting.models import CustomerInvoice
from donor.models import DonorLedger

# Count invoices vs ledger entries
invoice_count = CustomerInvoice.objects.filter(donor__isnull=False).count()
ledger_count = DonorLedger.objects.filter(reference__startswith='Invoice-').count()

print(f"Invoices: {invoice_count}")
print(f"Ledger entries: {ledger_count}")

if invoice_count != ledger_count:
    print("⚠️  Mismatch detected - run: python manage.py generate_donor_ledgers --clean")
```

## Next Steps

1. ✅ Deploy donor module with ledger sync system
2. ✅ Test signals work with existing transactions
3. ✅ Run `generate_donor_ledgers` to populate initial data
4. ✅ Verify frontend Collection tab displays ledgers
5. Future: Add reconciliation workflow (approve/reject ledger entries)
6. Future: Add financial reports (PDF export, dashboard charts)
7. Future: Add Celery tasks for very large-scale batch processing
