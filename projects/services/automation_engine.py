"""
ClickUp-style automation engine for Project Management.

Evaluates automation rules when triggered by task events and executes
configured actions (change status, assign user, add tag, etc.).
"""

import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def trigger_automation(trigger_type, task, user, context=None):
    """
    Main entry point. Called from task views when an event occurs.

    Args:
        trigger_type: str - one of Automation.TRIGGER_CHOICES values
        task: Task instance that triggered the event
        user: User who performed the action
        context: dict - additional context (e.g. old/new status, assignee_id)
    """
    from projects.models import Automation

    context = context or {}

    # Find matching active automations for this trigger type
    automations = Automation.objects.filter(
        trigger_type=trigger_type,
        is_active=True,
    ).prefetch_related("actions")

    # Filter by space if the task has a list in a space
    if task.list and task.list.space:
        automations = automations.filter(
            models_Q(space=task.list.space) | models_Q(space__isnull=True)
        )

    for automation in automations:
        _execute_automation(automation, task, user, context)


def _evaluate_conditions(conditions, task, context):
    """
    Evaluate automation conditions against the task and context.
    Conditions is a list of dicts like:
    [{"field": "priority", "operator": "equals", "value": "urgent"}]
    Returns True if ALL conditions pass.
    """
    if not conditions:
        return True

    for cond in conditions:
        field = cond.get("field", "")
        operator = cond.get("operator", "equals")
        value = cond.get("value")

        # Get the actual field value from task or context
        if field in context:
            actual = context[field]
        elif hasattr(task, field):
            actual = getattr(task, field)
            # Handle FK fields
            if hasattr(actual, "id"):
                actual = str(actual.id)
            elif hasattr(actual, "name"):
                actual = actual.name
            else:
                actual = str(actual) if actual is not None else None
        else:
            continue

        actual_str = str(actual).lower() if actual is not None else ""
        value_str = str(value).lower() if value is not None else ""

        if operator == "equals" and actual_str != value_str:
            return False
        elif operator == "not_equals" and actual_str == value_str:
            return False
        elif operator == "contains" and value_str not in actual_str:
            return False
        elif operator == "not_contains" and value_str in actual_str:
            return False
        elif operator == "is_set" and not actual:
            return False
        elif operator == "is_not_set" and actual:
            return False

    return True


@transaction.atomic
def _execute_automation(automation, task, user, context):
    """Execute all actions for a matched automation."""
    from projects.models import AutomationLog

    if not _evaluate_conditions(automation.conditions, task, context):
        AutomationLog.objects.create(
            automation=automation,
            task=task,
            trigger_type=automation.trigger_type,
            actions_executed=[],
            status="skipped",
            error_message="Conditions not met",
        )
        return

    actions_executed = []
    try:
        for action in automation.actions.all():
            result = _execute_action(action, task, user, context)
            actions_executed.append(
                {
                    "action_type": action.action_type,
                    "result": result,
                }
            )

        AutomationLog.objects.create(
            automation=automation,
            task=task,
            trigger_type=automation.trigger_type,
            actions_executed=actions_executed,
            status="success",
        )

        # Update automation stats
        automation.runs += 1
        automation.last_run = timezone.now()
        automation.save(update_fields=["runs", "last_run"])

    except Exception as e:
        logger.exception(f"Automation {automation.id} failed for task {task.id}")
        AutomationLog.objects.create(
            automation=automation,
            task=task,
            trigger_type=automation.trigger_type,
            actions_executed=actions_executed,
            status="failed",
            error_message=str(e),
        )


