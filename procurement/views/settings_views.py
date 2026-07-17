from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from django.db.models import Q
from django.db import transaction
from paginations import Pagination
from authentication.models import User
from employee.models import Employee
from inventory.views import CreatedByMixin
from ..models.settings_models import (
    ApprovalMatrix,
    EmailTemplate,
    ProcurementRole,
    ProcurementUserRole,
    NotificationSetting,
    UserManagement,
)
from ..serializers.settings_serializers import (
    ApproverUserSerializer,
    ApprovalMatrixSerializer,
    EmailTemplateSerializer,
    ProcurementRoleSerializer,
    ProcurementUserRoleSerializer,
    NotificationSettingSerializer,
    SimpleUserSerializer,
    UserManagementSerializer,
)


class ApprovalMatrixViewSet(viewsets.ModelViewSet):
    queryset = (
        ApprovalMatrix.objects.select_related("approver", "department")
        .prefetch_related("approvers__designation")
        .all()
    )
    serializer_class = ApprovalMatrixSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["module", "approver_role"]
    ordering = ["module", "approval_level"]
    filterset_fields = ["type", "module", "is_active"]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="form-options")
    def form_options(self, request):
        employees = list(
            Employee.objects.select_related("designation", "user")
            .filter(
                Q(status="active") | Q(user__is_staff=True) | Q(user__is_superuser=True)
            )
            .order_by("employee_name")
            .values("pk", "employee_name", "designation__name")
        )
        return Response(
            {
                "employees": [
                    {
                        "id": e["pk"],
                        "name": e["employee_name"],
                        "designation": e["designation__name"] or "",
                    }
                    for e in employees
                ]
            }
        )


class EmailTemplateViewSet(CreatedByMixin, viewsets.ModelViewSet):
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ["name", "subject"]
    filterset_fields = ["module", "is_active"]


class ProcurementRoleViewSet(viewsets.ModelViewSet):
    queryset = ProcurementRole.objects.all()
    serializer_class = ProcurementRoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ["name"]
    filterset_fields = ["is_active"]


class ProcurementUserRoleViewSet(viewsets.ModelViewSet):
    queryset = ProcurementUserRole.objects.select_related("user", "role").all()
    serializer_class = ProcurementUserRoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["user", "role"]


class NotificationSettingViewSet(viewsets.ModelViewSet):
    queryset = NotificationSetting.objects.all()
    serializer_class = NotificationSettingSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["module", "is_active"]


class UserManagementFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    role = django_filters.CharFilter(method="filter_role")
    department = django_filters.CharFilter(method="filter_department")

    def filter_role(self, queryset, name, value):
        if value.isdigit():
            return queryset.filter(role_id=value)
        return queryset.filter(role__name__iexact=value)

    def filter_department(self, queryset, name, value):
        if value.isdigit():
            return queryset.filter(department_id=value)
        return queryset.filter(department__name__iexact=value)

    class Meta:
        model = UserManagement
        fields = ["status", "role", "department"]


class UserManagementViewSet(viewsets.ModelViewSet):
    queryset = UserManagement.objects.select_related("user", "role", "department").all()
    serializer_class = UserManagementSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = UserManagementFilter
    search_fields = [
        "username",
        "email",
        "name",
        "role__name",
        "department__name",
        "phone",
    ]
    ordering = ["-created_at"]


class SimpleUserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SimpleUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = [
        "username",
        "email",
        "first_name",
        "last_name",
        "role__name",
        "department__name",
        "employee__employee_name",
        "user_management_profile__name",
    ]
    ordering = ["username", "email"]

    def get_queryset(self):
        return _active_non_vendor_auth_user_queryset()


def _active_non_vendor_auth_user_queryset():
    return (
        User.objects.select_related(
            "role",
            "department",
            "employee",
            "user_management_profile",
            "user_management_profile__role",
            "user_management_profile__department",
        )
        .filter(is_active=True)
        .exclude(
            Q(role__name__iexact="vendor")
            | Q(vendor_profile__isnull=False)
            | Q(user_management_profile__role__name__iexact="vendor")
            | Q(user_management_profile__status__iexact="inactive")
        )
        .order_by("username", "email")
        .distinct()
    )


class AproverUserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ApproverUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = [
        "username",
        "email",
        "role__name",
        "employee__employee_name",
        "user_management_profile__name",
    ]
    ordering = ["username", "email"]

    def get_queryset(self):
        return _active_non_vendor_auth_user_queryset()
