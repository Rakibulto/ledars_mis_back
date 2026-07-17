from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Workspace, WorkspaceMember
from projects.serializers.workspace_serializers import (
    WorkspaceSerializer,
    WorkspaceListSerializer,
    WorkspaceMemberSerializer,
)


class WorkspaceViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return Workspace.objects.prefetch_related("workspace_members", "spaces").all()

    def get_serializer_class(self):
        if self.action == "list":
            return WorkspaceListSerializer
        return WorkspaceSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        workspace = serializer.save(created_by=self.request.user)
        WorkspaceMember.objects.create(
            workspace=workspace, user=self.request.user, role="owner"
        )

    @action(detail=True, methods=["post"], url_path="add-member")
    @transaction.atomic
    def add_member(self, request, pk=None):
        workspace = self.get_object()
        user_id = request.data.get("user_id")
        role = request.data.get("role", "member")
        if not user_id:
            return Response(
                {"detail": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        member, created = WorkspaceMember.objects.get_or_create(
            workspace=workspace, user_id=user_id, defaults={"role": role}
        )
        if not created:
            return Response(
                {"detail": "User is already a member"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            WorkspaceMemberSerializer(member).data, status=status.HTTP_201_CREATED
        )

    @action(
        detail=True, methods=["delete"], url_path="remove-member/(?P<user_id>[^/.]+)"
    )
    @transaction.atomic
    def remove_member(self, request, pk=None, user_id=None):
        workspace = self.get_object()
        deleted, _ = WorkspaceMember.objects.filter(
            workspace=workspace, user_id=user_id
        ).delete()
        if not deleted:
            return Response(
                {"detail": "Member not found"}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceMemberViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = WorkspaceMemberSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["workspace", "role"]

    def get_queryset(self):
        return WorkspaceMember.objects.select_related("user", "workspace").all()
