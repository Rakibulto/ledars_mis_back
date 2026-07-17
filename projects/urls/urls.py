from django.urls import path, include
from rest_framework.routers import DefaultRouter

from ..views.views import ProjectViewSet, ProjectActivityViewSet,SimpleProjectViews
from ..views.workspace_views import WorkspaceViewSet, WorkspaceMemberViewSet
from ..views.space_views import SpaceViewSet, SpaceMemberViewSet
from ..views.list_views import ListViewSet
from ..views.status_views import StatusGroupViewSet, StatusViewSet
from ..views.task_views import (
    TaskViewSet,
    TaskAssigneeViewSet,
    TaskWatcherViewSet,
    TaskDependencyViewSet,
    SubtaskViewSet,
    ChecklistViewSet,
    ChecklistItemViewSet,
    TaskAttachmentViewSet,
    TaskCommentViewSet,
    TaskActivityLogViewSet,
)
from ..views.tag_views import TagViewSet, TaskTagViewSet
from ..views.sprint_views import SprintViewSet, SprintTaskViewSet
from ..views.milestone_views import MilestoneViewSet
from ..views.goal_views import GoalViewSet, KeyResultViewSet
from ..views.time_tracking_views import TimeEntryViewSet
from ..views.doc_views import DocViewSet
from ..views.custom_field_views import (
    CustomFieldViewSet,
    CustomFieldOptionViewSet,
    TaskCustomFieldValueViewSet,
)
from ..views.automation_views import (
    AutomationViewSet,
    AutomationActionViewSet,
    AutomationLogViewSet,
)
from ..views.view_views import SavedViewViewSet
from ..views.template_views import TemplateViewSet
from ..views.form_views import FormViewSet, FormFieldViewSet, FormSubmissionViewSet
from ..views.whiteboard_views import WhiteboardViewSet
from ..views.dashboard_views import (
    DashboardViewSet,
    DashboardWidgetViewSet,
    PMDashboardStatsView,
)
from ..views.favorite_views import FavoriteViewSet
from ..views.notification_views import PMNotificationViewSet
from ..views.role_views import PMRoleViewSet, PMUserRoleViewSet


router = DefaultRouter()

# ── Core Projects (preserved from original) ──
router.register(r"projects", ProjectViewSet, basename="projects")
router.register(
    r"project-activities", ProjectActivityViewSet, basename="project-activities"
)

# ── Workspaces ──
router.register(r"pm-workspaces", WorkspaceViewSet, basename="pm-workspaces")
router.register(
    r"pm-workspace-members", WorkspaceMemberViewSet, basename="pm-workspace-members"
)

# ── Spaces ──
router.register(r"pm-spaces", SpaceViewSet, basename="pm-spaces")
router.register(r"pm-space-members", SpaceMemberViewSet, basename="pm-space-members")

# ── Lists ──
router.register(r"pm-lists", ListViewSet, basename="pm-lists")

# ── Statuses ──
router.register(r"pm-status-groups", StatusGroupViewSet, basename="pm-status-groups")
router.register(r"pm-statuses", StatusViewSet, basename="pm-statuses")

# ── Tasks ──
router.register(r"pm-tasks", TaskViewSet, basename="pm-tasks")
router.register(r"pm-task-assignees", TaskAssigneeViewSet, basename="pm-task-assignees")
router.register(r"pm-task-watchers", TaskWatcherViewSet, basename="pm-task-watchers")
router.register(
    r"pm-task-dependencies", TaskDependencyViewSet, basename="pm-task-dependencies"
)
router.register(r"pm-subtasks", SubtaskViewSet, basename="pm-subtasks")
router.register(r"pm-checklists", ChecklistViewSet, basename="pm-checklists")
router.register(
    r"pm-checklist-items", ChecklistItemViewSet, basename="pm-checklist-items"
)
router.register(
    r"pm-task-attachments", TaskAttachmentViewSet, basename="pm-task-attachments"
)
router.register(r"pm-task-comments", TaskCommentViewSet, basename="pm-task-comments")
router.register(
    r"pm-task-activity-logs", TaskActivityLogViewSet, basename="pm-task-activity-logs"
)

# ── Tags ──
router.register(r"pm-tags", TagViewSet, basename="pm-tags")
router.register(r"pm-task-tags", TaskTagViewSet, basename="pm-task-tags")

# ── Sprints ──
router.register(r"pm-sprints", SprintViewSet, basename="pm-sprints")
router.register(r"pm-sprint-tasks", SprintTaskViewSet, basename="pm-sprint-tasks")

# ── Milestones ──
router.register(r"pm-milestones", MilestoneViewSet, basename="pm-milestones")

# ── Goals ──
router.register(r"pm-goals", GoalViewSet, basename="pm-goals")
router.register(r"pm-key-results", KeyResultViewSet, basename="pm-key-results")

# ── Time Tracking ──
router.register(r"pm-time-entries", TimeEntryViewSet, basename="pm-time-entries")

# ── Docs ──
router.register(r"pm-docs", DocViewSet, basename="pm-docs")

# ── Custom Fields ──
router.register(r"pm-custom-fields", CustomFieldViewSet, basename="pm-custom-fields")
router.register(
    r"pm-custom-field-options",
    CustomFieldOptionViewSet,
    basename="pm-custom-field-options",
)
router.register(
    r"pm-task-custom-field-values",
    TaskCustomFieldValueViewSet,
    basename="pm-task-custom-field-values",
)

# ── Automations ──
router.register(r"pm-automations", AutomationViewSet, basename="pm-automations")
router.register(
    r"pm-automation-actions", AutomationActionViewSet, basename="pm-automation-actions"
)
router.register(
    r"pm-automation-logs", AutomationLogViewSet, basename="pm-automation-logs"
)

# ── Views ──
router.register(r"pm-saved-views", SavedViewViewSet, basename="pm-saved-views")

# ── Templates ──
router.register(r"pm-templates", TemplateViewSet, basename="pm-templates")

# ── Forms ──
router.register(r"pm-forms", FormViewSet, basename="pm-forms")
router.register(r"pm-form-fields", FormFieldViewSet, basename="pm-form-fields")
router.register(
    r"pm-form-submissions", FormSubmissionViewSet, basename="pm-form-submissions"
)

# ── Whiteboards ──
router.register(r"pm-whiteboards", WhiteboardViewSet, basename="pm-whiteboards")

# ── Dashboards ──
router.register(r"pm-dashboards", DashboardViewSet, basename="pm-dashboards")
router.register(
    r"pm-dashboard-widgets", DashboardWidgetViewSet, basename="pm-dashboard-widgets"
)

# ── Favorites ──
router.register(r"pm-favorites", FavoriteViewSet, basename="pm-favorites")

# ── Notifications ──
router.register(r"pm-notifications", PMNotificationViewSet, basename="pm-notifications")

# ── Roles ──
router.register(r"pm-roles", PMRoleViewSet, basename="pm-roles")
router.register(r"pm-user-roles", PMUserRoleViewSet, basename="pm-user-roles")

# ── Dashboard Stats ──
pm_dashboard_stats = PMDashboardStatsView.as_view({"get": "overview"})
pm_dashboard_workload = PMDashboardStatsView.as_view({"get": "workload"})

urlpatterns = [
    path("", include(router.urls)),
    path("simple-project/", SimpleProjectViews.as_view(), name="simple-projects"),
    path(
        "pm-dashboard-stats/overview/",
        pm_dashboard_stats,
        name="pm-dashboard-stats-overview",
    ),
    path(
        "pm-dashboard-stats/workload/",
        pm_dashboard_workload,
        name="pm-dashboard-stats-workload",
    ),
]
