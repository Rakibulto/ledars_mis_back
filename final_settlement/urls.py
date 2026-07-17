from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FinalSettlementViewSet

router = DefaultRouter()
router.register(r'final-settlement', FinalSettlementViewSet, basename='final-settlement')

urlpatterns = [
    path('', include(router.urls)),
]