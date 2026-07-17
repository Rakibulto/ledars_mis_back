from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import LeadViewSet, LeadFollowUpViewSet

router = DefaultRouter()
router.register(r'leads', LeadViewSet, basename='lead')

followup_list = LeadFollowUpViewSet.as_view({
    'get': 'list',
    'post': 'create',
})
followup_detail = LeadFollowUpViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy',
})

urlpatterns = [
    path('', include(router.urls)),
    path('leads/<int:lead_pk>/followups/', followup_list, name='lead-followup-list'),
    path('leads/<int:lead_pk>/followups/<int:pk>/', followup_detail, name='lead-followup-detail'),
]
