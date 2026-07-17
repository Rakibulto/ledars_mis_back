from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from django.utils import timezone


class Command(BaseCommand):
    help = "Create comparative statements for RFQs whose submission_deadline has passed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--as-of",
            type=str,
            help="ISO datetime to use as the cutoff for submission_deadline. Defaults to now.",
        )

    def handle(self, *args, **options):
        as_of = timezone.now()
        if options.get("as_of"):
            parsed = parse_datetime(options["as_of"])
            if not parsed:
                self.stderr.write("Invalid ISO datetime for --as-of")
                return
            as_of = parsed

        from procurement.signals import create_comparative_statements_for_expired_rfqs

        created_count = create_comparative_statements_for_expired_rfqs(as_of=as_of)
        self.stdout.write(
            f"Done. Created {created_count} comparative statement{'' if created_count == 1 else 's'}."
        )
