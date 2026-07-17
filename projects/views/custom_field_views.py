from django.db import transaction
from rest_framework import viewsets, permissions
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import CustomField, CustomFieldOption, TaskCustomFieldValue
from projects.serializers.custom_field_serializers import (
    CustomFieldSerializer,
    CustomFieldOptionSerializer,
    TaskCustomFieldValueSerializer,
)


class CustomFieldViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = CustomFieldSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering = ["name"]
    filterset_fields = ["space", "field_type", "is_active"]

    def get_queryset(self):
        return (
            CustomField.objects.select_related("space")
            .prefetch_related("options")
            .all()
        )

    @transaction.atomic
    def perform_create(self, serializer):
        field = serializer.save(created_by=self.request.user)
        # Create options if provided
        options = self.request.data.get("options_data", [])
        for idx, opt in enumerate(options):
            CustomFieldOption.objects.create(
                field=field,
                label=opt.get("label", ""),
                color=opt.get("color"),
                position=idx,
            )


class CustomFieldOptionViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = CustomFieldOptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["field"]

    def get_queryset(self):
        return CustomFieldOption.objects.select_related("field").all()


class TaskCustomFieldValueViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = TaskCustomFieldValueSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["task", "field"]

    def get_queryset(self):
        return TaskCustomFieldValue.objects.select_related("task", "field").all()
