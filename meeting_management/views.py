from rest_framework import permissions, viewsets
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from paginations import Pagination
from .models import Meeting, MeetingAttachment
from .serializers import (
    MeetingListSerializer, MeetingDetailSerializer, MeetingWriteSerializer,
    MeetingAttachmentSerializer,
)

from django.db.models import Q


class MeetingViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['date']
    search_fields = ['title', 'description', 'meeting_id']
    ordering_fields = ['date', 'start_time', 'created_at']
    ordering = ['-date', '-start_time']

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser:
            return Meeting.objects.all()

        return Meeting.objects.filter(
            Q(created_by=user) | Q(assigned_to=user)
        ).distinct()

    def get_serializer_class(self):
        if self.action == 'list':
            return MeetingListSerializer
        elif self.action in ('create', 'update', 'partial_update'):
            return MeetingWriteSerializer
        return MeetingDetailSerializer

    def perform_create(self, serializer):
        assigned_to = self.request.data.get('assigned_to')
        if not assigned_to:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save()
        
        
class MeetingAttachmentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MeetingAttachmentSerializer

    def get_queryset(self):
        return MeetingAttachment.objects.filter(
            meeting_id=self.kwargs['meeting_pk']
        )

    def perform_create(self, serializer):
        meeting = Meeting.objects.get(pk=self.kwargs['meeting_pk'])
        file = self.request.FILES.get('file')
        serializer.save(
            meeting=meeting,
            file_name=file.name if file else '',
            file_size=file.size if file else None,
        )
