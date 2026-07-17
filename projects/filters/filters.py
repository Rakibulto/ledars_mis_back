import django_filters
from projects.models import (
    Task,
    Sprint,
    TimeEntry,
    Project,
    ProjectActivity,
    Automation,
    AutomationLog,
    Doc,
    Milestone,
    Goal,
)


class TaskFilter(django_filters.FilterSet):
    space = django_filters.NumberFilter(field_name="list__space__id")
    workspace = django_filters.NumberFilter(field_name="list__space__workspace__id")
    list = django_filters.NumberFilter(field_name="list__id")
    status = django_filters.NumberFilter(field_name="status__id")
    status_group = django_filters.CharFilter(field_name="status__group__label")
    priority = django_filters.CharFilter(field_name="priority")
    assignee = django_filters.NumberFilter(field_name="assignees__user__id")
    tag = django_filters.NumberFilter(field_name="task_tags__tag__id")
    due_date_before = django_filters.DateFilter(
        field_name="due_date", lookup_expr="lte"
    )
    due_date_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateFilter(
        field_name="created_at", lookup_expr="lte"
    )
    is_completed = django_filters.BooleanFilter(method="filter_is_completed")
    parent = django_filters.NumberFilter(field_name="parent__id")
    has_due_date = django_filters.BooleanFilter(method="filter_has_due_date")

    class Meta:
        model = Task
        fields = [
            "space",
            "workspace",
            "list",
            "status",
            "status_group",
            "priority",
            "assignee",
            "tag",
            "parent",
        ]

    def filter_is_completed(self, queryset, name, value):
        if value:
            return queryset.filter(completed_at__isnull=False)
        return queryset.filter(completed_at__isnull=True)

    def filter_has_due_date(self, queryset, name, value):
        if value:
            return queryset.filter(due_date__isnull=False)
        return queryset.filter(due_date__isnull=True)


class SprintFilter(django_filters.FilterSet):
    space = django_filters.NumberFilter(field_name="space__id")
    status = django_filters.CharFilter(field_name="status")
    start_after = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    end_before = django_filters.DateFilter(field_name="end_date", lookup_expr="lte")

    class Meta:
        model = Sprint
        fields = ["space", "status"]


class TimeEntryFilter(django_filters.FilterSet):
    task = django_filters.NumberFilter(field_name="task__id")
    user = django_filters.NumberFilter(field_name="user__id")
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    is_billable = django_filters.BooleanFilter(field_name="is_billable")
    is_running = django_filters.BooleanFilter(field_name="is_running")

    class Meta:
        model = TimeEntry
        fields = ["task", "user", "is_billable", "is_running"]


class ProjectFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status")
    donor = django_filters.CharFilter(field_name="donor", lookup_expr="icontains")
    manager = django_filters.NumberFilter(field_name="manager__id")
    start_after = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    end_before = django_filters.DateFilter(field_name="end_date", lookup_expr="lte")

    class Meta:
        model = Project
        fields = ["status", "donor", "manager"]


class ProjectActivityFilter(django_filters.FilterSet):
    project = django_filters.NumberFilter(field_name="project__id")
    status = django_filters.CharFilter(field_name="status")
    priority = django_filters.CharFilter(field_name="priority")
    department = django_filters.NumberFilter(field_name="department__id")
    responsible = django_filters.NumberFilter(field_name="responsible_person__id")

    class Meta:
        model = ProjectActivity
        fields = ["project", "status", "priority", "department"]


class AutomationFilter(django_filters.FilterSet):
    space = django_filters.NumberFilter(field_name="space__id")
    trigger_type = django_filters.CharFilter(field_name="trigger_type")
    is_active = django_filters.BooleanFilter(field_name="is_active")

    class Meta:
        model = Automation
        fields = ["space", "trigger_type", "is_active"]


class AutomationLogFilter(django_filters.FilterSet):
    automation = django_filters.NumberFilter(field_name="automation__id")
    task = django_filters.NumberFilter(field_name="task__id")
    status = django_filters.CharFilter(field_name="status")
    executed_after = django_filters.DateTimeFilter(
        field_name="executed_at", lookup_expr="gte"
    )

    class Meta:
        model = AutomationLog
        fields = ["automation", "task", "status"]


class DocFilter(django_filters.FilterSet):
    space = django_filters.NumberFilter(field_name="space__id")
    parent = django_filters.NumberFilter(field_name="parent__id")
    is_archived = django_filters.BooleanFilter(field_name="is_archived")
    is_favorite = django_filters.BooleanFilter(field_name="is_favorite")

    class Meta:
        model = Doc
        fields = ["space", "parent", "is_archived", "is_favorite"]


class MilestoneFilter(django_filters.FilterSet):
    space = django_filters.NumberFilter(field_name="space__id")
    status = django_filters.CharFilter(field_name="status")

    class Meta:
        model = Milestone
        fields = ["space", "status"]


class GoalFilter(django_filters.FilterSet):
    owner = django_filters.NumberFilter(field_name="owner__id")
    goal_type = django_filters.CharFilter(field_name="goal_type")
    status = django_filters.CharFilter(field_name="status")
    target_type = django_filters.CharFilter(field_name="target_type")

    class Meta:
        model = Goal
        fields = ["owner", "goal_type", "status", "target_type"]
