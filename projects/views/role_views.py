from rest_framework import viewsets, permissions
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from projects.models import PMRole, PMUserRole
from projects.serializers.role_serializers import PMRoleSerializer, PMUserRoleSerializer


class PMRoleViewSet(viewsets.ModelViewSet):
    serializer_class = PMRoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        return PMRole.objects.filter(is_active=True)


class PMUserRoleViewSet(viewsets.ModelViewSet):
    serializer_class = PMUserRoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["user", "role"]

    def get_queryset(self):
        return PMUserRole.objects.select_related("user", "role").all()
