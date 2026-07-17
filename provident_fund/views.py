from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ProvidentFundLoan
from .serializers import (
    ProvidentFundLoanListSerializer,
    ProvidentFundLoanDetailSerializer,
    ProvidentFundLoanWriteSerializer,
    SignSerializer,
)


class ProvidentFundLoanPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProvidentFundLoanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = ProvidentFundLoanPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return ProvidentFundLoanListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return ProvidentFundLoanWriteSerializer
        return ProvidentFundLoanDetailSerializer

    def get_queryset(self):
        queryset = ProvidentFundLoan.objects.all()
        status_param = self.request.query_params.get('status', '')
        search = self.request.query_params.get('search', '')

        if status_param:
            queryset = queryset.filter(status=status_param)

        if search:
            queryset = queryset.filter(
                Q(applicant_name__icontains=search)
                | Q(program_name__icontains=search)
                | Q(designation__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, status='draft')

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.status not in ('draft',):
            raise PermissionDenied(
                f"This record is in '{instance.status}' status and cannot be edited."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance.created_by != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied('Only the creator or admin can delete this record.')
        instance.delete()

    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        pf_loan = self.get_object()
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
            'supervisor': 'supervisor_signature',
            'upper_authority': 'upper_authority_signature',
            'accounts_officer': 'accounts_officer_signature',
            'trust_member_1': 'trust_member_1_signature',
            'trust_member_2': 'trust_member_2_signature',
            'recommender': 'recommender_signature',
            'recorder': 'recorder_signature',
            'approver': 'approver_signature',
        }

        field_name = field_map[role]

        existing = getattr(pf_loan, field_name, None)
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

        setattr(pf_loan, field_name, signature_data)

        # Auto-approve when recommender + recorder + approver all signed
        if (pf_loan.recommender_signature
                and pf_loan.recorder_signature
                and pf_loan.approver_signature):
            pf_loan.status = 'approved'

        pf_loan.save()

        detail_serializer = ProvidentFundLoanDetailSerializer(
            pf_loan, context={'request': request}
        )
        return Response(detail_serializer.data)
