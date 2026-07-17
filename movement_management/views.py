from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import MovementManagement
from .serializers import (
    MovementManagementListSerializer,
    MovementManagementDetailSerializer,
    SignSerializer,
)


class MovementManagementPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class MovementManagementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = MovementManagementPagination
    filterset_fields = ['status']
    search_fields = ['name', 'project_name']

    def get_serializer_class(self):
        if self.action == 'list':
            return MovementManagementListSerializer
        return MovementManagementDetailSerializer

    def get_queryset(self):
        queryset = MovementManagement.objects.all()
        status_param = self.request.query_params.get('status', '')
        search = self.request.query_params.get('search', '')

        if status_param:
            queryset = queryset.filter(status=status_param)

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(project_name__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.status not in ('draft', 'submitted'):
            raise PermissionDenied(
                f"This movement is in '{instance.status}' status and cannot be edited."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance.created_by != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied('Only the creator or admin can delete this record.')
        instance.delete()

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """Return status counts for the movement management dashboard."""
        qs = MovementManagement.objects.all()
        return Response({
            'total': qs.count(),
            'draft': qs.filter(status='draft').count(),
            'submitted': qs.filter(status='submitted').count(),
            'approved': qs.filter(status='approved').count(),
        })

    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        movement = self.get_object()
        serializer = SignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = serializer.validated_data['role']
        confirmed = serializer.validated_data['confirmed']

        if not confirmed:
            return Response(
                {'detail': 'Confirmation is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        field_map = {
            'submitted_by': 'submitted_by_signature',
            'checked_supervised': 'checked_supervised_signature',
            'approved_by': 'approved_by_signature',
        }

        field_name = field_map[role]

        existing = getattr(movement, field_name, None)
        if existing:
            return Response(
                {'detail': f'{role} has already signed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        employee = None
        try:
            from employee.models import Employee
            employee = Employee.objects.filter(user=request.user).first()
        except Exception:
            pass

        from django.utils import timezone
        now = timezone.now()

        signature_data = {
            'user_id': request.user.id,
            'name': request.user.get_full_name() or request.user.email,
            'email': request.user.email,
            'signature_image': employee.signature.url if employee and employee.signature else None,
            'signed_at': now.isoformat(),
        }

        setattr(movement, field_name, signature_data)

        if role == 'submitted_by' and movement.status == 'draft':
            movement.status = 'submitted'

        if movement.submitted_by_signature and movement.checked_supervised_signature and movement.approved_by_signature:
            movement.status = 'approved'

        movement.save()

        detail_serializer = MovementManagementDetailSerializer(movement)
        return Response(detail_serializer.data)
