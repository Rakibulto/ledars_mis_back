from decimal import Decimal

from approval_workflow.models import ApprovalWorkflow


def get_active_scrap_workflow():
    return (
        ApprovalWorkflow.objects.filter(
            module_type_name="inventory",
            menu_name="scrap_management",
            is_active=True,
        )
        .prefetch_related("levels__level_users__user")
        .first()
    )


def get_level_users(matched_level):
    return list(matched_level.level_users.select_related("user").all())


def get_user_level_entry(level_users, user):
    """Match by user ID first, then fall back to email for flexibility."""
    for entry in level_users:
        if entry.user_id == user.id:
            return entry
    # Fallback: match by email
    user_email = (user.email or "").lower()
    if user_email:
        for entry in level_users:
            entry_email = (entry.user.email or "").lower() if entry.user else ""
            if entry_email == user_email:
                return entry
    return None


def user_already_approved(scrap_record, user):
    user_email = (user.email or "").lower()
    if not user_email:
        return False

    for entry in scrap_record.approval_log or []:
        if (entry.get("email") or "").lower() == user_email:
            return True
    return False


def resolve_matched_level_for_scrap(scrap_record):
    workflow = get_active_scrap_workflow()
    if not workflow:
        return None, None
    matched_level = workflow.levels.first() if workflow.levels.exists() else None
    return workflow, matched_level
