"""
Seed canonical budget workspace data matching the frontend demo-data.js exactly.
Usage:
    python manage.py seed_budgets_workspace
    python manage.py seed_budgets_workspace --clear
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from accounting.models import (
    Account,
    Budget,
    BudgetAmendment,
    BudgetLine,
    CostCenter,
    FiscalYear,
)


# ── Canonical data mirrors ACCOUNTING_MOCK_BUDGETS in demo-data.js ─────────────

CANONICAL_BUDGETS = [
    {
        "name": "Health Outreach FY26",
        "department_label": "Health Outreach",
        "fiscal_year_code": "FY-2026",
        "cost_center_code": "CC-HLT",
        "owner": "Budget Controller",
        "status": "active",
        "warning_threshold": 85,
        "critical_threshold": 95,
        "lines": [
            {
                "account_code": "6110",  # Medical Supplies
                "owner": "Procurement Finance",
                "planned": 90000,
                "actual": 72000,
                "commitments": 8000,
                "encumbrance": 5000,
                "note": "Medical supplies and outreach consumables",
            },
            {
                "account_code": "6100",  # Salaries
                "owner": "Program Manager",
                "planned": 60000,
                "actual": 43000,
                "commitments": 6000,
                "encumbrance": 3000,
                "note": "Outreach staff and temporary support payroll",
            },
            {
                "account_code": "6120",  # Travel & Transport
                "owner": "Budget Controller",
                "planned": 40000,
                "actual": 18000,
                "commitments": 2000,
                "encumbrance": 0,
                "note": "Transport and field banking support",
            },
            {
                "account_code": "6200",  # Program Expenses
                "owner": "Grant Accountant",
                "planned": 50000,
                "actual": 35000,
                "commitments": 7000,
                "encumbrance": 4000,
                "note": "Community event delivery and specialist vendors",
            },
        ],
        "amendment": {
            "amount": 12000,
            "reason": "Expanded mobile-clinic medicines and field travel cover",
            "requested_by": "Program Manager",
            "effective_period": "Apr 2026",
            "status": "approved",
            "approved_by": "Finance Director",
        },
    },
    {
        "name": "Education Program FY26",
        "department_label": "Education Program",
        "fiscal_year_code": "FY-2026",
        "cost_center_code": "CC-EDU",
        "owner": "Program Manager",
        "status": "active",
        "warning_threshold": 85,
        "critical_threshold": 95,
        "lines": [
            {
                "account_code": "6100",
                "owner": "Program Manager",
                "planned": 140000,
                "actual": 102000,
                "commitments": 15000,
                "encumbrance": 9000,
                "note": "Teachers, facilitators, and project coordinators",
            },
            {
                "account_code": "6110",
                "owner": "Procurement Finance",
                "planned": 60000,
                "actual": 39500,
                "commitments": 6000,
                "encumbrance": 3500,
                "note": "Learning kits, digital content, and training material",
            },
            {
                "account_code": "6120",
                "owner": "Cost Center Lead",
                "planned": 50000,
                "actual": 24000,
                "commitments": 5500,
                "encumbrance": 2000,
                "note": "Internet, transport, and support services",
            },
            {
                "account_code": "6200",
                "owner": "Grant Accountant",
                "planned": 60000,
                "actual": 39000,
                "commitments": 9000,
                "encumbrance": 4500,
                "note": "Implementing partner services and venue support",
            },
        ],
        "amendment": None,
    },
    {
        "name": "Operations Support FY26",
        "department_label": "Operations Support",
        "fiscal_year_code": "FY-2026",
        "cost_center_code": "CC-OPS",
        "owner": "Finance Analyst",
        "status": "draft",
        "warning_threshold": 85,
        "critical_threshold": 95,
        "lines": [
            {
                "account_code": "6100",
                "owner": "Controller",
                "planned": 50000,
                "actual": 36000,
                "commitments": 5000,
                "encumbrance": 2000,
                "note": "Shared services payroll and finance operations",
            },
            {
                "account_code": "6120",
                "owner": "Budget Controller",
                "planned": 25000,
                "actual": 18000,
                "commitments": 2500,
                "encumbrance": 1200,
                "note": "Utilities, connectivity, and support services",
            },
            {
                "account_code": "5100",  # Accrued Liabilities fallback → admin cost
                "owner": "Procurement Finance",
                "planned": 20000,
                "actual": 10500,
                "commitments": 2800,
                "encumbrance": 800,
                "note": "Office accruals and maintenance pre-commitments",
            },
            {
                "account_code": "4000",  # Revenue fallback → admin banking cost
                "owner": "Finance Analyst",
                "planned": 25000,
                "actual": 19000,
                "commitments": 2200,
                "encumbrance": 1000,
                "note": "Admin banking, insurance, and platform costs",
            },
        ],
        "amendment": {
            "amount": 8000,
            "reason": "Admin platform renewal and compliance cost update",
            "requested_by": "Controller",
            "effective_period": "Apr 2026",
            "status": "pending_approval",
            "approved_by": "",
        },
    },
]


class Command(BaseCommand):
    help = "Seed canonical budget workspace data matching frontend demo-data.js"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing seeded budgets before re-seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = Budget.objects.filter(
                name__in=[b["name"] for b in CANONICAL_BUDGETS]
            ).delete()
            self.stdout.write(f"  Cleared {deleted} existing budget records")

        # Ensure FY 2026 exists
        fy, _ = FiscalYear.objects.get_or_create(
            code="FY-2026",
            defaults={
                "name": "FY 2026",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "status": "open",
                "is_active": True,
            },
        )

        # Ensure cost centres exist
        cc_map = {}
        for code, name in [
            ("CC-EDU", "Education Program"),
            ("CC-HLT", "Health Outreach"),
            ("CC-OPS", "Operations Support"),
            ("CC-HR", "Shared Services"),
        ]:
            cc, _ = CostCenter.objects.get_or_create(
                code=code,
                defaults={"name": name, "is_active": True},
            )
            cc_map[code] = cc

        # Build account fallback map: code → Account
        # Load a pool of accounts for fallback rotation to avoid unique_together collision
        account_pool = list(Account.objects.order_by("code").values_list("id", "code", "name")[:30])
        account_cache = {}
        _pool_index = [0]  # mutable counter for rotation

        def get_account(code):
            if code in account_cache:
                return account_cache[code]
            acct = Account.objects.filter(code=code).first()
            if acct is None and account_pool:
                # Rotate through pool to avoid every missing code returning the same account
                pk, _, _ = account_pool[_pool_index[0] % len(account_pool)]
                acct = Account.objects.get(id=pk)
                _pool_index[0] += 1
            account_cache[code] = acct
            return acct

        budgets_created = 0
        lines_created = 0
        amendments_created = 0

        for spec in CANONICAL_BUDGETS:
            budget, created = Budget.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "fiscal_year": fy,
                    "cost_center": cc_map.get(spec["cost_center_code"]),
                    "owner": spec["owner"],
                    "department_label": spec["department_label"],
                    "status": spec["status"],
                    "warning_threshold": Decimal(str(spec["warning_threshold"])),
                    "critical_threshold": Decimal(str(spec["critical_threshold"])),
                },
            )

            if not created:
                # Update fields in case the seed was run before without the new fields
                budget.fiscal_year = fy
                budget.cost_center = cc_map.get(spec["cost_center_code"])
                budget.owner = spec["owner"]
                budget.department_label = spec["department_label"]
                budget.status = spec["status"]
                budget.warning_threshold = Decimal(str(spec["warning_threshold"]))
                budget.critical_threshold = Decimal(str(spec["critical_threshold"]))
                # Clear old lines so we can re-seed cleanly
                budget.lines.all().delete()
                budget.amendments.all().delete()
                budget.save()
            else:
                budgets_created += 1

            total_planned = Decimal("0")
            total_actual = Decimal("0")
            total_committed = Decimal("0")
            total_encumbrance = Decimal("0")

            for line_spec in spec["lines"]:
                account = get_account(line_spec["account_code"])
                if account is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  No account found for code {line_spec['account_code']}, skipping line"
                        )
                    )
                    continue

                planned = Decimal(str(line_spec["planned"]))
                actual = Decimal(str(line_spec["actual"]))
                committed = Decimal(str(line_spec["commitments"]))
                encumbrance = Decimal(str(line_spec["encumbrance"]))
                available = planned - actual - committed - encumbrance

                # Skip if this account is already used in this budget (unique_together)
                if budget.lines.filter(account=account).exists():
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Skipping duplicate account {account.code} in {budget.name}"
                        )
                    )
                    continue

                BudgetLine.objects.create(
                    budget=budget,
                    account=account,
                    owner=line_spec["owner"],
                    planned_amount=planned,
                    actual_amount=actual,
                    committed_amount=committed,
                    encumbrance_amount=encumbrance,
                    available_amount=available,
                    notes=line_spec["note"],
                )
                lines_created += 1
                total_planned += planned
                total_actual += actual
                total_committed += committed
                total_encumbrance += encumbrance

            # Update denormalised totals
            budget.total_planned = total_planned
            budget.total_actual = total_actual
            budget.total_committed = total_committed
            budget.total_encumbrance = total_encumbrance
            budget.total_available = (
                total_planned - total_actual - total_committed - total_encumbrance
            )
            budget.save(
                update_fields=[
                    "total_planned",
                    "total_actual",
                    "total_committed",
                    "total_encumbrance",
                    "total_available",
                ]
            )

            # Seed amendment if specified
            if spec.get("amendment"):
                amd_spec = spec["amendment"]
                first_line = budget.lines.first()
                BudgetAmendment.objects.create(
                    budget=budget,
                    target_line=first_line,
                    amount=Decimal(str(amd_spec["amount"])),
                    reason=amd_spec["reason"],
                    effective_period=amd_spec["effective_period"],
                    requested_by=amd_spec["requested_by"],
                    approved_by=amd_spec.get("approved_by", ""),
                    status=amd_spec["status"],
                )
                amendments_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Budget workspace seeded: {budgets_created} new budgets, "
                f"{lines_created} lines, {amendments_created} amendments"
            )
        )
