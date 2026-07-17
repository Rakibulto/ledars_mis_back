from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Template
from projects.serializers.template_serializers import TemplateSerializer


class TemplateViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = TemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "usage_count", "created_at"]
    ordering = ["-usage_count"]
    filterset_fields = ["category", "is_public"]

    def get_queryset(self):
        return Template.objects.select_related("space").all()

    @action(detail=True, methods=["post"], url_path="apply")
    @transaction.atomic
    def apply_template(self, request, pk=None):
        """Apply a template to create tasks/lists in a target space."""
        template = self.get_object()
        space_id = request.data.get("space_id")
        if not space_id:
            return Response(
                {"detail": "space_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        from projects.models import List, Task, StatusGroup, Status

        # Create statuses from template
        for s_data in template.statuses:
            group, _ = StatusGroup.objects.get_or_create(
                name=s_data.get("group", "active"),
                space_id=space_id,
                defaults={
                    "label": s_data.get("group", "Active").title(),
                    "created_by": request.user,
                },
            )
            Status.objects.get_or_create(
                name=s_data.get("name"),
                space_id=space_id,
                defaults={
                    "color": s_data.get("color", "#94a3b8"),
                    "group": group,
                    "created_by": request.user,
                },
            )

        # Create lists from template
        for l_data in template.lists:
            List.objects.create(
                space_id=space_id,
                name=l_data.get("name", "List"),
                created_by=request.user,
            )

        template.usage_count += 1
        template.save(update_fields=["usage_count"])

        return Response({"detail": "Template applied successfully"})
