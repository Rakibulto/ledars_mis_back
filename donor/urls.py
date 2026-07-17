from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import DonorViewSet, DonorLedgerViewSet

router = DefaultRouter()
router.register("donors", DonorViewSet, basename="donor")
router.register("donor-ledgers", DonorLedgerViewSet, basename="donorledger")

urlpatterns = [
    path("", include(router.urls)),
]
