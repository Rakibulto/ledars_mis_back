from rest_framework import permissions, viewsets
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from paginations import Pagination
from .models import Lead, LeadFollowUp, LeadFollowUpAttachment
from .serializers import (
    LeadListSerializer, LeadDetailSerializer, LeadWriteSerializer,
    LeadFollowUpReadSerializer, LeadFollowUpWriteSerializer,
)

from django.db.models import Q

class LeadViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'project_type', 'assigned_to', 'country', 'city']
    search_fields = ['name', 'phone', 'email', 'project_name', 'lead_id']
    ordering_fields = ['created_at', 'name', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.is_superuser:
            return Lead.objects.all()
        
        return Lead.objects.filter(
            Q(created_by=user) | Q(assigned_to=user)
        ).distinct()

    def get_serializer_class(self):
        if self.action == 'list':
            return LeadListSerializer
        elif self.action in ('create', 'update', 'partial_update'):
            return LeadWriteSerializer
        return LeadDetailSerializer

    def perform_create(self, serializer):
        assigned_to = self.request.data.get('assigned_to')
        if not assigned_to:
            serializer.save(created_by=self.request.user, assigned_to=self.request.user)
        else:
            serializer.save(created_by=self.request.user)


class LeadFollowUpViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LeadFollowUpReadSerializer

    def get_queryset(self):
        return LeadFollowUp.objects.filter(lead_id=self.kwargs.get('lead_pk')).prefetch_related(
            'assigned_to', 'attachments'
        )

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return LeadFollowUpWriteSerializer
        return LeadFollowUpReadSerializer

    def perform_create(self, serializer):
        follow_up = serializer.save(
            lead_id=self.kwargs.get('lead_pk'),
            created_by=self.request.user,
        )
        for f in self.request.FILES.getlist('attachments'):
            LeadFollowUpAttachment.objects.create(
                follow_up=follow_up,
                file=f,
                file_name=str(f.name)[:255] if f.name else '',
                file_size=f.size or 0,
            )
