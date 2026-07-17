from django.core.management.base import BaseCommand
from leave.models import LeaveGroup

class Command(BaseCommand):
    help = 'Seed leave groups'
    
    def handle(self, *args, **kwargs):
        group_names = [
            'General Staff (Probation)',
            'General Staff (Regular)',
            'Teachers (Probation)',
            'Teachers (Regular)'
        ]
        
        for name in group_names:
            obj, created = LeaveGroup.objects.get_or_create(name=name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Leave group "{name}" created successfully.'))
            else:
                self.stdout.write(self.style.WARNING(f'Leave group "{name}" already exists.'))