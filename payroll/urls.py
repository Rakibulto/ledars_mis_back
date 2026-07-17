from rest_framework.routers import DefaultRouter
from django.urls import path, include
from payroll.views import (
    PayrollListViewSet,
    PayrollDetailViewSet,
    GeneratePayrollView,
    LockPayrollView,
)

router = DefaultRouter()
urlpatterns = router.urls + [
    path("payrolls/", PayrollListViewSet.as_view(), name="payroll-list"),
    path("payrolls/<int:pk>/", PayrollDetailViewSet.as_view(), name="payroll-detail"),
    path("payrolls/generate/", GeneratePayrollView.as_view(), name="payroll-generate"),
    path("payrolls/lock/", LockPayrollView.as_view(), name="payroll-lock"),
]
