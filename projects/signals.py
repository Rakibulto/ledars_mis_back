"""
Signals for the Project Management app.
Handles notifications, cascade updates, and automation triggers.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone


@receiver(pre_save, sender="projects.Task")
def track_task_completion(sender, instance, **kwargs):
    """Mark completed_at when task moves to a done/closed status."""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            if instance.status and instance.status.group:
                if (
                    instance.status.group.label in ("done", "closed")
                    and old.status != instance.status
                ):
                    instance.completed_at = timezone.now()
                elif (
                    instance.status.group.label not in ("done", "closed")
                    and instance.completed_at
                ):
                    instance.completed_at = None
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender="projects.Task")
def notify_task_assignees(sender, instance, created, **kwargs):
    """Send PM notification to assignees when a task is created."""
    if created:
        from projects.models import TaskAssignee, PMNotification

        assignees = TaskAssignee.objects.filter(task=instance).select_related("user")
        for assignee in assignees:
            if assignee.user != instance.created_by:
                PMNotification.objects.create(
                    recipient=assignee.user,
                    title="New Task Assigned",
                    message=f'You have been assigned to "{instance.title}"',
                    notification_type="task_assigned",
                    reference_type="task",
                    reference_id=str(instance.id),
                )


@receiver(post_save, sender="projects.TaskComment")
def notify_comment(sender, instance, created, **kwargs):
    """Notify task assignees and watchers when a new comment is added."""
    if created:
        from projects.models import TaskAssignee, TaskWatcher, PMNotification

        task = instance.task
        notified = set()

        # Notify assignees
        for assignee in TaskAssignee.objects.filter(task=task).select_related("user"):
            if assignee.user != instance.user and assignee.user_id not in notified:
                PMNotification.objects.create(
                    recipient=assignee.user,
                    title="New Comment",
                    message=f'{instance.user.username or instance.user.email} commented on "{task.title}"',
                    notification_type="comment_added",
                    reference_type="task",
                    reference_id=str(task.id),
                )
                notified.add(assignee.user_id)

        # Notify watchers
        for watcher in TaskWatcher.objects.filter(task=task).select_related("user"):
            if watcher.user != instance.user and watcher.user_id not in notified:
                PMNotification.objects.create(
                    recipient=watcher.user,
                    title="New Comment",
                    message=f'{instance.user.username or instance.user.email} commented on "{task.title}"',
                    notification_type="comment_added",
                    reference_type="task",
                    reference_id=str(task.id),
                )
                notified.add(watcher.user_id)


@receiver(post_save, sender="projects.SprintTask")
def notify_sprint_assignment(sender, instance, created, **kwargs):
    """Notify when a task is added to a sprint."""
    if created:
        from projects.models import TaskAssignee, PMNotification

        task = instance.task
        sprint = instance.sprint
        for assignee in TaskAssignee.objects.filter(task=task).select_related("user"):
            PMNotification.objects.create(
                recipient=assignee.user,
                title="Task Added to Sprint",
                message=f'"{task.title}" was added to sprint "{sprint.name}"',
                notification_type="sprint_update",
                reference_type="task",
                reference_id=str(task.id),
            )


@receiver(post_save, sender="projects.Milestone")
def check_milestone_status(sender, instance, **kwargs):
    """Auto-update milestone status based on target date."""
    if instance.status == "upcoming" and instance.target_date:
        if instance.target_date < timezone.now().date():
            sender.objects.filter(pk=instance.pk).update(status="overdue")
