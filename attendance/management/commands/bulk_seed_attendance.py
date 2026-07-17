import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from attendance.models import AttendanceHistory
from employee.models import Employee


class Command(BaseCommand):
    help = "Bulk seed attendance data to reach target number of records for pagination testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--target",
            type=int,
            default=100000,
            help="Target number of total attendance records (default: 100,000)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Batch size for bulk operations (default: 1,000)",
        )

    def handle(self, *args, **kwargs):
        target = kwargs["target"]
        batch_size = kwargs["batch_size"]

        current_count = AttendanceHistory.objects.count()
        self.stdout.write(f"Current attendance records: {current_count:,}")
        self.stdout.write(f"Target: {target:,}")

        if current_count >= target:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Already have {current_count:,} records, target reached!"
                )
            )
            return

        records_needed = target - current_count
        self.stdout.write(f"Need to create: {records_needed:,} more records")

        # Get all employees
        employees = list(Employee.objects.all())
        if not employees:
            self.stdout.write(self.style.ERROR("No employees found!"))
            return

        total_employees = len(employees)
        self.stdout.write(f"Available employees: {total_employees}")

        # Calculate date range - extend much further back and forward
        end_date = datetime.now().date() + timedelta(
            days=365 * 3
        )  # 3 years into future
        start_date = end_date - timedelta(
            days=365 * 8
        )  # 8 years back from future end date

        self.stdout.write(f"Date range: {start_date} to {end_date}")

        # Calculate records per employee needed
        records_per_employee = records_needed // total_employees
        extra_records = records_needed % total_employees

        self.stdout.write(f"Records per employee: ~{records_per_employee}")
        self.stdout.write(f"Extra records for some employees: {extra_records}")

        created_total = 0

        try:
            with transaction.atomic():
                # Distribute the remaining records across all employees
                records_per_employee = records_needed // total_employees
                extra_records = records_needed % total_employees

                for i, employee in enumerate(employees):
                    # Determine how many records this employee should get
                    target_for_employee = records_per_employee
                    if i < extra_records:
                        target_for_employee += 1

                    # Create attendance records for this employee (don't skip based on existing count)
                    created_for_employee = self._seed_employee_attendance(
                        employee, start_date, end_date, target_for_employee, batch_size
                    )

                    created_total += created_for_employee

                    if (i + 1) % 10 == 0:
                        self.stdout.write(
                            f"Processed {i + 1}/{total_employees} employees..."
                        )

                final_count = AttendanceHistory.objects.count()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully created {created_total:,} attendance records!"
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Total attendance records: {final_count:,}")
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during bulk seeding: {str(e)}"))
            raise

    def _seed_employee_attendance(
        self, employee, start_date, end_date, target_records, batch_size
    ):
        """Seed attendance records for a specific employee"""
        created = 0
        batch = []

        # Generate random dates within the range
        all_dates = [
            start_date + timedelta(days=i)
            for i in range((end_date - start_date).days + 1)
        ]

        # Keep generating records until we reach the target
        attempts = 0
        max_attempts = (
            target_records * 3
        )  # Allow some failed attempts due to duplicates

        while created < target_records and attempts < max_attempts:
            # Pick a random date
            date = random.choice(all_dates)

            # Try to create the record (get_or_create will handle duplicates)
            attendance, created_flag = AttendanceHistory.objects.get_or_create(
                employee=employee,
                date=date,
                defaults={
                    "status": random.choice(
                        ["Present", "Present", "Present", "Late", "Absent"]
                    ),
                    "check_in_time": (
                        datetime.combine(
                            date, datetime.strptime("09:00", "%H:%M").time()
                        )
                        if random.random() > 0.1
                        else None
                    ),
                    "check_out_time": (
                        datetime.combine(
                            date, datetime.strptime("18:00", "%H:%M").time()
                        )
                        if random.random() > 0.1
                        else None
                    ),
                    "is_late": random.choice([True, False]),
                    "late_by": (
                        timedelta(minutes=random.randint(0, 120))
                        if random.random() > 0.7
                        else timedelta(0)
                    ),
                    "rfid_or_machine_code": f"EMP{employee.pk}",
                    "device_serial_number": "DEVICE_001",
                },
            )

            if created_flag:
                created += 1

            attempts += 1

        return created
