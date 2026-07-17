from decimal import Decimal

from approval_workflow.models import ApprovalWorkflow


def get_active_gin_workflow():
    return (
        ApprovalWorkflow.objects.filter(
            module_type_name="inventory",
            menu_name="good_issue_note",
            is_active=True,
        )
        .prefetch_related("levels__level_users__user")
        .first()
    )


def compute_gin_total_value(gin):
    lines = gin.line_items.select_related("product").all()
    if lines:
        total = sum(
            Decimal(str(line.issued_qty or 0)) * Decimal(str(line.unit_price or 0))
            for line in lines
        )
        if total > 0:
            return total
    return Decimal(str(gin.total_value or 0))


def find_matched_level(workflow, total_value):
    if not workflow:
        return None

    for level in workflow.levels.all():
        from_amt = Decimal(str(level.from_amount or 0))
        to_amt = level.to_amount
        if to_amt is None:
            if total_value >= from_amt:
                return level
        else:
            to_amt = Decimal(str(to_amt))
            if from_amt <= total_value <= to_amt:
                return level
    return None



def get_level_users(matched_level):
    return list(matched_level.level_users.select_related("user").all())


def get_user_level_entry(level_users, user):
    return next((entry for entry in level_users if entry.user_id == user.id), None)


def user_already_approved(gin, user):
    user_email = (user.email or "").lower()
    if not user_email:
        return False

    for entry in gin.approval_log or []:
        if (entry.get("email") or "").lower() == user_email:
            return True
    return False


def resolve_matched_level_for_gin(gin):
    workflow = get_active_gin_workflow()
    if not workflow:
        return None, None
    total_value = compute_gin_total_value(gin)
    matched_level = find_matched_level(workflow, total_value)
    return workflow, matched_level
