from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReturnHeaderViewSet, ReturnLineViewSet, ReturnDamageHistoryViewSet

router = DefaultRouter()
router.register('returns', ReturnHeaderViewSet, basename='return')
router.register('return-lines', ReturnLineViewSet, basename='return-line')
router.register('return-damage-histories', ReturnDamageHistoryViewSet, basename='return-damage-history')

urlpatterns = [
    path('', include(router.urls)),
]

__all__ = ['urlpatterns', 'router']
