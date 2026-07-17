from django.db.models import Prefetch
from django.utils import timezone

from project_managements.models import (
    ProjectManagementPlanWorkItem,
    ProjectManagementProject,
    ProjectManagementProjectPlan,
)


def _to_float(value):
    return float(value or 0)


def _safe_username(user):
    if not user:
        return "Unassigned"
    return user.username or "Unknown user"


def _normalize_project_status(project, plans, work_items):
    if project.status in {"Completed", "Closed", "On Hold", "Planning", "Draft"}:
        return project.status

    if not plans:
        return "Planning"

    completed_plans = sum(1 for plan in plans if plan.status == "Completed")
    active_plans = sum(1 for plan in plans if plan.status in {"In Progress", "Active"})
    on_hold_plans = sum(1 for plan in plans if plan.status == "On Hold")
    completed_work_items = sum(1 for item in work_items if item.state == "Done")
    active_work_items = sum(1 for item in work_items if item.state == "Doing")

    if completed_plans == len(plans):
        return "Completed"

    if on_hold_plans and not active_plans and not active_work_items:
        return "On Hold"

    if active_plans or active_work_items or completed_plans or completed_work_items:
        return "Active"

    return "Planning"


def _calculate_plan_progress_percent(plan):
    status = plan.status or "Pending"

    if status == "Completed":
        return 100

    work_items = list(plan.work_items.all())
    if work_items:
        completed_work_items = sum(1 for item in work_items if item.state == "Done")
        return round((completed_work_items / len(work_items)) * 100)

    if status in {"In Progress", "Active"}:
        return 50

    return 0


