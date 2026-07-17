from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone

from accounting.models.perdium_claim_models import PerdiumClaim
from accounting.serializers.perdium_claim_serializers import PerdiumClaimSerializer


class PerdiumSignSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['prepared_by', 'reviewed_by', 'finance_by', 'approved_by'])
    confirmed = serializers.BooleanField()


class PerdiumClaimViewSet(viewsets.ModelViewSet):
    queryset = PerdiumClaim.objects.all()
    serializer_class = PerdiumClaimSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "grade"]
    search_fields = ["employee_name", "designation", "purpose_of_travel", "name_of_project"]
    ordering_fields = ["created_at", "date", "employee_name"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        user = self.request.user
        full_name = user.get_full_name() or user.email or ''
        serializer.save(created_by=user, prepared_by=full_name)

    @action(detail=False, methods=["post"])
    def submit(self, request):
        """Submit a perdium claim for approval."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user, status="submitted")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def change_status(self, request, pk=None):
        """Change the status of a perdium claim."""
        claim = self.get_object()
        new_status = request.data.get("status")
        valid_statuses = dict(PerdiumClaim.STATUS_CHOICES).keys()
        if new_status not in valid_statuses:
            return Response(
                {"detail": f"Invalid status. Choose from: {', '.join(valid_statuses)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        claim.status = new_status
        claim.save(update_fields=["status", "updated_at"])
        serializer = self.get_serializer(claim)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def sign(self, request, pk=None):
        """Sign a perdium claim with the current user's signature."""
        claim = self.get_object()
        sign_serializer = PerdiumSignSerializer(data=request.data)
        sign_serializer.is_valid(raise_exception=True)

        role = sign_serializer.validated_data['role']
        confirmed = sign_serializer.validated_data['confirmed']

        if not confirmed:
            return Response(
                {'detail': 'Confirmation is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        field_map = {
            'prepared_by': 'prepared_by_signature',
            'reviewed_by': 'reviewed_by_signature',
            'finance_by': 'finance_by_signature',
            'approved_by': 'approved_by_signature',
        }

        field_name = field_map[role]

        existing = getattr(claim, field_name, None)
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

        now = timezone.now()

        signature_data = {
            'user_id': request.user.id,
            'name': request.user.get_full_name() or request.user.email,
            'email': request.user.email,
            'signature_image': employee.signature.url if employee and employee.signature else None,
            'signed_at': now.isoformat(),
        }

        setattr(claim, field_name, signature_data)

        # Update the text field as well
        text_field_map = {
            'prepared_by': 'prepared_by',
            'reviewed_by': 'reviewed_by',
            'finance_by': 'finance_by',
            'approved_by': 'approved_by',
        }
        text_field = text_field_map[role]
        if not getattr(claim, text_field):
            setattr(claim, text_field, signature_data['name'])

        # Auto-update status based on role
        if role == 'reviewed_by' and claim.status == 'draft':
            claim.status = 'submitted'
        if role == 'approved_by' and claim.status in ('draft', 'submitted'):
            claim.status = 'approved'

        claim.save()
        serializer = self.get_serializer(claim)
        return Response(serializer.data)
