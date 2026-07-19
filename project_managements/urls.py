from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdvanceViewSet,
    CurrencyViewSet,
    ProjectManagementDashboardViewSet,
    ProjectManagementExpenseViewSet,
    ProjectManagementPlanAttachmentViewSet,
    ProjectManagementPlanWorkItemViewSet,
    ProjectManagementPlanViewSet,
    ProjectManagementProjectViewSet,
    ProjectManagementUnitViewSet,
)

router = DefaultRouter()
router.register(
    r"ngo-project-units",
    ProjectManagementUnitViewSet,
    basename="project-management-units",
)
router.register(
    r"ngo-project-dashboard",
    ProjectManagementDashboardViewSet,
    basename="project-management-dashboard",
)
router.register(
    r"ngo-projects",
    ProjectManagementProjectViewSet,
    basename="project-management-projects",
)
router.register(
    r"ngo-project-plans",
    ProjectManagementPlanViewSet,
    basename="project-management-plans",
)
router.register(
    r"ngo-project-plan-attachments",
    ProjectManagementPlanAttachmentViewSet,
    basename="project-management-plan-attachments",
)
router.register(
    r"ngo-project-plan-work-items",
    ProjectManagementPlanWorkItemViewSet,
    basename="project-management-plan-work-items",
)
router.register(
    r"ngo-project-expenses",
    ProjectManagementExpenseViewSet,
    basename="project-management-expenses",
)
router.register(
    r"ngo-project-advances",
    AdvanceViewSet,
    basename="project-management-advances",
)
router.register(
    r"currencies",
    CurrencyViewSet,
    basename="project-management-currencies",
)

urlpatterns = [
    path("", include(router.urls)),
]
