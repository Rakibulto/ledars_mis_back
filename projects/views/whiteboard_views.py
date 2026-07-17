from rest_framework import viewsets, permissions
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Whiteboard
from projects.serializers.whiteboard_serializers import WhiteboardSerializer


class WhiteboardViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = WhiteboardSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["-created_at"]
    filterset_fields = ["space"]

    def get_queryset(self):
        return (
            Whiteboard.objects.select_related("space", "created_by")
            .prefetch_related("collaborators")
            .all()
        )
