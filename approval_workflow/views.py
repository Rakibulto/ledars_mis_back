from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from .models import ApprovalWorkflow, MODULE_TYPE_CHOICES, MENU_CHOICES_BY_TYPE
from .serializers import (
    ApprovalWorkflowSerializer,
    ApprovalWorkflowListSerializer,
    ApprovalWorkflowWriteSerializer,
    UserMiniSerializer,
)
from .services import create_or_replace_workflow, update_workflow_status

User = get_user_model()


class ApprovalWorkflowViewSet(ModelViewSet):
    """
    List/retrieve/create/destroy approval workflows.
    POST   /api/approval-workflows/          → create workflow
    GET    /api/approval-workflows/           → table list
    GET    /api/approval-workflows/{id}/      → detail with levels
    DELETE /api/approval-workflows/{id}/      → remove workflow
    PATCH  /api/approval-workflows/{id}/toggle-status/ → toggle active
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = (
            ApprovalWorkflow.objects
            .select_related('created_by')
            .prefetch_related('levels__level_users__user')
        )
        module_type = self.request.query_params.get('module_type')
        if module_type:
            qs = qs.filter(module_type_name=module_type)
        menu = self.request.query_params.get('menu')
        if menu:
            qs = qs.filter(menu_name=menu)
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(menu_name__icontains=search) |
                Q(module_type_name__icontains=search)
            )
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return ApprovalWorkflowSerializer
        return ApprovalWorkflowSerializer

    def create(self, request, *args, **kwargs):
        write_serializer = ApprovalWorkflowWriteSerializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        workflow = create_or_replace_workflow(
            write_serializer.validated_data, requesting_user=request.user
        )
        out = ApprovalWorkflowSerializer(workflow)
        return Response(out.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        write_serializer = ApprovalWorkflowWriteSerializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        workflow = create_or_replace_workflow(
            write_serializer.validated_data,
            requesting_user=request.user,
            workflow_instance=instance,
        )
        out = ApprovalWorkflowSerializer(workflow)
        return Response(out.data)

    @action(detail=False, methods=['get'], url_path='form-options')
    def form_options(self, request):
        module_type = request.query_params.get('module_type')

        module_types = [
            {'id': key, 'name': label}
            for key, label in MODULE_TYPE_CHOICES
        ]
        menus_by_type = {
            type_key: [{'id': menu, 'name': menu} for menu in menu_names]
            for type_key, menu_names in MENU_CHOICES_BY_TYPE.items()
        }

        if module_type:
            if module_type not in menus_by_type:
                return Response(
                    {'detail': 'Invalid module_type parameter.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({'module_type': module_type, 'menus': menus_by_type[module_type]})

        return Response({'module_types': module_types, 'menus': menus_by_type})

    @action(detail=True, methods=['patch'], url_path='toggle-status')
    def toggle_status(self, request, pk=None):
        workflow = self.get_object()
        workflow = update_workflow_status(workflow.pk, not workflow.is_active)
        return Response({'id': workflow.pk, 'is_active': workflow.is_active})


class WorkflowUserListView(APIView):
    """Return all active users for assigning to approval levels."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        search = request.query_params.get('search', '').strip()
        qs = User.objects.filter(is_active=True).order_by('username', 'email')
        if search:
            qs = qs.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search)
            )
        serializer = UserMiniSerializer(qs[:100], many=True)
        return Response(serializer.data)
