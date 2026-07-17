"""
Test script to demonstrate donor ledger synchronization system.

This script:
1. Creates sample donors and transactions
2. Verifies signals create ledger entries automatically
3. Tests the management command for generating ledgers
"""

from decimal import Decimal
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from donor.models import Donor, DonorLedger


class DonorLedgerSignalTests(TransactionTestCase):
    """Test automatic ledger generation via signals."""

    def setUp(self):
        """Create test donor."""
        self.donor = Donor.objects.create(
            name="Test Donor Organization",
            email="donor@example.com",
            phone="+1234567890",
            organization_name="Donor Org Inc",
            type="individual",
            currency="USD",
        )

    def test_customer_invoice_creates_ledger(self):
        """
        Test: When a CustomerInvoice is created with a donor FK,
        a DonorLedger entry is automatically created.
        
        Expected Flow:
        1. Create CustomerInvoice with donor FK
        2. Signal catches post_save event
        3. DonorLedger entry created with reference=Invoice-{number}
        """
        try:
            from accounting.models import CustomerInvoice

            from django.utils import timezone as tz
            invoice = CustomerInvoice.objects.create(
                customer=self.donor,
                subtotal=Decimal("5000.00"),
                tax_amount=Decimal("0.00"),
                date=tz.now().date(),
                due_date=tz.now().date(),
            )

            # Check ledger entry was created
            ledger = DonorLedger.objects.get(reference=f"Invoice-{invoice.number}")
            self.assertEqual(ledger.donor, self.donor)
            self.assertEqual(ledger.amount, Decimal("5000.00"))
            self.assertEqual(ledger.transaction_type, "donation")

            print("[OK] Test passed: CustomerInvoice signal creates ledger entry")

        except ImportError:
            print("[/] Skipped: accounting.models.CustomerInvoice not available")

    def test_material_requisition_creates_ledger(self):
        """
        Test: When a MaterialRequisition is created with a donor FK,
        a DonorLedger entry is automatically created.
        """
        try:
            from procurement.models import MaterialRequisition

            req = MaterialRequisition.objects.create(
                donor_code=self.donor,
                purpose="Test Requisition",
                total_amount=Decimal("3000.00"),
            )

            # Check ledger entry was created
            ledger = DonorLedger.objects.get(reference=f"MatReq-{req.id}")
            self.assertEqual(ledger.donor, self.donor)
            self.assertEqual(ledger.amount, Decimal("3000.00"))
            self.assertEqual(ledger.transaction_type, "donation")

            print("[OK] Test passed: MaterialRequisition signal creates ledger entry")

        except ImportError:
            print("[/] Skipped: procurement models not available")

    def test_distribution_plan_creates_ledger(self):
        """
        Test: When a DistributionPlan is created for a project with a donor,
        the signal handler does not crash.  No ledger is created because
        DistributionPlan has no quantity/cost fields (amount is 0).
        """
        try:
            from projects.models import Project
            from beneficiary.models import DistributionPlan

            # Create project with donor
            project = Project.objects.create(
                name="Test Project",
                donor=self.donor,
            )

            # Create distribution plan (must not raise ValueError)
            plan = DistributionPlan.objects.create(
                project=project,
                name="Test Distribution",
            )

            # No ledger entry should exist (amount was 0)
            self.assertFalse(
                DonorLedger.objects.filter(reference=f"DistPlan-{plan.id}").exists()
            )

            print("[OK] Test passed: DistributionPlan signal does not crash")

        except ImportError:
            print("[/] Skipped: beneficiary models not available")

    def test_management_command_generates_ledgers(self):
        """
        Test: The generate_donor_ledgers management command
        creates ledger entries for existing transactions.
        """
        try:
            from accounting.models import CustomerInvoice

            from django.utils import timezone as tz

            # Create invoice (signal may or may not have been triggered)
            invoice = CustomerInvoice.objects.create(
                customer=self.donor,
                subtotal=Decimal("2000.00"),
                tax_amount=Decimal("0.00"),
                date=tz.now().date(),
                due_date=tz.now().date(),
            )

            reference = f"Invoice-{invoice.number}"

            # Clear any existing ledger
            DonorLedger.objects.filter(reference=reference).delete()

            # Run management command
            call_command("generate_donor_ledgers", donor_id=self.donor.id)

            # Check ledger was created by command
            ledger = DonorLedger.objects.get(reference=reference)
            self.assertEqual(ledger.amount, Decimal("2000.00"))

            print("[OK] Test passed: generate_donor_ledgers command works")

        except ImportError:
            print("[/] Skipped: accounting models not available")

    def test_ledger_deletion_on_transaction_delete(self):
        """
        Test: When a transaction with a ledger entry is deleted,
        the corresponding ledger entry is also deleted.
        """
        try:
            from accounting.models import CustomerInvoice

            from django.utils import timezone as tz

            invoice = CustomerInvoice.objects.create(
                customer=self.donor,
                subtotal=Decimal("1000.00"),
                tax_amount=Decimal("0.00"),
                date=tz.now().date(),
                due_date=tz.now().date(),
            )

            reference = f"Invoice-{invoice.number}"
            self.assertTrue(DonorLedger.objects.filter(reference=reference).exists())

            # Delete invoice
            invoice.delete()

            # Check ledger was also deleted
            self.assertFalse(
                DonorLedger.objects.filter(reference=reference).exists()
            )

            print("[OK] Test passed: Deleting transaction also deletes ledger entry")

        except ImportError:
            print("[/] Skipped: accounting models not available")


if __name__ == "__main__":
    # Run tests
    import django
    from django.conf import settings
    from django.test.utils import get_runner

    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()

    print("\n" + "="*60)
    print("DONOR LEDGER SYNCHRONIZATION SYSTEM - TEST SUITE")
    print("="*60 + "\n")

    failures = test_runner.run_tests(["donor.tests"])
    
    print("\n" + "="*60)
    if failures == 0:
        print("[OK] All tests passed!")
    else:
        print(f"✗ {failures} test(s) failed")
    print("="*60 + "\n")
