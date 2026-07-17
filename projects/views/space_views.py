from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Space, SpaceMember
from projects.serializers.space_serializers import (
    SpaceSerializer,
    SpaceListSerializer,
    SpaceMemberSerializer,
)


class SpaceViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = SpaceSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    filterset_fields = ["workspace", "is_private"]

    def get_queryset(self):
        return (
            Space.objects.select_related("workspace")
            .prefetch_related("space_members", "lists")
            .all()
        )

    def get_serializer_class(self):
        if self.action == "list":
            return SpaceListSerializer
        return SpaceSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        space = serializer.save(created_by=self.request.user)
        SpaceMember.objects.create(space=space, user=self.request.user, role="admin")

    @action(detail=True, methods=["post"], url_path="add-member")
    @transaction.atomic
    def add_member(self, request, pk=None):
        space = self.get_object()
        user_id = request.data.get("user_id")
        role = request.data.get("role", "member")
        if not user_id:
            return Response(
                {"detail": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        member, created = SpaceMember.objects.get_or_create(
            space=space, user_id=user_id, defaults={"role": role}
        )
        if not created:
            return Response(
                {"detail": "User is already a member"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            SpaceMemberSerializer(member).data, status=status.HTTP_201_CREATED
        )

    @action(
        detail=True, methods=["delete"], url_path="remove-member/(?P<user_id>[^/.]+)"
    )
    @transaction.atomic
    def remove_member(self, request, pk=None, user_id=None):
        space = self.get_object()
        deleted, _ = SpaceMember.objects.filter(space=space, user_id=user_id).delete()
        if not deleted:
            return Response(
                {"detail": "Member not found"}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class SpaceMemberViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = SpaceMemberSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["space", "role"]

    def get_queryset(self):
        return SpaceMember.objects.select_related("user", "space").all()
