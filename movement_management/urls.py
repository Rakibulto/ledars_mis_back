from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import MovementManagementViewSet

router = DefaultRouter()
router.register(r'movement-management', MovementManagementViewSet, basename='movement-management')

urlpatterns = [
    path('', include(router.urls)),
]
