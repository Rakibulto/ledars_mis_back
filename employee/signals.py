from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .models import Employee
from leave.models import SupervisorLevel

import logging

logger = logging.getLogger(__name__)


@receiver(m2m_changed, sender=Employee.supervisor.through)
def handle_employee_supervisor_levels(sender, instance, action, pk_set, **kwargs):
    """
    Signal handler to create SupervisorLevel entries for employee supervisors.
    This is triggered when the supervisor M2M field is changed via normal admin operations.
    Supervisors are assigned incremental levels based on their order.

    A single supervisor (User) can be supervisor of multiple employees.
    This creates SupervisorLevel entries for each employee-supervisor combination.

    Note: For Excel imports via django-import-export, the import_row
    method in EmployeeResource handles this instead, as import-export doesn't
    trigger m2m_changed signals reliably.
    """
    # Only process after supervisors are added
    if action not in ["post_add", "post_set"]:
        return

    # Skip if no supervisors were added
    if not pk_set:
        return

    # Get all current supervisors for this employee
    current_supervisors = list(instance.supervisor.all())

    # Delete existing SupervisorLevel entries for this employee
    SupervisorLevel.objects.filter(employee=instance).delete()

    # Create new SupervisorLevel entries with incremental levels
    for level, supervisor in enumerate(current_supervisors, start=1):
        SupervisorLevel.objects.create(
            employee=instance, supervisor=supervisor, level=level
        )
        logger.info(
            f"Created SupervisorLevel: Employee ID {instance.pk} - Supervisor ID {supervisor.pk} at Level {level}"
        )
