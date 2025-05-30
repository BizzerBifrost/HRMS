from django.core.management.base import BaseCommand
from HRMS.models import LEAVE_BALANCE

class Command(BaseCommand):
    help = 'Reset annual leave for all employees for the new year'

    def handle(self, *args, **options):
        balances = LEAVE_BALANCE.objects.all()
        reset_count = 0
        
        for balance in balances:
            # Store the year before reset
            previous_year = balance.year
            
            # Try to reset
            balance.reset_annual_leave()
            
            # If year changed, the reset happened
            if balance.year != previous_year:
                reset_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Checked {balances.count()} leave balances. Reset {reset_count} balances for the new year."
            )
        )