from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as dj_filters
from django_filters.rest_framework import DjangoFilterBackend
from .atomic import AtomicModelViewSetMixin

from ..models.apply_rfq_models import VendorRFQSubmission, SubmissionDocument
from ..serializers.vendor_rfq_submission_serializers import (
    VendorRFQSubmissionSerializer,
    VendorRFQSubmissionWriteSerializer,
)


class VendorRFQSubmissionFilter(dj_filters.FilterSet):
    user_id = dj_filters.NumberFilter(field_name="created_by_id")
    vendor_email = dj_filters.CharFilter(method="filter_by_vendor_email")

    def filter_by_vendor_email(self, queryset, name, value):
        from vendorportal.models.models import VendorProfile
        vendor_ids = VendorProfile.objects.filter(email__iexact=value).values_list("id", flat=True)
        return queryset.filter(vendor_id__in=vendor_ids)

    class Meta:
        model = VendorRFQSubmission
        fields = ["status", "vendor_id", "rfq", "user_id", "vendor_email"]


class VendorRFQSubmissionViewSet(AtomicModelViewSetMixin, viewsets.ModelViewSet):
    """
    CRUD for vendor RFQ submissions.

    Endpoints (via DefaultRouter):
        POST   /api/vendor-rfq-submission/               → create
        GET    /api/vendor-rfq-submission/               → list
        GET    /api/vendor-rfq-submission/{id}/          → retrieve
        PUT    /api/vendor-rfq-submission/{id}/          → full update
        PATCH  /api/vendor-rfq-submission/{id}/          → partial update
        DELETE /api/vendor-rfq-submission/{id}/          → delete

    Extra:
        DELETE /api/vendor-rfq-submission/{id}/documents/{doc_id}/  → delete single document
    """

    queryset = (
        VendorRFQSubmission.objects.select_related(
            "rfq",
            "technical_proposal",
            "financial_proposal",
            "created_by",
        )
        .prefetch_related(
            "technical_proposal__compliance_items",
            "financial_proposal__items",
            "documents",
        )
        .all()
    )

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = VendorRFQSubmissionFilter
    search_fields    = ["vendor_name", "rfq__rfq_number"]
    ordering_fields  = ["created_at", "updated_at", "submitted_at"]
    ordering         = ["-created_at"]

    # permission_classes = [IsAuthenticated]   # uncomment when auth is wired

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return VendorRFQSubmissionWriteSerializer
        return VendorRFQSubmissionSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    # ── POST /api/vendor-rfq-submission/ ─────────────────────────────────────
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        response_data = VendorRFQSubmissionSerializer(
            instance, context={"request": request}
        ).data
        return Response(response_data, status=status.HTTP_201_CREATED)

    # ── GET /api/vendor-rfq-submission/ ──────────────────────────────────────
    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            data = VendorRFQSubmissionSerializer(page, many=True, context={"request": request}).data
            return self.get_paginated_response(data)
        data = VendorRFQSubmissionSerializer(qs, many=True, context={"request": request}).data
        return Response(data)

    # ── GET /api/vendor-rfq-submission/{id}/ ─────────────────────────────────
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        data = VendorRFQSubmissionSerializer(instance, context={"request": request}).data
        return Response(data)

    # ── PUT /api/vendor-rfq-submission/{id}/ ─────────────────────────────────
    def update(self, request, *args, **kwargs):
        partial  = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        response_data = VendorRFQSubmissionSerializer(
            instance, context={"request": request}
        ).data
        return Response(response_data)

    # ── PATCH /api/vendor-rfq-submission/{id}/ ───────────────────────────────
    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    # ── DELETE /api/vendor-rfq-submission/{id}/ ──────────────────────────────
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # also wipe uploaded files from storage
        for doc in instance.documents.all():
            doc.file.delete(save=False)
        instance.delete()
        return Response(
            {"detail": "Submission deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )

    # ── DELETE /api/vendor-rfq-submission/{id}/documents/{doc_id}/ ───────────
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"documents/(?P<doc_id>[^/.]+)",
    )
    def delete_document(self, request, pk=None, doc_id=None):
        submission = self.get_object()
        doc = get_object_or_404(SubmissionDocument, id=doc_id, submission=submission)
        doc.file.delete(save=False)
        doc.delete()
        return Response(
            {"detail": "Document deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )