from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.core.management.base import CommandError

class Command(BaseCommand):
    help = "Runs all data loading scripts from different apps"

    def handle(self, *args, **kwargs):
        scripts = [
            "seed_role",
            "seed_shifts",
            "leave_groups",
            "leave_policies",
            "special_leave_policies",
        ]

        errors_occurred = False

        for script in scripts:
            try:
                self.stdout.write(self.style.SUCCESS(f"Running {script}..."))
                call_command(script)  # Django will find the command in any installed app
                self.stdout.write(self.style.SUCCESS(f"Finished {script} ✅"))
            except CommandError as e:
                self.stderr.write(self.style.ERROR(f"Error in {script}: {e} ❌"))
                errors_occurred = True
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Unexpected error in {script}: {e} ❌"))
                errors_occurred = True

        if errors_occurred:
            self.stderr.write(self.style.ERROR("Scripts executed with errors. ❌"))
        else:
            self.stdout.write(self.style.SUCCESS("All scripts executed without errors. 🚀"))
