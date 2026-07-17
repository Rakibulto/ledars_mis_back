from django.core.management.base import BaseCommand
from projects.models.models import Project
from project_managements.models import ProjectManagementProject


class Command(BaseCommand):
    help = "Sync ProjectManagementProject records into projects.Project for accounting FKs"

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for pm in ProjectManagementProject.objects.all():
            obj, created = Project.objects.update_or_create(
                code=pm.code,
                defaults={
                    "name": pm.title,
                    "donor": pm.donor,
                    "start_date": pm.start_date,
                    "end_date": pm.end_date,
                    "status": pm.status if pm.status in ("Planning", "Active", "On Hold", "Completed") else "Active",
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        existing_codes = set(ProjectManagementProject.objects.values_list("code", flat=True))
        orphans = Project.objects.exclude(code__in=existing_codes)
        if orphans.exists():
            self.stdout.write(f"  Orphan projects (no matching PM project): {orphans.count()}")
            for o in orphans:
                self.stdout.write(f"    - {o.code} / {o.name}")

        self.stdout.write(self.style.SUCCESS(
            f"Done — created: {created_count}, updated: {updated_count}"
        ))
