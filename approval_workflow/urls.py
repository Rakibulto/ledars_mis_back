from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ApprovalWorkflowViewSet,
    WorkflowUserListView,
)

router = DefaultRouter()
router.register('approval-workflows', ApprovalWorkflowViewSet, basename='approval-workflow')

urlpatterns = [
    path('', include(router.urls)),
    path('workflow-users/', WorkflowUserListView.as_view(), name='workflow-users'),
]
