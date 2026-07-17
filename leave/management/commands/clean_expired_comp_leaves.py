from django.core.management.base import BaseCommand
from django.utils import timezone
from leave.models import CompensatoryLeaveBalance

class Command(BaseCommand):
    help = 'Clean expired compensatory leaves'
    
    def handle(self, *args, **options):
        balances = CompensatoryLeaveBalance.objects.all()
        total_expired = 0
        
        for balance in balances:
            expired_count = balance.clean_expired_leaves()
            total_expired += expired_count
            
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully cleaned {total_expired} expired compensatory leaves'
            )
        )