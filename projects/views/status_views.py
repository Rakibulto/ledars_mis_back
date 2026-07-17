from rest_framework import viewsets, permissions
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import StatusGroup, Status
from projects.serializers.status_serializers import (
    StatusGroupSerializer,
    StatusSerializer,
)


class StatusGroupViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = StatusGroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["space"]

    def get_queryset(self):
        return StatusGroup.objects.prefetch_related("statuses").all()


class StatusViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = StatusSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["group", "space"]

    def get_queryset(self):
        return Status.objects.select_related("group").all()
