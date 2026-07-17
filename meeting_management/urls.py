from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import MeetingViewSet, MeetingAttachmentViewSet

router = DefaultRouter()
router.register(r'meetings', MeetingViewSet, basename='meeting')

meeting_attachment_list = MeetingAttachmentViewSet.as_view({
    'get': 'list',
    'post': 'create',
})
meeting_attachment_detail = MeetingAttachmentViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy',
})

urlpatterns = [
    path('', include(router.urls)),
    path('meetings/<int:meeting_pk>/attachments/', meeting_attachment_list, name='meeting-attachment-list'),
    path('meetings/<int:meeting_pk>/attachments/<int:pk>/', meeting_attachment_detail, name='meeting-attachment-detail'),
]