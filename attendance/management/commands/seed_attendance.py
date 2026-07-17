import random
from datetime import datetime, timedelta, time
from django.core.management.base import BaseCommand
from django.utils import timezone
from attendance.models import AttendanceHistory
from employee.models import Employee


class Command(BaseCommand):
    help = "Seeds AttendanceHistory for employees from January 2025 to December 2025"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Seeding attendance history..."))

        try:
            # Get existing employees
            employees = Employee.objects.select_related("user", "office_time").all()
            if not employees.exists():
                self.stdout.write(
                    self.style.ERROR("No employees found. Please seed employees first.")
                )
                return

            self.stdout.write(f"Found {employees.count()} employees.")

            # Seed AttendanceHistory
            self.stdout.write("Seeding AttendanceHistory...")
            start_date = datetime(2026, 1, 1).date()
            end_date = datetime(2026, 2, 28).date()

            attendance_history_records = []
            total_records = 0

            for i, employee in enumerate(employees):
                shift = employee.office_time
                if not shift:
                    continue

                current_date = start_date
                while current_date <= end_date:
                    # Skip weekends for regular full-time shifts (assuming Saturday/Sunday are weekends)
                    # Only skip weekends for shifts that start before 5 PM (17:00)
                    if (
                        shift.office_start_time
                        and shift.office_start_time.hour < 17
                        and current_date.weekday() >= 5
                    ):  # 5=Saturday, 6=Sunday
                        current_date += timedelta(days=1)
                        continue

                    # Use actual shift times from the database
                    if not shift.office_start_time or not shift.office_end_time:
                        current_date += timedelta(days=1)
                        continue

                    # Determine if this is an overnight shift
                    is_overnight = shift.office_end_time < shift.office_start_time

                    # Generate check-in and check-out times based on actual shift times
                    check_in_time = shift.office_start_time
                    check_out_time = shift.office_end_time

                    # Add random variation (±30 minutes)
                    check_in_variation = random.randint(-30, 30)
                    check_out_variation = random.randint(-30, 30)

                    # Calculate actual timestamps
                    check_in_dt = datetime.combine(
                        current_date, check_in_time
                    ) + timedelta(minutes=check_in_variation)

                    if is_overnight:
                        # For overnight shifts, check-out is next day
                        check_out_dt = datetime.combine(
                            current_date + timedelta(days=1), check_out_time
                        ) + timedelta(minutes=check_out_variation)
                    else:
                        check_out_dt = datetime.combine(
                            current_date, check_out_time
                        ) + timedelta(minutes=check_out_variation)

                    # Make timestamps timezone aware
                    check_in_dt = timezone.make_aware(check_in_dt)
                    check_out_dt = timezone.make_aware(check_out_dt)

                    # All attendance records should have status "Present"
                    is_late = (
                        check_in_variation > 15
                    )  # Late if more than 15 minutes late
                    late_by = (
                        timedelta(minutes=max(0, check_in_variation))
                        if is_late
                        else None
                    )
                    status = "Present"

                    # Create AttendanceHistory record
                    attendance_history_records.append(
                        AttendanceHistory(
                            employee=employee,
                            date=current_date,
                            check_in_time=check_in_dt,
                            check_out_time=check_out_dt,
                            is_late=is_late,
                            late_by=late_by,
                            status=status,
                            remarks=f'Attendance for {current_date.strftime("%Y-%m-%d")}',
                            rfid_or_machine_code=f"RFID{employee.user.id:04d}",
                            device_serial_number=f"DEVICE{random.randint(1000, 9999)}",
                            local_ip_address=f"192.168.1.{random.randint(10, 254)}",
                            is_weekend=current_date.weekday() >= 5,
                            is_holiday=False,  # Assuming no holidays for seeding
                        )
                    )

                    current_date += timedelta(days=1)

                if (i + 1) % 50 == 0:
                    self.stdout.write(
                        f"Prepared attendance history for {i + 1} employees..."
                    )

            # Bulk insert attendance history
            batch_size = 500
            for i in range(0, len(attendance_history_records), batch_size):
                batch = attendance_history_records[i : i + batch_size]
                AttendanceHistory.objects.bulk_create(batch)
                total_records += len(batch)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Inserted {len(batch)} records... Total: {total_records}"
                    )
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully seeded {total_records} attendance history records."
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during seeding: {str(e)}"))
            import traceback

            traceback.print_exc()
            raise
