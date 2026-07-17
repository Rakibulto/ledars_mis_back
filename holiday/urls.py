from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HolidayViewSet

# Create a router and register the HolidayViewSet
router = DefaultRouter()
router.register(r'holidays', HolidayViewSet, basename='holiday')

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
]