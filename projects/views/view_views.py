from django.db.models import Q
from rest_framework import viewsets, permissions
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import SavedView
from projects.serializers.view_serializers import SavedViewSerializer


class SavedViewViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = SavedViewSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering = ["name"]
    filterset_fields = ["view_type", "is_shared"]

    def get_queryset(self):
        return SavedView.objects.filter(
            Q(created_by=self.request.user) | Q(is_shared=True)
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
