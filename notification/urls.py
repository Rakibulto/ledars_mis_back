from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import MarkAllNotificationsReadView, NotificationList, NotificationDetails




urlpatterns = [
    # All Notifications for Admin only
    path('notifications/', NotificationList.as_view(), name='notification-list'),
    
    # Single Notification
    path('notifications/<int:pk>/', NotificationDetails.as_view(), name='notification-detail'),
    
    # Mark all notifications as read
    path('notifications/mark-all-read/', MarkAllNotificationsReadView.as_view(), name='mark-all-notifications-read'),
]
