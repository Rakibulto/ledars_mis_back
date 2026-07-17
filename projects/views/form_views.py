from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Form, FormField, FormSubmission, Task
from projects.serializers.form_serializers import (
    FormSerializer,
    FormFieldSerializer,
    FormSubmissionSerializer,
)


class FormViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = FormSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "submissions_count", "created_at"]
    ordering = ["-created_at"]
    filterset_fields = ["space", "is_active"]

    def get_queryset(self):
        return (
            Form.objects.select_related("space", "target_list")
            .prefetch_related("fields")
            .all()
        )


class FormFieldViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = FormFieldSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["form"]

    def get_queryset(self):
        return FormField.objects.select_related("form").all()


class FormSubmissionViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = FormSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["form"]

    def get_queryset(self):
        return FormSubmission.objects.select_related(
            "form", "submitted_by", "task_created"
        ).all()

    @transaction.atomic
    def perform_create(self, serializer):
        submission = serializer.save(submitted_by=self.request.user)
        form = submission.form

        # Auto-create task in target list if configured
        if form.target_list:
            title = (
                submission.data.get("title")
                or submission.data.get("name")
                or f"Form: {form.name}"
            )
            description = submission.data.get("description", "")
            task = Task.objects.create(
                title=title,
                description=description,
                list=form.target_list,
                created_by=self.request.user,
            )
            submission.task_created = task
            submission.save(update_fields=["task_created"])

        # Increment submissions count
        form.submissions_count += 1
        form.save(update_fields=["submissions_count"])
