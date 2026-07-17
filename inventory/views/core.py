from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from paginations import Pagination
from inventory.models import Category, UnitOfMeasure
from inventory.serializers import CategorySerializer, UnitOfMeasureSerializer
from inventory.filters import CategoryFilter


class CreatedByMixin:
    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(created_by=user if user.is_authenticated else None)

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()


class CategoryViewSet(CreatedByMixin, ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CategoryFilter
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "created_at", "item_count"]
    ordering = ["-created_at"]


class UnitOfMeasureViewSet(ModelViewSet):
    queryset = UnitOfMeasure.objects.order_by("name")
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ["name"]
    filterset_fields = ["is_active"]
    ordering_fields = ["id", "name"]
    ordering = ["name"]
