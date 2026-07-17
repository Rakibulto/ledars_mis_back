from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    DepartmentListCreateAPIView,
    EmployeeSimpleListViewSet,
    EmployeeViewSet,
    DepartmentRetrieveUpdateDestroyAPIView,
    DesignationListCreateAPIView,
    DesignationRetrieveUpdateDestroyAPIView,
    BranchListCreateAPIView,
    BranchRetrieveUpdateDestroyAPIView,
    GradeListCreateAPIView,
    GradeRetrieveUpdateDestroyAPIView,
    SalaryViewSet,
    SupervisorEmployeeViewSet,
)


router = DefaultRouter()
router.register(
    r"employees", EmployeeViewSet, basename="employee"
)  # api/employees/<int:employee_id>/  to get employee details by user_id

router.register(
    r"salaries", SalaryViewSet, basename="salary"
)  # api/salaries/<int:employee_id>/  to get salary details by employee_id
urlpatterns = [
    # Simple Employee List URL
    path(
        "employees/simple/",
        EmployeeSimpleListViewSet.as_view(),
        name="employee-simple-list",
    ),
    # Department URLs
    path("departments/", DepartmentListCreateAPIView.as_view(), name="department-list"),
    path(
        "departments/<int:pk>/",
        DepartmentRetrieveUpdateDestroyAPIView.as_view(),
        name="department-detail",
    ),
    # Designation URLs
    path(
        "designations/", DesignationListCreateAPIView.as_view(), name="designation-list"
    ),
    path(
        "designations/<int:pk>/",
        DesignationRetrieveUpdateDestroyAPIView.as_view(),
        name="designation-detail",
    ),
    # Branch URLs
    path("branches/", BranchListCreateAPIView.as_view(), name="branch-list"),
    path(
        "branches/<int:pk>/",
        BranchRetrieveUpdateDestroyAPIView.as_view(),
        name="branch-detail",
    ),
    # Grade URLs
    path("grades/", GradeListCreateAPIView.as_view(), name="grade-list"),
    path(
        "grades/<int:pk>/",
        GradeRetrieveUpdateDestroyAPIView.as_view(),
        name="grade-detail",
    ),
    # Supervisor Employee URLs
    path("supervisors/", SupervisorEmployeeViewSet.as_view(), name="supervisor-list"),
] + router.urls
