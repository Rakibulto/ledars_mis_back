from rest_framework import viewsets, permissions
from inventory.views import CreatedByMixin
from .models import Project, ProjectActivity, Notification
from .serializers import (
    ProjectSerializer,
    ProjectActivitySerializer,
    NotificationSerializer
)


# -----------------------------
# Project ViewSet
# -----------------------------
class ProjectViewSet(CreatedByMixin, viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by('-created_at')
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# -----------------------------
# Project Activity ViewSet
# -----------------------------
class ProjectActivityViewSet(CreatedByMixin, viewsets.ModelViewSet):
    queryset = ProjectActivity.objects.all().order_by('-created_at')
    serializer_class = ProjectActivitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# -----------------------------
# Notification ViewSet
# -----------------------------
class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all().order_by('-date')
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]