from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.utils import timezone
from paginations import Pagination
from ..models.notification_models import ProcurementNotification
from ..serializers.notification_serializers import ProcurementNotificationSerializer


class ProcurementNotificationViewSet(viewsets.ModelViewSet):
    serializer_class = ProcurementNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "message"]
    ordering = ["-created_at"]
    filterset_fields = ["notification_type", "is_read", "priority"]

    def get_queryset(self):
        return ProcurementNotification.objects.filter(recipient=self.request.user)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=True, methods=["post", "patch"], url_path="mark-read")
    @transaction.atomic
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
        return Response({"status": "marked as read"})

    @action(detail=False, methods=["post", "patch"], url_path="mark-all-read")
    @transaction.atomic
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return Response({"status": "all marked as read"})