def build_project_management_dashboard_payload():
    today = timezone.localdate()

    work_item_prefetch = Prefetch(
        "work_items",
        queryset=ProjectManagementPlanWorkItem.objects.select_related("assigned_to", "approved_by").prefetch_related("attachments"),
    )
    plan_prefetch = Prefetch(
        "plans",
        queryset=ProjectManagementProjectPlan.objects.select_related("approved_by").prefetch_related(
            "assigned_users",
            work_item_prefetch,
            "attachments__uploaded_by",
        ),
    )

    projects = list(
        ProjectManagementProject.objects.select_related("donor", "project_manager", "created_by")
        .prefetch_related("assigned_users", plan_prefetch)
        .order_by("-updated_at", "-created_at")
    )

    overview = {
        "totalProjects": len(projects),
        "activeProjects": 0,
        "completedProjects": 0,
        "onHoldProjects": 0,
        "planningProjects": 0,
        "pendingProjects": 0,
        "closedProjects": 0,
        "totalBudget": 0.0,
        "totalPlans": 0,
        "completedPlans": 0,
        "inProgressPlans": 0,
        "onHoldPlans": 0,
        "pendingPlans": 0,
        "totalWorkItems": 0,
        "completedWorkItems": 0,
        "inProgressWorkItems": 0,
        "pendingWorkItems": 0,
        "overduePlans": 0,
        "overdueWorkItems": 0,
        "unassignedPlans": 0,
        "projectCompletionRate": 0,
        "planCompletionRate": 0,
        "workItemCompletionRate": 0,
        "totalTrackedAttachments": 0,
        "recentProjects": [],
        "statusDistribution": [],
        "projectProgressRows": [],
        "donorRows": [],
        "priorityActions": [],
        "teamLoadRows": [],
        "timelineHealth": {
            "onTrack": 0,
            "atRisk": 0,
            "overdue": 0,
            "blocked": 0,
        },
        "upcomingDeadlines": [],
    }

    donor_map = {}
    assignee_map = {}
    recent_candidates = []
    deadline_candidates = []

    for project in projects:
        plans = list(project.plans.all())
        project_work_items = [item for plan in plans for item in plan.work_items.all()]
        derived_status = _normalize_project_status(project, plans, project_work_items)

        completed_plans = sum(1 for plan in plans if plan.status == "Completed")
        in_progress_plans = sum(1 for plan in plans if plan.status in {"In Progress", "Active"})
        on_hold_plans = sum(1 for plan in plans if plan.status == "On Hold")
        pending_plans = len(plans) - completed_plans - in_progress_plans - on_hold_plans
        overdue_plans = sum(
            1
            for plan in plans
            if plan.end_date and plan.status != "Completed" and plan.end_date < today
        )
        unassigned_plans = sum(1 for plan in plans if not plan.assigned_users.exists())

        completed_work_items = sum(1 for item in project_work_items if item.state == "Done")
        in_progress_work_items = sum(1 for item in project_work_items if item.state == "Doing")
        pending_work_items = sum(1 for item in project_work_items if item.state == "Todo")
        overdue_work_items = sum(
            1
            for item in project_work_items
            if item.scheduled_date and item.state != "Done" and item.scheduled_date < today
        )
        at_risk_work_items = sum(
            1
            for item in project_work_items
            if item.scheduled_date
            and item.state != "Done"
            and 0 <= (item.scheduled_date - today).days <= 7
        )
        attachment_count = sum(item.attachments.count() for item in project_work_items) + sum(plan.attachments.count() for plan in plans)

        overview["totalBudget"] += _to_float(project.budget_amount)
        overview["totalPlans"] += len(plans)
        overview["completedPlans"] += completed_plans
        overview["inProgressPlans"] += in_progress_plans
        overview["onHoldPlans"] += on_hold_plans
        overview["pendingPlans"] += pending_plans
        overview["overduePlans"] += overdue_plans
        overview["unassignedPlans"] += unassigned_plans
        overview["totalWorkItems"] += len(project_work_items)
        overview["completedWorkItems"] += completed_work_items
        overview["inProgressWorkItems"] += in_progress_work_items
        overview["pendingWorkItems"] += pending_work_items
        overview["overdueWorkItems"] += overdue_work_items
        overview["totalTrackedAttachments"] += attachment_count

        if derived_status == "Active":
            overview["activeProjects"] += 1
        elif derived_status == "Completed":
            overview["completedProjects"] += 1
        elif derived_status == "On Hold":
            overview["onHoldProjects"] += 1
        elif derived_status == "Closed":
            overview["closedProjects"] += 1
        else:
            overview["planningProjects"] += 1
            overview["pendingProjects"] += 1

        if overdue_plans or overdue_work_items:
            overview["timelineHealth"]["overdue"] += 1
        elif on_hold_plans or derived_status == "On Hold":
            overview["timelineHealth"]["blocked"] += 1
        elif at_risk_work_items:
            overview["timelineHealth"]["atRisk"] += 1
        elif in_progress_plans or in_progress_work_items:
            overview["timelineHealth"]["onTrack"] += 1
        else:
            overview["timelineHealth"]["onTrack"] += 1

        progress_percent = 0
        if plans:
            total_plan_progress = sum(_calculate_plan_progress_percent(plan) for plan in plans)
            progress_percent = round(total_plan_progress / len(plans))

        progress_summary = f"{completed_plans}/{len(plans)} roadmap steps complete" if plans else "No roadmap steps yet"
        progress_detail_parts = []
        if project_work_items:
            progress_detail_parts.append(f"{completed_work_items}/{len(project_work_items)} work items done")
        if in_progress_work_items:
            progress_detail_parts.append(f"{in_progress_work_items} in progress")
        if overdue_plans or overdue_work_items:
            progress_detail_parts.append(f"{overdue_plans + overdue_work_items} overdue")
        if unassigned_plans:
            progress_detail_parts.append(f"{unassigned_plans} steps unassigned")

        project_row = {
            "id": project.id,
            "title": project.title,
            "code": project.code,
            "donorName": project.donor.name if project.donor else "—",
            "projectManagerName": _safe_username(project.project_manager),
            "budgetAmount": _to_float(project.budget_amount),
            "currency": project.currency or "BDT",
            "derivedStatus": derived_status,
            "progressPercent": progress_percent,
            "progressSummary": progress_summary,
            "progressDetail": " • ".join(progress_detail_parts) or progress_summary,
            "plansCount": len(plans),
            "completedPlans": completed_plans,
            "totalWorkItems": len(project_work_items),
            "completedWorkItems": completed_work_items,
            "overdueCount": overdue_plans + overdue_work_items,
            "startDate": project.start_date.isoformat() if project.start_date else None,
            "endDate": project.end_date.isoformat() if project.end_date else None,
            "updatedAt": project.updated_at.isoformat() if project.updated_at else None,
        }
        overview["projectProgressRows"].append(project_row)
        recent_candidates.append((project.updated_at or project.created_at, project_row))

        donor_name = project.donor.name if project.donor else None
        if donor_name:
            donor_row = donor_map.setdefault(
                donor_name,
                {
                    "donorName": donor_name,
                    "projects": 0,
                    "budgetAmount": 0.0,
                    "completedProjects": 0,
                    "activeProjects": 0,
                },
            )
            donor_row["projects"] += 1
            donor_row["budgetAmount"] += _to_float(project.budget_amount)
            if derived_status == "Completed":
                donor_row["completedProjects"] += 1
            if derived_status == "Active":
                donor_row["activeProjects"] += 1

        for item in project_work_items:
            assignee_name = _safe_username(item.assigned_to)
            assignee_row = assignee_map.setdefault(
                assignee_name,
                {
                    "username": assignee_name,
                    "total": 0,
                    "done": 0,
                    "doing": 0,
                    "todo": 0,
                    "approved": 0,
                },
            )
            assignee_row["total"] += 1
            if item.state == "Done":
                assignee_row["done"] += 1
            elif item.state == "Doing":
                assignee_row["doing"] += 1
            else:
                assignee_row["todo"] += 1
            if item.approval_status == "Approved":
                assignee_row["approved"] += 1

            scheduled_point = item.scheduled_end_date or item.scheduled_date
            if scheduled_point and item.state != "Done":
                days_left = (scheduled_point - today).days
                deadline_candidates.append(
                    {
                        "id": item.id,
                        "title": item.title,
                        "projectId": project.id,
                        "projectTitle": project.title,
                        "planId": item.plan_id,
                        "planTitle": item.plan.title,
                        "assignee": assignee_name,
                        "scheduledDate": scheduled_point.isoformat(),
                        "daysLeft": days_left,
                        "state": item.state,
                    }
                )

    overview["projectCompletionRate"] = round((overview["completedProjects"] / overview["totalProjects"]) * 100) if overview["totalProjects"] else 0
    overview["planCompletionRate"] = round((overview["completedPlans"] / overview["totalPlans"]) * 100) if overview["totalPlans"] else 0
    overview["workItemCompletionRate"] = round((overview["completedWorkItems"] / overview["totalWorkItems"]) * 100) if overview["totalWorkItems"] else 0

    overview["statusDistribution"] = [
        {"label": "Active", "count": overview["activeProjects"], "color": "success"},
        {"label": "Completed", "count": overview["completedProjects"], "color": "info"},
        {"label": "On Hold", "count": overview["onHoldProjects"], "color": "warning"},
        {"label": "Pending", "count": overview["pendingProjects"], "color": "default"},
    ]

    overview["projectProgressRows"] = sorted(
        overview["projectProgressRows"],
        key=lambda row: (-row["progressPercent"], -row["budgetAmount"], row["title"].lower()),
    )[:8]
    overview["recentProjects"] = [row for _, row in sorted(recent_candidates, key=lambda item: item[0], reverse=True)[:6]]
    overview["donorRows"] = sorted(donor_map.values(), key=lambda row: (-row["budgetAmount"], row["donorName"].lower()))[:6]
    overview["teamLoadRows"] = sorted(
        (
            {
                **row,
                "progress": round((row["done"] / row["total"]) * 100) if row["total"] else 0,
            }
            for row in assignee_map.values()
        ),
        key=lambda row: (-row["total"], row["username"].lower()),
    )[:8]
    overview["upcomingDeadlines"] = sorted(
        deadline_candidates,
        key=lambda item: (item["daysLeft"], item["projectTitle"].lower(), item["title"].lower()),
    )[:7]

    if overview["overdueWorkItems"]:
        overview["priorityActions"].append(
            f"Resolve {overview['overdueWorkItems']} overdue work item{'s' if overview['overdueWorkItems'] != 1 else ''} still behind schedule."
        )
    if overview["overduePlans"]:
        overview["priorityActions"].append(
            f"Review {overview['overduePlans']} overdue roadmap step{'s' if overview['overduePlans'] != 1 else ''} and reset delivery dates."
        )
    if overview["onHoldProjects"]:
        overview["priorityActions"].append(
            f"Restart or close {overview['onHoldProjects']} on-hold project{'s' if overview['onHoldProjects'] != 1 else ''} after stakeholder review."
        )
    if overview["unassignedPlans"]:
        overview["priorityActions"].append(
            f"Assign owners to {overview['unassignedPlans']} roadmap step{'s' if overview['unassignedPlans'] != 1 else ''} with no accountable lead."
        )
    if overview["planningProjects"]:
        overview["priorityActions"].append(
            f"Break down {overview['planningProjects']} planning project{'s' if overview['planningProjects'] != 1 else ''} into execution-ready roadmap steps."
        )
    if not overview["priorityActions"]:
        overview["priorityActions"].append(
            "Portfolio health looks strong. Keep monitoring approvals, upcoming dates, and assignee workload balance."
        )

    overview["statusDistribution"] = [
        item for item in overview["statusDistribution"] if item["count"] > 0 or overview["totalProjects"] == 0
    ]

    return overview