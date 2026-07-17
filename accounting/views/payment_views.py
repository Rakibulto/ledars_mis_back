from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from accounting.models import PaymentMethod, Payment, PaymentAllocation
from accounting.serializers.payment_serializers import (
    PaymentMethodSerializer,
    PaymentListSerializer,
    PaymentDetailSerializer,
    PaymentWriteSerializer,
    PaymentAllocationSerializer,
)


class PaymentMethodViewSet(viewsets.ModelViewSet):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["payment_type", "is_active"]


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related(
        "payment_method", "journal", "bank_account"
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["direction", "status", "payment_method", "partner_type", "date"]
    search_fields = ["reference", "partner_name", "memo"]
    ordering_fields = ["date", "amount", "created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return PaymentListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return PaymentWriteSerializer
        return PaymentDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PaymentAllocationViewSet(viewsets.ModelViewSet):
    queryset = PaymentAllocation.objects.select_related("payment").all()
    serializer_class = PaymentAllocationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["payment", "document_type"]
