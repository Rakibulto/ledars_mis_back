from django.core.management.base import BaseCommand
from django.db import models
from employee.models import Employee


class Command(BaseCommand):
    help = 'Delete employees with empty or null employee_id'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Find employees with empty or null employee_id
        employees_to_delete = Employee.objects.filter(
            models.Q(employee_id__isnull=True) | models.Q(employee_id='')
        )

        count = employees_to_delete.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('No employees found with empty or null employee_id.')
            )
            return

        self.stdout.write(
            self.style.WARNING(f'Found {count} employee(s) with empty or null employee_id:')
        )

        # Show details of employees to be deleted
        for employee in employees_to_delete:
            self.stdout.write(f'  - {employee.user.username} (ID: {employee.pk})')

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'Dry run: Would delete {count} employee(s).')
            )
        else:
            # Confirm deletion
            confirm = input(f'\nAre you sure you want to delete {count} employee(s)? (yes/no): ')
            if confirm.lower() == 'yes':
                deleted_count, _ = employees_to_delete.delete()
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully deleted {deleted_count} employee(s).')
                )
            else:
                self.stdout.write('Deletion cancelled.')