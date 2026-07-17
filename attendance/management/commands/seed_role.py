from django.core.management.base import BaseCommand
from authentication.models import Role


class Command(BaseCommand):
    help = 'Seeds the database with initial roles: Admin, Employee, Supervisor'

    def handle(self, *args, **kwargs):
        roles = ['Admin', 'Supervisor','Employee', 'Guest']
        created_count = 0

        for i, role_name in enumerate(roles, start=1):
            role, created = Role.objects.get_or_create(
                id=i,
                defaults={'name': role_name}
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created role: {role.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Role already exists: {role.name}'))

        self.stdout.write(self.style.SUCCESS(f'Total roles created: {created_count}'))
