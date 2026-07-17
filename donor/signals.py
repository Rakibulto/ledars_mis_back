"""
Signal handlers for automatic DonorLedger synchronization.

These signals watch related models (CustomerInvoice, MaterialRequisition, etc.)
and automatically create/update corresponding DonorLedger entries when transactions
are created or modified.

They also keep Donor.total_donated_amount and Donor.last_donation_date in sync
whenever any DonorLedger entry is saved or deleted.
"""

from decimal import Decimal
from django.db.models.signals import post_save, post_delete
from django.db.models import Sum
from django.dispatch import receiver
from django.utils import timezone

from .models import Donor, DonorLedger


# ---------------------------------------------------------------------------
# Donor aggregate sync
# ---------------------------------------------------------------------------

def _sync_donor_totals(donor):
    """
    Recompute and persist total_donated_amount and last_donation_date
    directly from the donor's ledger entries.

    Uses .update() to avoid triggering Donor.save() signals and to skip
    the donor_code generation logic in Donor.save().
    """
    qs = DonorLedger.objects.filter(donor=donor, transaction_type="donation")

    total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    last_date = (
        qs.order_by("-transaction_date")
        .values_list("transaction_date", flat=True)
        .first()
    )

    Donor.objects.filter(pk=donor.pk).update(
        total_donated_amount=total,
        last_donation_date=last_date,
    )


@receiver(post_save, sender=DonorLedger)
def donor_ledger_saved(sender, instance, **kwargs):
    """Keep Donor totals in sync whenever a DonorLedger entry is created or updated."""
    _sync_donor_totals(instance.donor)


