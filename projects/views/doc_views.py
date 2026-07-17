from rest_framework import viewsets, permissions
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Doc
from projects.serializers.doc_serializers import DocSerializer


class DocViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = DocSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "content"]
    ordering_fields = ["title", "created_at", "updated_at"]
    ordering = ["-updated_at"]
    filterset_fields = ["space", "is_favorite", "is_archived"]

    def get_queryset(self):
        return (
            Doc.objects.select_related("space", "created_by", "parent")
            .prefetch_related("shared_with", "sub_pages")
            .all()
        )
