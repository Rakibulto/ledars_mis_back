from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

from beneficiary.urls import router as supporter_router_beneficiary
from projects.urls.urls import router as supporter_router_projects
from inventory.urls import router as supporter_router_inventory
from procurement.urls.urls import router as supporter_router_procurement
from accounting.urls.urls import router as supporter_router_accounting
from vendorportal.urls.urls import router as supporter_router_vendorportal
from donor.urls import router as supporter_router_donor
from project_managements.urls import router as supporter_router_project_managements
from returns.urls import router as supporter_router_returns
from crm.urls import router as supporter_router_crm

# Create a single central router for all API endpoints
router = DefaultRouter()
router.registry.extend(supporter_router_beneficiary.registry)
router.registry.extend(supporter_router_projects.registry)
router.registry.extend(supporter_router_inventory.registry)
router.registry.extend(supporter_router_procurement.registry)
router.registry.extend(supporter_router_accounting.registry)
router.registry.extend(supporter_router_vendorportal.registry)
router.registry.extend(supporter_router_donor.registry)
router.registry.extend(supporter_router_project_managements.registry)
router.registry.extend(supporter_router_returns.registry)
router.registry.extend(supporter_router_crm.registry)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/", include("inventory.urls")),
    path("api/", include("procurement.urls")),
    path("api/", include("beneficiary.urls")),
    path("api/", include("projects.urls")),
    path("api/", include("accounting.urls")),
    path("api-auth/", include("rest_framework.urls")),
    path("api/", include("authentication.urls")),
    path("api/", include("employee.urls")),
    path("api/", include("attendance.urls")),
    path("", include("device_attendance.urls")),
    path("api/", include("shift.urls")),
    path("api/", include("holiday.urls")),
    path("api/", include("leave.urls")),
    path("api/", include("notification.urls")),
    path("api/", include("payroll.urls")),
    path("api/", include("vendorportal.urls")),
    path("api/", include("donor.urls")),
    path("api/", include("project_managements.urls")),
    path("api/", include("returns.urls")),
    path("api/", include("approval_workflow.urls")),
    path("api/crm/", include("crm.urls")),
    path("api/", include("donor.urls")),
    path("api/todo/", include("todo.urls")),
    path("api/meeting_management/", include("meeting_management.urls")),
    path("api/", include("final_settlement.urls")),
    path("api/", include("movement_management.urls")),
    path("api/", include("travel_expense.urls")),
    path("api/", include("provident_fund.urls")),
    path("api/", include("central_dashboard.urls")),
] + static(
    settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
)  # static urls for media files
