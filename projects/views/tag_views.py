from rest_framework import viewsets, permissions
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Tag, TaskTag
from projects.serializers.tag_serializers import TagSerializer, TaskTagSerializer


class TagViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering = ["name"]
    filterset_fields = ["space"]

    def get_queryset(self):
        return Tag.objects.all()


class TaskTagViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = TaskTagSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["task", "tag"]

    def get_queryset(self):
        return TaskTag.objects.select_related("task", "tag").all()
