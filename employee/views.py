from django.shortcuts import get_object_or_404
from attendance.pagination import StandardResultsSetPagination
from authentication.models import User
from .models import Branch, Department, Designation, Employee, Grade, Salary
from django.db import models
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .serializers import (
    BranchSerializer,
    DepartmentSerializer,
    DesignationSerializer,
    EmployeeDetailSerializer,
    EmployeesSimpleSerializer,
    GradeSerializer,
    SalaryCreateSerializer,
    SalaryListSerializer,
    SimplifiedUserSerializer,
    EmployeeSerializer,
    EmployeeListSerializer,
)
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone


# Views for Employee Salary


class SalaryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing employee salaries.

    Access is controlled by model permissions:

    - `employee.view_salary`: can view all salary records; otherwise user sees only their own record(s).
    - `employee.add_salary`: can create salary records.
    - `employee.change_salary`: can update salary records.
    - `employee.delete_salary`: can delete salary records.

    List supports query params: employee_id, department_id, designation_id
    """

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    # Helper methods to check permissions
    def get_view_perm(self):
        return self.request.user.has_perm("employee.view_salary")

    def get_add_perm(self):
        return self.request.user.has_perm("employee.add_salary")

    def get_change_perm(self):
        return self.request.user.has_perm("employee.change_salary")

    def get_delete_perm(self):
        return self.request.user.has_perm("employee.delete_salary")

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return SalaryListSerializer
        return SalaryCreateSerializer

    # Override get_queryset to enforce permissions and support filtering
    def get_queryset(self):
        # Get queryset with related employee and creator to optimize queries
        queryset = Salary.objects.select_related("employee", "creator").order_by("-pk")
        user = self.request.user

        # Superusers and users with view_salary permission can see all records;
        # otherwise restrict to their own salary record(s).
        if not user.is_superuser and not self.get_view_perm():
            queryset = queryset.filter(employee__user=user)

        if self.action == "list":
            employee = self.request.query_params.get("employee_id")
            department = self.request.query_params.get("department_id")
            designation = self.request.query_params.get("designation_id")
            if employee:
                queryset = queryset.filter(employee__user__id=employee)
            if department:
                queryset = queryset.filter(employee__department__id=department)
            if designation:
                queryset = queryset.filter(employee__designation__id=designation)

        return queryset

    def perform_create(self, serializer):
        # Only Admin can create salary records
        if not self.get_add_perm():
            raise PermissionDenied(
                "You do not have permission to create salary records."
            )
        serializer.save(creator=self.request.user)

    def create(self, request, *args, **kwargs):
        if not self.get_add_perm():
            print("here..")
            raise PermissionDenied(
                "You do not have permission to create salary records."
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not self.get_change_perm():
            raise PermissionDenied(
                "You do not have permission to update salary records."
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not self.get_change_perm():
            raise PermissionDenied(
                "You do not have permission to update salary records."
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not self.get_delete_perm():
            raise PermissionDenied(
                "You do not have permission to delete salary records."
            )
        return super().destroy(request, *args, **kwargs)


# ViewSet for Get Employee
class EmployeeSimpleListViewSet(generics.ListAPIView):
    """
    API endpoint to retrieve a simple list of employees with their ID and name.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = EmployeesSimpleSerializer

    def get_queryset(self):
        return Employee.objects.select_related("user").order_by("-pk")


class EmployeeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing employees.

    List employees with optional filters:

    - department: Filter by department ID (exact match)
    - role: Filter by user role ID (exact match)
    - designation: Filter by designation ID (exact match)
    - status: Filter by employee status (case-insensitive exact match)
    - keyword: Search in user username, email, employee ID, employee name, personal email, personal mobile number, and official mobile number (case-insensitive partial match)
    - pagination: Set to 'true' to enable pagination and include status counts in response
    """

    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeSerializer
    pagination_class = StandardResultsSetPagination
    lookup_url_kwarg = "user_id"

    def get_queryset(self):
        queryset = Employee.objects.select_related(
            "user",
            "department",
            "designation",
            "location",
            "office_time",
            "leave_group",
        ).order_by("-pk")

        if self.action == "list":
            queryset = queryset.prefetch_related("supervisor")

            # Apply filters
            department = self.request.query_params.get("department")
            if department:
                queryset = queryset.filter(department_id=department)

            role = self.request.query_params.get("role")
            if role:
                queryset = queryset.filter(user__role_id=role)

            designation = self.request.query_params.get("designation")
            if designation:
                queryset = queryset.filter(designation_id=designation)

            status = self.request.query_params.get("status")
            if status:
                queryset = queryset.filter(status__iexact=status)

            keyword = self.request.query_params.get("keyword")
            if keyword:
                user_ids = User.objects.filter(
                    Q(username__icontains=keyword) | Q(email__icontains=keyword)
                ).values_list("id", flat=True)
                queryset = queryset.filter(
                    Q(user__in=user_ids)
                    | Q(employee_id__icontains=keyword)
                    | Q(employee_name__icontains=keyword)
                    | Q(personal_email_id__icontains=keyword)
                    | Q(personal_mobile_number__icontains=keyword)
                    | Q(official_mobile_number__icontains=keyword)
                )

        else:
            queryset = queryset.prefetch_related(
                "supervisor",
                "emergency_contact",
                "nominee",
                "user__user_permissions",
                "user__groups__permissions",
                "leave_group__leave_policies",
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return EmployeeListSerializer
        elif self.action == "retrieve":
            return EmployeeDetailSerializer
        return EmployeeSerializer

    def get_object(self):
        user_id = self.kwargs.get(self.lookup_url_kwarg)
        return get_object_or_404(self.get_queryset(), user__pk=user_id)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)

        # Add employee status counts to the response
        status_counts = Employee.objects.aggregate(
            total_count=models.Count("pk"),
            active_count=models.Count("pk", filter=models.Q(status__iexact="active")),
            inactive_count=models.Count(
                "pk", filter=models.Q(status__iexact="inactive")
            ),
            resigned_count=models.Count(
                "pk", filter=models.Q(status__iexact="resigned")
            ),
            terminated_count=models.Count(
                "pk", filter=models.Q(status__iexact="terminated")
            ),
            incomplete_count=models.Count(
                "pk", filter=models.Q(status__iexact="incomplete")
            ),
        )

        # Check if response.data is a list (no pagination) or dict (paginated)
        if isinstance(response.data, list):
            # No pagination, do not wrap
            pass
        else:
            # Paginated response, add to existing dict
            response.data["status_counts"] = {
                "total": status_counts["total_count"],
                "active": status_counts["active_count"],
                "inactive": status_counts["inactive_count"],
                "resigned": status_counts["resigned_count"],
                "terminated": status_counts["terminated_count"],
                "incomplete": status_counts["incomplete_count"],
            }

        return response

    def perform_destroy(self, instance):
        instance.status = "terminated"
        instance.resign_terminated_date = timezone.now().date()
        instance.resign_terminated_reason = "Terminated by Admin."
        instance.save()

        if instance.user:
            instance.user.is_active = False
            instance.user.save()


# ------------------ Viewset for Supervisor Employee ------------------


class SupervisorEmployeeViewSet(generics.ListAPIView):
    """
    A ViewSet for handling GET operations on Supervisor User models.
    Provides a list of users whose role is 'Supervisor'.
    """

    serializer_class = SimplifiedUserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(role__name="Supervisor")


# ------------------ Viewset for Department and Designation ------------------
class DepartmentListCreateAPIView(generics.ListCreateAPIView):
    """
    A ViewSet for handling GET/CREATE operations on Department models.
    Only users with the 'Admin' role can create departments.
    """

    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return hasattr(user, "role") and user.has_perm("employee.add_department")

    def create(self, request, *args, **kwargs):
        if not self.has_permission(request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().create(request, *args, **kwargs)


class DepartmentRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    A ViewSet for handling GET/UPDATE/DELETE operations on a specific Department model.
    Only users with the 'Admin' role can access these operations.
    """

    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return (
            hasattr(user, "role")
            and user.has_perm("employee.change_department")
            or user.has_perm("employee.delete_department")
        )

    def get_object(self):
        if not self.has_permission(self.request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().get_object()


# Designation Views
class DesignationListCreateAPIView(generics.ListCreateAPIView):
    queryset = Designation.objects.all()
    serializer_class = DesignationSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return hasattr(user, "role") and user.has_perm("employee.add_designation")

    def create(self, request, *args, **kwargs):
        if not self.has_permission(request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().create(request, *args, **kwargs)


class DesignationRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Designation.objects.all()
    serializer_class = DesignationSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return (
            hasattr(user, "role")
            and user.has_perm("employee.change_designation")
            or user.has_perm("employee.delete_designation")
        )

    def get_object(self):
        if not self.has_permission(self.request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().get_object()


# ------------------ Viewset for Branch ------------------


class BranchListCreateAPIView(generics.ListCreateAPIView):
    """
    A ViewSet for handling GET/CREATE operations on Branch models.
    Provides a list of all branches.
    """

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return hasattr(user, "role") and user.has_perm("employee.add_branch")

    def create(self, request, *args, **kwargs):
        if not self.has_permission(request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().create(request, *args, **kwargs)


class BranchRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    A ViewSet for handling GET/UPDATE/DELETE operations on a specific Branch model.
    Provides detailed information about a branch.
    """

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return (
            hasattr(user, "role")
            and user.has_perm("employee.change_branch")
            or user.has_perm("employee.delete_branch")
        )

    def get_object(self):
        if not self.has_permission(self.request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().get_object()


# ------------------ Viewset for Grade ------------------


class GradeListCreateAPIView(generics.ListCreateAPIView):
    """
    A ViewSet for handling GET/CREATE operations on Grade models.
    Provides a list of all grades.
    """

    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return hasattr(user, "role") and user.has_perm("employee.add_grade")

    def create(self, request, *args, **kwargs):
        if not self.has_permission(request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().create(request, *args, **kwargs)


class GradeRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    A ViewSet for handling GET/UPDATE/DELETE operations on a specific Grade model.
    Provides detailed information about a grade.
    """

    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return (
            hasattr(user, "role")
            and user.has_perm("employee.change_grade")
            or user.has_perm("employee.delete_grade")
        )

    def get_object(self):
        if not self.has_permission(self.request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().get_object()