@receiver(post_delete, sender=DonorLedger)
def donor_ledger_deleted(sender, instance, **kwargs):
    """Keep Donor totals in sync whenever a DonorLedger entry is deleted."""
    _sync_donor_totals(instance.donor)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_import(module_path):
    """Safely import a model to avoid circular imports."""
    try:
        parts = module_path.rsplit('.', 1)
        module = __import__(parts[0], fromlist=[parts[1]])
        return getattr(module, parts[1], None)
    except (ImportError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# CustomerInvoice → DonorLedger
# ---------------------------------------------------------------------------

@receiver(post_save, sender=None)
def sync_customer_invoice_to_donor_ledger(sender, instance, created, **kwargs):
    """Create DonorLedger entry when a CustomerInvoice is created with a donor."""
    if sender.__name__ != 'CustomerInvoice':
        return

    donor = getattr(instance, 'customer', None)
    if not donor:
        return

    amount = getattr(instance, 'total', Decimal('0.00')) or Decimal('0.00')
    if amount <= 0:
        return

    transaction_date = getattr(instance, 'date', None) or timezone.now()
    reference = f'Invoice-{instance.number}'
    description = 'Customer Invoice'

    # CustomerInvoice has no project FK; related_project must be None.
    related_project = None

    DonorLedger.objects.update_or_create(
        donor=donor,
        reference=reference,
        defaults={
            'transaction_type': 'donation',
            'amount': amount,
            'currency': donor.currency or 'USD',
            'description': description,
            'transaction_date': transaction_date,
            'related_project': related_project,
        },
    )


# ---------------------------------------------------------------------------
# MaterialRequisition → DonorLedger
# ---------------------------------------------------------------------------

@receiver(post_save, sender=None)
def sync_material_requisition_to_donor_ledger(sender, instance, created, **kwargs):
    """Create DonorLedger entry when a MaterialRequisition is created with a donor."""
    if sender.__name__ != 'MaterialRequisition':
        return

    donor = getattr(instance, 'donor_code', None)
    if not donor:
        return

    total_cost = getattr(instance, 'total_amount', Decimal('0.00')) or Decimal('0.00')
    if total_cost <= 0:
        return

    transaction_date = getattr(instance, 'created_at', None) or timezone.now()
    reference = f'MatReq-{instance.id}'
    description = getattr(instance, 'purpose', None) or 'Material Requisition'

    # related_project is a ForeignKey to ProjectManagementProject — use the FK instance.
    related_project = getattr(instance, 'project', None)

    DonorLedger.objects.update_or_create(
        donor=donor,
        reference=reference,
        defaults={
            'transaction_type': 'donation',
            'amount': total_cost,
            'currency': donor.currency or 'USD',
            'description': description,
            'transaction_date': transaction_date,
            'related_project': related_project,
        },
    )


# ---------------------------------------------------------------------------
# DistributionPlan → DonorLedger
# ---------------------------------------------------------------------------

@receiver(post_save, sender=None)
def sync_distribution_plan_to_donor_ledger(sender, instance, created, **kwargs):
    """Create DonorLedger entry when a DistributionPlan is created for a donor's project."""
    if sender.__name__ != 'DistributionPlan':
        return

    project = getattr(instance, 'project', None)
    if not project:
        return

    donor = getattr(project, 'donor', None)
    if not donor:
        return

    # DistributionPlan has no quantity/cost fields — skip if amount cannot be
    # determined (no crash, just no ledger entry).
    amount = Decimal('0.00')
    if amount <= 0:
        return

    transaction_date = getattr(instance, 'created_at', None) or timezone.now()
    reference = f'DistPlan-{instance.id}'
    description = f'Distribution Plan: {getattr(instance, "name", "")}'

    # DistributionPlan.project is a FK to projects.Project, not
    # ProjectManagementProject.  DonorLedger.related_project expects the
    # latter, so pass None to avoid a ValueError.
    DonorLedger.objects.update_or_create(
        donor=donor,
        reference=reference,
        defaults={
            'transaction_type': 'donation',
            'amount': amount,
            'currency': donor.currency or 'USD',
            'description': description,
            'transaction_date': transaction_date,
            'related_project': None,
        },
    )


# ---------------------------------------------------------------------------
# Cascade delete: remove DonorLedger when source record is deleted
# ---------------------------------------------------------------------------

@receiver(post_delete, sender=None)
def sync_delete_to_donor_ledger(sender, instance, **kwargs):
    """Delete corresponding DonorLedger entry when a source transaction is deleted."""
    if sender.__name__ not in ['CustomerInvoice', 'MaterialRequisition', 'DistributionPlan']:
        return

    if sender.__name__ == 'CustomerInvoice':
        reference = f'Invoice-{instance.number}'
    elif sender.__name__ == 'MaterialRequisition':
        reference = f'MatReq-{instance.id}'
    elif sender.__name__ == 'DistributionPlan':
        reference = f'DistPlan-{instance.id}'
    else:
        return

    if sender.__name__ == 'DistributionPlan':
        project = getattr(instance, 'project', None)
        donor = getattr(project, 'donor', None) if project else None
    elif sender.__name__ == 'CustomerInvoice':
        donor = getattr(instance, 'customer', None)
    elif sender.__name__ == 'MaterialRequisition':
        donor = getattr(instance, 'donor_code', None)
    else:
        donor = None

    if donor:
        DonorLedger.objects.filter(donor=donor, reference=reference).delete()
        # _sync_donor_totals is triggered automatically via the post_delete
        # signal on DonorLedger (donor_ledger_deleted above), so no manual
        # call is needed here.


# ---------------------------------------------------------------------------
# Register signals for external models (called from apps.py ready())
# ---------------------------------------------------------------------------

def register_signals():
    """
    Register signal handlers for external models without creating circular imports.
    Called from apps.py AppConfig.ready().
    """
    try:
        from accounting.models import CustomerInvoice
        post_save.connect(
            sync_customer_invoice_to_donor_ledger,
            sender=CustomerInvoice,
            weak=False,
            dispatch_uid='sync_customer_invoice_to_donor_ledger',
        )
        post_delete.connect(
            sync_delete_to_donor_ledger,
            sender=CustomerInvoice,
            weak=False,
            dispatch_uid='sync_delete_customer_invoice_ledger',
        )
    except ImportError:
        pass

    try:
        from procurement.models import MaterialRequisition
        post_save.connect(
            sync_material_requisition_to_donor_ledger,
            sender=MaterialRequisition,
            weak=False,
            dispatch_uid='sync_material_requisition_to_donor_ledger',
        )
        post_delete.connect(
            sync_delete_to_donor_ledger,
            sender=MaterialRequisition,
            weak=False,
            dispatch_uid='sync_delete_material_requisition_ledger',
        )
    except ImportError:
        pass

    try:
        from beneficiary.models import DistributionPlan
        post_save.connect(
            sync_distribution_plan_to_donor_ledger,
            sender=DistributionPlan,
            weak=False,
            dispatch_uid='sync_distribution_plan_to_donor_ledger',
        )
        post_delete.connect(
            sync_delete_to_donor_ledger,
            sender=DistributionPlan,
            weak=False,
            dispatch_uid='sync_delete_distribution_plan_ledger',
        )
    except ImportError:
        pass