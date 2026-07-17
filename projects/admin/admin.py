from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from projects.models import (
    Project,
    ProjectActivity,
    Workspace,
    WorkspaceMember,
    Space,
    SpaceMember,
    List,
    StatusGroup,
    Status,
    Task,
    TaskAssignee,
    TaskWatcher,
    TaskDependency,
    Subtask,
    Checklist,
    ChecklistItem,
    TaskAttachment,
    TaskComment,
    TaskActivityLog,
    Tag,
    TaskTag,
    Sprint,
    SprintTask,
    Milestone,
    MilestoneTask,
    Goal,
    KeyResult,
    TimeEntry,
    Doc,
    CustomField,
    CustomFieldOption,
    TaskCustomFieldValue,
    Automation,
    AutomationAction,
    AutomationLog,
    SavedView,
    Template,
    Form,
    FormField,
    FormSubmission,
    Whiteboard,
    Dashboard,
    DashboardWidget,
    Favorite,
    PMNotification,
    PMRole,
    PMUserRole,
)


# ── Core Projects ──
class ProjectActivityInline(TabularInline):
    model = ProjectActivity
    extra = 0


@admin.register(Project)
class ProjectAdmin(ModelAdmin):
    list_display = [
        "code",
        "name",
        "donor",
        "status",
        "manager",
        "start_date",
        "end_date",
    ]
    list_filter = ["status", "donor"]
    search_fields = ["code", "name", "donor"]
    inlines = [ProjectActivityInline]


@admin.register(ProjectActivity)
class ProjectActivityAdmin(ModelAdmin):
    list_display = [
        "title",
        "project",
        "status",
        "priority",
        "responsible_person",
        "start_date",
        "due_date",
    ]
    list_filter = ["status", "priority"]
    search_fields = ["title"]


# ── Workspaces ──
class WorkspaceMemberInline(TabularInline):
    model = WorkspaceMember
    extra = 0


@admin.register(Workspace)
class WorkspaceAdmin(ModelAdmin):
    list_display = ["name", "is_active", "created_at"]
    search_fields = ["name"]
    inlines = [WorkspaceMemberInline]


# ── Spaces ──
class SpaceMemberInline(TabularInline):
    model = SpaceMember
    extra = 0


@admin.register(Space)
class SpaceAdmin(ModelAdmin):
    list_display = ["name", "workspace", "is_private", "created_at"]
    list_filter = ["workspace", "is_private"]
    search_fields = ["name"]
    inlines = [SpaceMemberInline]


# ── Lists ──
@admin.register(List)
class ListAdmin(ModelAdmin):
    list_display = ["name", "space", "position"]
    list_filter = ["space"]
    search_fields = ["name"]


# ── Statuses ──
@admin.register(StatusGroup)
class StatusGroupAdmin(ModelAdmin):
    list_display = ["name", "label", "space", "position", "is_default"]
    list_filter = ["space"]


@admin.register(Status)
class StatusAdmin(ModelAdmin):
    list_display = ["name", "group", "space", "position", "is_default"]
    list_filter = ["space", "group"]


# ── Tasks ──
class TaskAssigneeInline(TabularInline):
    model = TaskAssignee
    extra = 0


class SubtaskInline(TabularInline):
    model = Subtask
    extra = 0


@admin.register(Task)
class TaskAdmin(ModelAdmin):
    list_display = [
        "task_id",
        "title",
        "status",
        "priority",
        "list",
        "due_date",
        "created_at",
    ]
    list_filter = ["priority", "status", "list__space"]
    search_fields = ["task_id", "title"]
    inlines = [TaskAssigneeInline, SubtaskInline]


@admin.register(TaskComment)
class TaskCommentAdmin(ModelAdmin):
    list_display = ["task", "user", "text", "created_at"]
    list_filter = ["created_at"]


@admin.register(TaskActivityLog)
class TaskActivityLogAdmin(ModelAdmin):
    list_display = ["task", "user", "action", "field", "timestamp"]
    list_filter = ["action"]


# ── Tags ──
@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ["name", "color", "space"]
    list_filter = ["space"]


# ── Sprints ──
class SprintTaskInline(TabularInline):
    model = SprintTask
    extra = 0


@admin.register(Sprint)
class SprintAdmin(ModelAdmin):
    list_display = ["name", "space", "status", "start_date", "end_date", "velocity"]
    list_filter = ["status", "space"]
    search_fields = ["name"]
    inlines = [SprintTaskInline]


# ── Milestones ──
@admin.register(Milestone)
class MilestoneAdmin(ModelAdmin):
    list_display = ["name", "space", "status", "target_date"]
    list_filter = ["status", "space"]


# ── Goals ──
class KeyResultInline(TabularInline):
    model = KeyResult
    extra = 0


@admin.register(Goal)
class GoalAdmin(ModelAdmin):
    list_display = ["name", "owner", "goal_type", "status", "start_date", "end_date"]
    list_filter = ["goal_type", "status"]
    search_fields = ["name"]
    inlines = [KeyResultInline]


# ── Time Tracking ──
@admin.register(TimeEntry)
class TimeEntryAdmin(ModelAdmin):
    list_display = ["task", "user", "date", "duration", "is_billable", "is_running"]
    list_filter = ["is_billable", "is_running", "date"]


# ── Docs ──
@admin.register(Doc)
class DocAdmin(ModelAdmin):
    list_display = ["title", "space", "is_favorite", "is_archived", "created_at"]
    list_filter = ["space", "is_archived"]
    search_fields = ["title"]


