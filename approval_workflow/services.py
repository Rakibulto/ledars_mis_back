from django.db import transaction
from django.contrib.auth import get_user_model

from .models import ApprovalWorkflow, ApprovalLevel, ApprovalLevelUser

User = get_user_model()


def create_or_replace_workflow(
    validated_data: dict,
    requesting_user=None,
    workflow_instance: ApprovalWorkflow = None,
) -> ApprovalWorkflow:
    """
    Creates (or fully replaces the levels of) an ApprovalWorkflow.

    * If *workflow_instance* is provided the existing row is updated in-place
      (ID is preserved) and its levels are rebuilt.
    * Otherwise a new workflow is created.
    """
    module_type_name = validated_data['module_type_name']
    menu_name = validated_data['menu_name']
    is_active = validated_data.get('is_active', True)
    levels_data = validated_data['levels']

    with transaction.atomic():
        if workflow_instance is not None:
            workflow_instance.module_type_name = module_type_name
            workflow_instance.menu_name = menu_name
            workflow_instance.is_active = is_active
            workflow_instance.save(update_fields=['module_type_name', 'menu_name', 'is_active', 'updated_at'])
            workflow_instance.levels.all().delete()  # rebuild levels
            workflow = workflow_instance
        else:
            workflow = ApprovalWorkflow.objects.create(
                module_type_name=module_type_name,
                menu_name=menu_name,
                is_active=is_active,
                created_by=requesting_user,
            )

        for level_data in levels_data:
            users = level_data.pop('users', [])
            level = ApprovalLevel.objects.create(workflow=workflow, **level_data)
            for entry in users:
                try:
                    user = User.objects.get(pk=entry['user_id'])
                    ApprovalLevelUser.objects.create(
                        level=level,
                        user=user,
                        approval_order=entry['approval_order'],
                    )
                except User.DoesNotExist:
                    pass

        return workflow


def update_workflow_status(workflow_id: int, is_active: bool) -> ApprovalWorkflow:
    """Toggle active status of a workflow."""
    with transaction.atomic():
        workflow = ApprovalWorkflow.objects.select_for_update().get(pk=workflow_id)
        workflow.is_active = is_active
        workflow.save(update_fields=['is_active', 'updated_at'])
        return workflow
