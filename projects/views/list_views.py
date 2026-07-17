from rest_framework import viewsets, permissions
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import List
from projects.serializers.list_serializers import ListSerializer


class ListViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = ListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "position", "created_at"]
    ordering = ["position", "name"]
    filterset_fields = ["space"]

    def get_queryset(self):
        return List.objects.select_related("space").prefetch_related("tasks").all()