# ── Custom Fields ──
@admin.register(CustomField)
class CustomFieldAdmin(ModelAdmin):
    list_display = ["name", "field_type", "space", "required", "is_active"]
    list_filter = ["field_type", "space"]


# ── Automations ──
class AutomationActionInline(TabularInline):
    model = AutomationAction
    extra = 0


@admin.register(Automation)
class AutomationAdmin(ModelAdmin):
    list_display = ["name", "trigger_type", "space", "is_active", "runs", "last_run"]
    list_filter = ["trigger_type", "is_active", "space"]
    search_fields = ["name"]
    inlines = [AutomationActionInline]


@admin.register(AutomationLog)
class AutomationLogAdmin(ModelAdmin):
    list_display = ["automation", "task", "trigger_type", "status", "executed_at"]
    list_filter = ["status", "trigger_type"]


# ── Templates ──
@admin.register(Template)
class TemplateAdmin(ModelAdmin):
    list_display = ["name", "category", "industry", "usage_count", "is_public"]
    list_filter = ["category", "is_public"]
    search_fields = ["name"]


# ── Forms ──
@admin.register(Form)
class FormAdmin(ModelAdmin):
    list_display = ["name", "space", "is_active", "submissions_count"]
    list_filter = ["is_active", "space"]


# ── Whiteboards ──
@admin.register(Whiteboard)
class WhiteboardAdmin(ModelAdmin):
    list_display = ["name", "space", "elements_count", "created_at"]
    list_filter = ["space"]


# ── Dashboards ──
@admin.register(Dashboard)
class DashboardAdmin(ModelAdmin):
    list_display = ["name", "is_default", "created_at"]


# ── Favorites ──
@admin.register(Favorite)
class FavoriteAdmin(ModelAdmin):
    list_display = ["user", "item_type", "name", "added_at"]
    list_filter = ["item_type"]


# ── Notifications ──
@admin.register(PMNotification)
class PMNotificationAdmin(ModelAdmin):
    list_display = ["recipient", "title", "notification_type", "is_read", "created_at"]
    list_filter = ["notification_type", "is_read"]


# ── Roles ──
@admin.register(PMRole)
class PMRoleAdmin(ModelAdmin):
    list_display = ["name", "is_active"]
    search_fields = ["name"]


@admin.register(PMUserRole)
class PMUserRoleAdmin(ModelAdmin):
    list_display = ["user", "role"]
    list_filter = ["role"]


# Register remaining models with Unfold ModelAdmin
@admin.register(WorkspaceMember)
class WorkspaceMemberAdmin(ModelAdmin):
    list_display = ["workspace", "user", "role"]
    list_filter = ["role"]


@admin.register(SpaceMember)
class SpaceMemberAdmin(ModelAdmin):
    list_display = ["space", "user", "role"]
    list_filter = ["role"]


@admin.register(TaskAssignee)
class TaskAssigneeAdmin(ModelAdmin):
    list_display = ["task", "user"]


@admin.register(TaskWatcher)
class TaskWatcherAdmin(ModelAdmin):
    list_display = ["task", "user"]


@admin.register(TaskDependency)
class TaskDependencyAdmin(ModelAdmin):
    list_display = ["task", "depends_on", "dependency_type"]
    list_filter = ["dependency_type"]


@admin.register(Checklist)
class ChecklistAdmin(ModelAdmin):
    list_display = ["name", "task", "position"]


@admin.register(ChecklistItem)
class ChecklistItemAdmin(ModelAdmin):
    list_display = ["text", "checklist", "is_done", "assignee"]
    list_filter = ["is_done"]


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(ModelAdmin):
    list_display = ["file_name", "task", "uploaded_by", "uploaded_at"]


@admin.register(TaskTag)
class TaskTagAdmin(ModelAdmin):
    list_display = ["task", "tag"]


@admin.register(SprintTask)
class SprintTaskAdmin(ModelAdmin):
    list_display = ["sprint", "task"]


@admin.register(MilestoneTask)
class MilestoneTaskAdmin(ModelAdmin):
    list_display = ["milestone", "task"]


@admin.register(KeyResult)
class KeyResultAdmin(ModelAdmin):
    list_display = ["name", "goal", "target", "current", "position"]


@admin.register(CustomFieldOption)
class CustomFieldOptionAdmin(ModelAdmin):
    list_display = ["label", "field", "color", "position"]


@admin.register(TaskCustomFieldValue)
class TaskCustomFieldValueAdmin(ModelAdmin):
    list_display = ["task", "field", "value"]


@admin.register(AutomationAction)
class AutomationActionAdmin(ModelAdmin):
    list_display = ["automation", "action_type", "position"]
    list_filter = ["action_type"]


@admin.register(SavedView)
class SavedViewAdmin(ModelAdmin):
    list_display = ["name", "view_type", "is_default", "is_shared"]
    list_filter = ["view_type"]


@admin.register(FormField)
class FormFieldAdmin(ModelAdmin):
    list_display = ["label", "form", "field_type", "required", "position"]
    list_filter = ["field_type", "required"]


@admin.register(FormSubmission)
class FormSubmissionAdmin(ModelAdmin):
    list_display = ["form", "submitted_by", "task_created", "submitted_at"]


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(ModelAdmin):
    list_display = ["title", "dashboard", "widget_type", "position_x", "position_y"]
    list_filter = ["widget_type"]


@admin.register(Subtask)
class SubtaskAdmin(ModelAdmin):
    list_display = ["title", "task", "is_done", "assignee", "position"]
    list_filter = ["is_done"]
