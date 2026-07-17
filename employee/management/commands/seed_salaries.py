from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from authentication.models import User
from employee.models import Employee, Salary


class Command(BaseCommand):
    help = "Seed Salary records for employees. Creates a Salary for employees without any Salary."

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite existing salaries for employees",
        )
        parser.add_argument(
            "--creator",
            type=str,
            help="Username to set as creator (defaults to first superuser)",
        )

    def handle(self, *args, **options):
        overwrite = options.get("overwrite", False)
        creator_username = options.get("creator")

        creator = None
        if creator_username:
            try:
                creator = User.objects.get(username=creator_username)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"Creator '{creator_username}' not found. Using None."
                    )
                )
                creator = None
        else:
            creator = User.objects.filter(is_superuser=True).first()

        employees = Employee.objects.all()
        total = employees.count()
        self.stdout.write(f"Found {total} employees. overwrite={overwrite}")

        created = 0
        skipped = 0

        for emp in employees:
            if emp.salaries.exists() and not overwrite:
                skipped += 1
                continue

            gross = emp.salary if emp.salary is not None else Decimal("0.00")
            if gross == Decimal("0.00"):
                gross = Decimal("30000.00")

            # Simple split: basic 50%, house 30%, convey 10%, medical = rest
            basic = (gross * Decimal("0.50")).quantize(Decimal("0.01"))
            house = (gross * Decimal("0.30")).quantize(Decimal("0.01"))
            convey = (gross * Decimal("0.10")).quantize(Decimal("0.01"))
            medical = (gross - basic - house - convey).quantize(Decimal("0.01"))

            with transaction.atomic():
                if overwrite:
                    emp.salaries.all().delete()

                Salary.objects.create(
                    creator=creator,
                    employee=emp,
                    effective_date=timezone.now().date(),
                    basic=basic,
                    house_rent=house,
                    conveyance=convey,
                    medical=medical,
                    festival_bonus=Decimal("0.00"),
                    absence_deduction=Decimal("0.00"),
                    late_deduction=Decimal("0.00"),
                    holiday_compensation=Decimal("0.00"),
                    weekday_compensation=Decimal("0.00"),
                    performance_bonus=Decimal("0.00"),
                )

                created += 1

        self.stdout.write(
            self.style.SUCCESS(f"Created {created} salaries, skipped {skipped}.")
        )