def _execute_action(action_obj, task, user, context):
    """Execute a single automation action."""
    from projects.models import (
        Status,
        TaskAssignee,
        Tag,
        TaskTag,
        Subtask,
        TaskComment,
        TaskActivityLog,
        PMNotification,
    )
    from authentication.models import User

    action_type = action_obj.action_type
    config = action_obj.action_config or {}

    if action_type == "change_status":
        status_id = config.get("status_id")
        if status_id:
            try:
                new_status = Status.objects.get(id=status_id)
                old_status = task.status
                task.status = new_status
                task.save(update_fields=["status"])
                TaskActivityLog.objects.create(
                    task=task,
                    user=user,
                    action="status_change",
                    field="status",
                    old_value=old_status.name if old_status else "",
                    new_value=new_status.name,
                )
                return f"Status changed to {new_status.name}"
            except Status.DoesNotExist:
                return "Status not found"

    elif action_type == "assign_user":
        user_id = config.get("user_id")
        if user_id:
            try:
                target_user = User.objects.get(id=user_id)
                TaskAssignee.objects.get_or_create(task=task, user=target_user)
                TaskActivityLog.objects.create(
                    task=task,
                    user=user,
                    action="assignee_add",
                    field="assignee",
                    new_value=target_user.username or target_user.email,
                )
                return f"Assigned to {target_user.username or target_user.email}"
            except User.DoesNotExist:
                return "User not found"

    elif action_type == "add_tag":
        tag_id = config.get("tag_id")
        tag_name = config.get("tag_name")
        if tag_id:
            try:
                tag = Tag.objects.get(id=tag_id)
                TaskTag.objects.get_or_create(task=task, tag=tag)
                return f"Tag '{tag.name}' added"
            except Tag.DoesNotExist:
                return "Tag not found"
        elif tag_name:
            space = task.list.space if task.list else None
            tag, _ = Tag.objects.get_or_create(
                name=tag_name,
                space=space,
                defaults={"color": config.get("tag_color", "#808080")},
            )
            TaskTag.objects.get_or_create(task=task, tag=tag)
            return f"Tag '{tag.name}' added"

    elif action_type == "remove_tag":
        tag_id = config.get("tag_id")
        if tag_id:
            deleted, _ = TaskTag.objects.filter(task=task, tag_id=tag_id).delete()
            return f"Tag removed" if deleted else "Tag not found on task"

    elif action_type == "set_priority":
        priority = config.get("priority", "normal")
        old_priority = task.priority
        task.priority = priority
        task.save(update_fields=["priority"])
        TaskActivityLog.objects.create(
            task=task,
            user=user,
            action="priority_change",
            field="priority",
            old_value=old_priority,
            new_value=priority,
        )
        return f"Priority set to {priority}"

    elif action_type == "send_notification":
        message = config.get("message", "Automation triggered")
        recipient_id = config.get("recipient_id")
        recipients = []
        if recipient_id:
            recipients = [recipient_id]
        else:
            # Notify all assignees
            recipients = list(
                TaskAssignee.objects.filter(task=task).values_list("user_id", flat=True)
            )

        for rid in recipients:
            PMNotification.objects.create(
                recipient_id=rid,
                title=f"Automation: {message}",
                message=f"Task '{task.title}' - {message}",
                notification_type="automation",
                reference_type="task",
                reference_id=str(task.id),
            )
        return f"Notification sent to {len(recipients)} users"

    elif action_type == "move_to_list":
        from projects.models import List

        list_id = config.get("list_id")
        if list_id:
            try:
                new_list = List.objects.get(id=list_id)
                old_list = task.list
                task.list = new_list
                task.save(update_fields=["list"])
                TaskActivityLog.objects.create(
                    task=task,
                    user=user,
                    action="list_change",
                    field="list",
                    old_value=old_list.name if old_list else "",
                    new_value=new_list.name,
                )
                return f"Moved to list '{new_list.name}'"
            except List.DoesNotExist:
                return "List not found"

    elif action_type == "create_subtask":
        title = config.get("title", "Auto-created subtask")
        assignee_id = config.get("assignee_id")
        Subtask.objects.create(
            task=task,
            title=title,
            assignee_id=assignee_id,
        )
        return f"Subtask '{title}' created"

    elif action_type == "add_comment":
        text = config.get("text", "Automation comment")
        TaskComment.objects.create(
            task=task,
            user=user,
            text=f"[Automation] {text}",
        )
        return "Comment added"

    elif action_type == "set_due_date":
        days = config.get("days_from_now")
        specific_date = config.get("date")
        if days is not None:
            from datetime import timedelta

            task.due_date = timezone.now().date() + timedelta(days=int(days))
            task.save(update_fields=["due_date"])
            return f"Due date set to {task.due_date}"
        elif specific_date:
            task.due_date = specific_date
            task.save(update_fields=["due_date"])
            return f"Due date set to {specific_date}"

    elif action_type == "send_email":
        # Email sending placeholder - integrate with email backend
        logger.info(
            f"Automation email for task {task.id}: {config.get('subject', 'N/A')}"
        )
        return "Email action logged (email sending not configured)"

    return f"Unknown action: {action_type}"


def models_Q(**kwargs):
    """Helper to avoid circular import of Q."""
    from django.db.models import Q

    return Q(**kwargs)
