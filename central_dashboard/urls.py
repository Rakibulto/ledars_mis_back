from django.urls import path
from .views import CentralDashboardAPIView

urlpatterns = [
    path("central-dashboard/", CentralDashboardAPIView.as_view(), name="central-dashboard"),
]
