"""
Management command to generate donor ledger entries from related transactions across modules.

This command scans all modules for donor-related transactions and creates corresponding
ledger entries in the DonorLedger model. It handles:
- Projects/Project Management expenses (direct)
- Material Requisitions (procurement)
- Customer Invoices (accounting)
- Distribution Plans (beneficiary, indirect via project)
"""

from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from donor.models import Donor, DonorLedger


class Command(BaseCommand):
    help = 'Generate donor ledger entries from related transactions across modules'

    def add_arguments(self, parser):
        parser.add_argument(
            '--donor-id',
            type=int,
            help='Process only a specific donor by ID',
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Delete existing ledger entries before regenerating',
        )

    def handle(self, *args, **options):
        donor_id = options.get('donor_id')
        clean = options.get('clean', False)

        if donor_id:
            try:
                donor = Donor.objects.get(id=donor_id)
                donors = [donor]
                self.stdout.write(self.style.SUCCESS(f'Processing donor: {donor.name}'))
            except Donor.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Donor with ID {donor_id} not found'))
                return
        else:
            donors = Donor.objects.all()
            self.stdout.write(self.style.SUCCESS(f'Processing {donors.count()} donors'))

        for donor in donors:
            if clean:
                DonorLedger.objects.filter(donor=donor).delete()
                self.stdout.write(f'  Cleaned ledgers for {donor.name}')

            self.generate_ledger_from_projects(donor)
            self.generate_ledger_from_requisitions(donor)
            self.generate_ledger_from_invoices(donor)
            self.generate_ledger_from_distributions(donor)

            self.stdout.write(
                self.style.SUCCESS(f'[OK] Completed ledger generation for {donor.name}')
            )

    def generate_ledger_from_projects(self, donor):
        """Generate ledger entries from project management expenses."""
        try:
            from project_managements.models import ProjectManagementExpense
        except ImportError:
            return

        expenses = ProjectManagementExpense.objects.filter(project__donor=donor)
        for expense in expenses:
            for item in expense.items.all():
                self._create_or_update_ledger(
                    donor=donor,
                    transaction_type='donation',
                    amount=item.line_total,
                    reference=f'ProjectExp-{expense.id}',
                    description=f'Project Management Expense: {item.description}',
                    related_project=expense.project,
                    transaction_date=expense.expense_date or timezone.now(),
                )

    def generate_ledger_from_requisitions(self, donor):
        """Generate ledger entries from material requisitions."""
        try:
            from procurement.models import MaterialRequisition
        except ImportError:
            return

        requisitions = MaterialRequisition.objects.filter(donor_code=donor)
        for req in requisitions:
            total_cost = req.total_amount or Decimal('0.00')

            if total_cost > 0:
                self._create_or_update_ledger(
                    donor=donor,
                    transaction_type='donation',
                    amount=total_cost,
                    reference=f'MatReq-{req.id}',
                    description=f'Material Requisition: {req.purpose or ""}',
                    related_project=getattr(req, 'project', None),
                    transaction_date=req.created_at,
                )

    def generate_ledger_from_invoices(self, donor):
        """Generate ledger entries from accounting customer invoices."""
        try:
            from accounting.models import CustomerInvoice
        except ImportError:
            return

        invoices = CustomerInvoice.objects.filter(customer=donor)
        for invoice in invoices:
            self._create_or_update_ledger(
                donor=donor,
                transaction_type='donation',
                amount=invoice.total or Decimal('0.00'),
                reference=f'Invoice-{invoice.number}',
                description=f'Customer Invoice: {invoice.number}',
                related_project=None,
                transaction_date=invoice.date or timezone.now(),
            )

    def generate_ledger_from_distributions(self, donor):
        """Generate ledger entries from distribution plans (indirect via project)."""
        try:
            from beneficiary.models import DistributionPlan
            from projects.models import Project
        except ImportError:
            return

        # DistributionPlan has no quantity/cost fields, so amount is 0
        # and no ledger entries will be created.
        pass

    def _create_or_update_ledger(
        self,
        donor,
        transaction_type,
        amount,
        reference,
        description,
        related_project,
        transaction_date,
    ):
        """Create or update a ledger entry, avoiding duplicates."""
        if not amount or amount == 0:
            return

        ledger, created = DonorLedger.objects.get_or_create(
            donor=donor,
            reference=reference,
            defaults={
                'transaction_type': transaction_type,
                'amount': amount,
                'description': description,
                'related_project': related_project,
                'transaction_date': transaction_date,
                'currency': donor.currency or 'USD',
            },
        )

        if not created and ledger.amount != amount:
            ledger.amount = amount
            ledger.description = description
            ledger.save()

        self.stdout.write(
            f'  {"Created" if created else "Updated"} ledger: '
            f'{reference} - {amount} {donor.currency or "USD"}'
        )
