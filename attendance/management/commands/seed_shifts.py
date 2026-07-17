from datetime import time
from django.core.management.base import BaseCommand
from employee.models import  Shift




class Command(BaseCommand):
    help = 'Seeds Shifts, Users, Employees, and AttendanceHistory for June 2025'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Seeding shifts ...'))
        created_count = 0

        try:
            # Step 1: Create Shifts if not exist
            self.stdout.write('Checking/Creating Shifts...')
            shift_data = [
                {
                    "id": 1,
                    "name": "Day",
                    "office_start_time": time(9, 0),
                    "office_end_time": time(18, 0),
                    "check_in_start_time": time(8, 0),
                    "check_in_end_time": time(12, 0),
                    "check_out_start_time": time(12, 0),
                    "check_out_end_time": time(18, 0)
                },
                {
                    "id": 2,
                    "name": "Night",
                    "office_start_time": time(18, 0),
                    "office_end_time": time(6, 0),
                    "check_in_start_time": time(13, 0),
                    "check_in_end_time": time(23, 0),
                    "check_out_start_time": time(1, 0),
                    "check_out_end_time": time(7, 0)
                }
            ]

            for shift in shift_data:
                obj, created = Shift.objects.get_or_create(
                    id=shift["id"],
                    defaults={
                        "name": shift["name"],
                        "office_start_time": shift["office_start_time"],
                        "office_end_time": shift["office_end_time"],
                        "office_start_time_consideration": 10,
                        "office_end_time_consideration": 10,
                        "check_in_start_time": shift["check_in_start_time"],
                        "check_in_end_time": shift["check_in_end_time"],
                        "check_out_start_time": shift["check_out_start_time"],
                        "check_out_end_time": shift["check_out_end_time"],
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'Created Shift: {obj.name}'))
                else:
                    self.stdout.write(self.style.WARNING(f'Shift already exists: {obj.name}'))

            self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} shifts'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during seeding: {str(e)}'))
            raise
