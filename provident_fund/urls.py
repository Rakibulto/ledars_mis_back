from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ProvidentFundLoanViewSet

router = DefaultRouter()
router.register(r'provident-fund', ProvidentFundLoanViewSet, basename='provident-fund')

urlpatterns = [
    path('', include(router.urls)),
]
