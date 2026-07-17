from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import TravelExpenseViewSet

router = DefaultRouter()
router.register(r'travel-expense', TravelExpenseViewSet, basename='travel-expense')

urlpatterns = [
    path('', include(router.urls)),
]
