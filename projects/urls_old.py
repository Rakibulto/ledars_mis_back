from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProjectViewSet,
    ProjectActivityViewSet,
    NotificationViewSet
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'activities', ProjectActivityViewSet)
router.register(r'notifications', NotificationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]