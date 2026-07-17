from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="project_managements.ProjectManagementProject")
def sync_to_accounting_project(sender, instance, **kwargs):
    """Auto-create/update projects.Project when ProjectManagementProject is saved."""
    from projects.models.models import Project

    status_map = {
        "Planning": "Planning",
        "Active": "Active",
        "On Hold": "On Hold",
        "Completed": "Completed",
    }

    Project.objects.update_or_create(
        code=instance.code,
        defaults={
            "name": instance.title,
            "donor": instance.donor,
            "start_date": instance.start_date,
            "end_date": instance.end_date,
            "status": status_map.get(instance.status, "Active"),
        },
    )
