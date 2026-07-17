from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .atomic import AtomicModelViewSetMixin

from ..models.apply_rfq_models import ApplyRFQ, ApplyRFQAttachment, ApplyRFQStatusLog, PriceProposal
from ..serializers.apply_rfq_serializers import (
    ApplyRFQSerializer,
    ApplyRFQCreateSerializer,
    ApplyRFQAttachmentSerializer,
    ApplyRFQStatusLogSerializer,
    PriceProposalSerializer
)


def _get_user_vendor_profile(user):
    return getattr(user, 'vendor_profile', None) or getattr(user, 'supplier_profile', None)


class ApplyRFQViewSet(AtomicModelViewSetMixin, viewsets.ModelViewSet):
    queryset = ApplyRFQ.objects.all().prefetch_related(
        'invitation_rfq__rfq_number__attachments',
        'invitation_rfq__rfq_number__status_logs',
        'invitation_rfq__rfq_number__items',
        'price_proposals__item',
        'invitation_rfq__rfq_number',
        'profile'
    ).select_related('created_by')
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ApplyRFQCreateSerializer
        return ApplyRFQSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        vendor_profile = _get_user_vendor_profile(user)

        if vendor_profile:
            queryset = queryset.filter(profile=vendor_profile)

        # Filter by invitation_rfq if provided
        invitation_rfq_id = self.request.query_params.get('invitation_rfq')
        if invitation_rfq_id:
            queryset = queryset.filter(invitation_rfq_id=invitation_rfq_id)

        # Filter by RFQ if provided
        rfq_id = self.request.query_params.get('rfq')
        if rfq_id:
            queryset = queryset.filter(invitation_rfq__rfq_number_id=rfq_id)

        return queryset

    @action(detail=True, methods=['post'])
    def add_attachment(self, request, pk=None):
        """Add a new attachment to an ApplyRFQ"""
        apply_rfq = self.get_object()
        serializer = ApplyRFQAttachmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                rfq_number=apply_rfq.invitation_rfq.rfq_number,
                uploaded_by=request.user
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def add_status_log(self, request, pk=None):
        """Add a new status log to an ApplyRFQ"""
        apply_rfq = self.get_object()
        serializer = ApplyRFQStatusLogSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                rfq_number=apply_rfq.invitation_rfq.rfq_number,
                acted_by=request.user
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def attachments(self, request, pk=None):
        """Get all attachments for an ApplyRFQ"""
        apply_rfq = self.get_object()
        attachments = apply_rfq.invitation_rfq.rfq_number.attachments.all()
        serializer = ApplyRFQAttachmentSerializer(attachments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def status_logs(self, request, pk=None):
        """Get all status logs for an ApplyRFQ"""
        apply_rfq = self.get_object()
        status_logs = apply_rfq.invitation_rfq.rfq_number.status_logs.all()
        serializer = ApplyRFQStatusLogSerializer(status_logs, many=True)
        return Response(serializer.data)


class ApplyRFQAttachmentViewSet(AtomicModelViewSetMixin, viewsets.ModelViewSet):
    queryset = ApplyRFQAttachment.objects.all().select_related(
        'rfq_number', 'uploaded_by'
    )
    serializer_class = ApplyRFQAttachmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        vendor_profile = _get_user_vendor_profile(user)

        if vendor_profile:
            supplier_rfqs = ApplyRFQ.objects.filter(profile=vendor_profile).values_list(
                'invitation_rfq__rfq_number', flat=True
            )
            queryset = queryset.filter(rfq_number__in=supplier_rfqs)

        # Filter by RFQ if provided
        rfq_id = self.request.query_params.get('rfq')
        if rfq_id:
            queryset = queryset.filter(rfq_number_id=rfq_id)

        return queryset

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class ApplyRFQStatusLogViewSet(AtomicModelViewSetMixin, viewsets.ModelViewSet):
    queryset = ApplyRFQStatusLog.objects.all().select_related(
        'rfq_number', 'acted_by'
    )
    serializer_class = ApplyRFQStatusLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        vendor_profile = _get_user_vendor_profile(user)

        if vendor_profile:
            supplier_rfqs = ApplyRFQ.objects.filter(profile=vendor_profile).values_list(
                'invitation_rfq__rfq_number', flat=True
            )
            queryset = queryset.filter(rfq_number__in=supplier_rfqs)

        # Filter by RFQ if provided
        rfq_id = self.request.query_params.get('rfq')
        if rfq_id:
            queryset = queryset.filter(rfq_number_id=rfq_id)

        return queryset

    def perform_create(self, serializer):
        serializer.save(acted_by=self.request.user)


class PriceProposalViewSet(AtomicModelViewSetMixin, viewsets.ModelViewSet):
    queryset = PriceProposal.objects.all().select_related(
        'apply_rfq__profile', 'apply_rfq__invitation_rfq__rfq_number',
        'item', 'created_by'
    )
    serializer_class = PriceProposalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        vendor_profile = _get_user_vendor_profile(user)

        if vendor_profile:
            supplier_apply_rfqs = ApplyRFQ.objects.filter(profile=vendor_profile).values_list('id', flat=True)
            queryset = queryset.filter(apply_rfq__in=supplier_apply_rfqs)

        # Filter by apply_rfq if provided
        apply_rfq_id = self.request.query_params.get('apply_rfq')
        if apply_rfq_id:
            queryset = queryset.filter(apply_rfq_id=apply_rfq_id)

        # Filter by item if provided
        item_id = self.request.query_params.get('item')
        if item_id:
            queryset = queryset.filter(item_id=item_id)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)