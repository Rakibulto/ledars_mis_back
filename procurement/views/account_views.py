# procurement_dashboard/views/account_view.py
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from ..models.account_models import Account, AccountCategory
from ..serializers.account_serializers import AccountSerializer, AccountCategorySerializer, SimpleAccountCategorySerializer



class AccountCategoryViewSet(viewsets.ModelViewSet):
    queryset = AccountCategory.objects.filter(is_active=True)
    serializer_class = AccountCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['parent']


class AccountViewSet(viewsets.ModelViewSet):

    queryset = Account.objects.select_related('category', 'sub_category', 'created_by').all().order_by("-created_at")
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]  # optional, require login

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'sub_category']
    search_fields = ['code', 'name']
    ordering_fields = ['created_at', 'name', 'balance']
    ordering = ['-created_at']


    @transaction.atomic
    def perform_create(self, serializer):
        # automatically set created_by to current user
        serializer.save(created_by=self.request.user)
