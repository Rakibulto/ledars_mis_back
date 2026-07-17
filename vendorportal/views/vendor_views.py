from django.db.models import Count
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from inventory.views import CreatedByMixin
from paginations import Pagination
from .atomic import AtomicModelViewSetMixin
from ..models.models import VendorProfile, VendorDocument
from ..serializers.vendor_serializers import (
    VendorProfileSerializer,
    VendorDocumentSerializer,
    SimpleVendorProfileSerializer,
    SimpleVendorDocumentSerializer,
)


class VendorProfileViewSet(AtomicModelViewSetMixin, CreatedByMixin, viewsets.ModelViewSet):
    queryset = VendorProfile.objects.all().prefetch_related('documents', 'categories').order_by('-created_at')
    serializer_class = VendorProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'code', 'verification_state', 'organization_type', 'created_by']
    search_fields = ['code', 'name', 'company_name_bn', 'email', 'contact_person']
    ordering_fields = ['created_at', 'updated_at', 'code', 'name']

    def get_permissions(self):
        # Allow public self-registration without authentication
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['get'], url_path='status-summary')
    def status_summary(self, request):
        status_values = ['Pending', 'Approved', 'Rejected', 'Active']
        counts = {
            item['status']: item['count']
            for item in VendorProfile.objects.filter(status__in=status_values)
            .values('status')
            .annotate(count=Count('id'))
        }

        summary = {status: counts.get(status, 0) for status in status_values}
        return Response(summary)

    @action(detail=False, methods=['get'], url_path='simple_VendorProfile')
    def simple_vendor_profile(self, request):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = SimpleVendorProfileSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = SimpleVendorProfileSerializer(qs, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user)


class VendorDocumentViewSet(AtomicModelViewSetMixin, CreatedByMixin, viewsets.ModelViewSet):
    queryset = VendorDocument.objects.all().order_by('-uploaded_at')
    serializer_class = VendorDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['review_status', 'vendor', 'reviewer']
    search_fields = ['doc_type', 'vendor__name', 'vendor__company_name_bn']

    parser_classes = [JSONParser, MultiPartParser, FormParser]  # support JSON and file upload

    def get_permissions(self):
        # Allow public document upload during vendor self-registration
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['get'], url_path='simple_vendor_document')
    def simple_vendor_document(self, request):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = SimpleVendorDocumentSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = SimpleVendorDocumentSerializer(qs, many=True)
        return Response(serializer.data)


