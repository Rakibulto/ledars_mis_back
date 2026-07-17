from django.shortcuts import render

from rest_framework import viewsets, permissions
from .atomic import AtomicModelViewSetMixin
from ..models.invitation_rfq_models import Invitation_rfq
from ..serializers.invitation_rfq_serializers import Invitation_rfqSerializer, Invitation_rfqCreateSerializer



class Invitation_rfqViewSet(AtomicModelViewSetMixin, viewsets.ModelViewSet):
    """
    A viewset for listing, retrieving, and creating submitted RFQs.
    """
    queryset = Invitation_rfq.objects.all().order_by('-submitted_at')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return Invitation_rfqCreateSerializer
        return Invitation_rfqSerializer

    def perform_create(self, serializer):
        # Automatically assign the current user as the submitter
        serializer.save(created_by=self.request.user)

        