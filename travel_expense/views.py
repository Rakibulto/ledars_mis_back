from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import TravelExpense, TravelExpenseAttachment
from .serializers import (
    TravelExpenseListSerializer,
    TravelExpenseDetailSerializer,
    TravelExpenseWriteSerializer,
    TravelExpenseAttachmentSerializer,
    SignSerializer,
)


class TravelExpensePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class TravelExpenseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = TravelExpensePagination
    filterset_fields = ['status']
    search_fields = ['name', 'project']

    def get_serializer_class(self):
        if self.action == 'list':
            return TravelExpenseListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return TravelExpenseWriteSerializer
        return TravelExpenseDetailSerializer

    def get_queryset(self):
        queryset = TravelExpense.objects.all()
        status_param = self.request.query_params.get('status', '')
        search = self.request.query_params.get('search', '')

        if status_param:
            queryset = queryset.filter(status=status_param)

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(project__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, status='draft')

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.status not in ('draft',):
            raise PermissionDenied(
                f"This travel expense is in '{instance.status}' status and cannot be edited."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance.created_by != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied('Only the creator or admin can delete this record.')
        instance.delete()

    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        travel_expense = self.get_object()
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
            'prepared_received': 'prepared_received_signature',
            'checked_by': 'checked_by_signature',
            'accountant': 'accountant_signature',
            'approved_by': 'approved_by_signature',
        }

        field_name = field_map[role]

        existing = getattr(travel_expense, field_name, None)
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

        setattr(travel_expense, field_name, signature_data)

        if (
            travel_expense.prepared_received_signature
            and travel_expense.checked_by_signature
            and travel_expense.accountant_signature
            and travel_expense.approved_by_signature
        ):
            travel_expense.status = 'approved'

        travel_expense.save()

        detail_serializer = TravelExpenseDetailSerializer(
            travel_expense, context={'request': request}
        )
        return Response(detail_serializer.data)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_file(self, request, pk=None):
        travel_expense = self.get_object()
        uploaded_file = request.FILES.get('file')
        row_index = request.data.get('row_index', 0)

        if not uploaded_file:
            return Response(
                {'detail': 'No file provided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attachment = TravelExpenseAttachment.objects.create(
            travel_expense=travel_expense,
            row_index=int(row_index),
            file=uploaded_file,
            original_name=uploaded_file.name,
            file_size=uploaded_file.size,
            uploaded_by=request.user,
        )

        serializer = TravelExpenseAttachmentSerializer(attachment, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='delete_file/(?P<file_id>[0-9]+)')
    def delete_file(self, request, pk=None, file_id=None):
        travel_expense = self.get_object()
        try:
            attachment = TravelExpenseAttachment.objects.get(id=file_id, travel_expense=travel_expense)
            attachment.file.delete(save=False)
            attachment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except TravelExpenseAttachment.DoesNotExist:
            return Response(
                {'detail': 'File not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
