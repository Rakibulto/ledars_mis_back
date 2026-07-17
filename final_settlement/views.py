from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q

from .models import FinalSettlement
from .serializers import (
    FinalSettlementListSerializer,
    FinalSettlementDetailSerializer,
    SignatureSerializer,
)


class FinalSettlementViewSet(viewsets.ModelViewSet):
    queryset = FinalSettlement.objects.all()
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status']
    search_fields = ['name_of_staff', 'project_name']

    def get_serializer_class(self):
        if self.action == 'list':
            return FinalSettlementListSerializer
        return FinalSettlementDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Filter by status if provided
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        # Search by name or project
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(name_of_staff__icontains=search) |
                Q(project_name__icontains=search)
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, status='Draft')

    def perform_update(self, serializer):
        instance = self.get_object()
        # Only allow update if Draft or Rejected
        if instance.status not in ['Draft', 'Rejected']:
            raise PermissionDenied(
                f"This settlement is in '{instance.status}' status and cannot be edited."
            )
        serializer.save()

    def perform_destroy(self, instance):
        # Hard delete for now
        instance.delete()

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        settlement = self.get_object()
        if settlement.status != 'Draft':
            return Response(
                {'detail': f'Cannot submit. Current status: {settlement.status}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        settlement.status = 'Submitted'
        settlement.save(update_fields=['status', 'updated_at'])
        serializer = self.get_serializer(settlement)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        settlement = self.get_object()
        serializer = SignatureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = serializer.validated_data['role']
        user = request.user
        now = timezone.now()

        signature_data = {
            'user_id': user.id,
            'name': user.get_full_name() or user.email,
            'email': user.email,
            'signed_at': now.isoformat(),
        }

        if role == 'supervisor':
            if settlement.supervisor_signature:
                return Response(
                    {'detail': 'Supervisor has already signed.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            settlement.supervisor_signature = signature_data
        elif role == 'finance':
            if settlement.finance_signature:
                return Response(
                    {'detail': 'Finance person has already signed.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            settlement.finance_signature = signature_data
        elif role == 'management':
            if settlement.management_signature:
                return Response(
                    {'detail': 'Management person has already signed.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            settlement.management_signature = signature_data

        # Check if all 3 signatures are present -> Payment_Pending
        if (
            settlement.supervisor_signature
            and settlement.finance_signature
            and settlement.management_signature
        ):
            settlement.status = 'Payment_Pending'

        settlement.save()
        resp_serializer = self.get_serializer(settlement)
        return Response(resp_serializer.data)

    @action(detail=True, methods=['post'])
    def payment_complete(self, request, pk=None):
        settlement = self.get_object()
        if settlement.status != 'Payment_Pending':
            return Response(
                {'detail': f'Cannot complete payment. Current status: {settlement.status}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        settlement.status = 'Completed'
        settlement.payment_completed_at = timezone.now()
        settlement.payment_completed_by = {
            'user_id': user.id,
            'name': user.get_full_name() or user.email,
            'email': user.email,
        }
        settlement.save()
        resp_serializer = self.get_serializer(settlement)
        return Response(resp_serializer.data)