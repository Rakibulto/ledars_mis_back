from rest_framework import permissions, viewsets
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from vendorportal.views.atomic import AtomicModelViewSetMixin

from .models import Donor, DonorLedger
from .serializers import DonorSerializer, DonorLedgerSerializer


class DonorViewSet(AtomicModelViewSetMixin, CreatedByMixin, viewsets.ModelViewSet):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = Donor.objects.all().order_by("-created_at")
    serializer_class = DonorSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "donor_code",
        "type",
        "status",
        "currency__code",
        "organization_name",
        "last_donation_date",
    ]
    search_fields = [
        "donor_code",
        "name",
        "email",
        "phone",
        "organization_name",
        "address",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "donor_code",
        "name",
        "total_donated_amount",
        "last_donation_date",
    ]
    ordering = ["-created_at"]


class DonorLedgerViewSet(AtomicModelViewSetMixin, CreatedByMixin, viewsets.ModelViewSet):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = DonorLedger.objects.all().order_by("-transaction_date", "-created_at")
    serializer_class = DonorLedgerSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "donor",
        "transaction_type",
        "currency",
        "related_project",
        "is_reconciled",
    ]
    search_fields = [
        "ledger_code",
        "reference",
        "description",
        "related_project",
    ]
    ordering_fields = [
        "transaction_date",
        "amount",
        "balance",
        "created_at",
    ]
    ordering = ["-transaction_date", "-created_at"]
