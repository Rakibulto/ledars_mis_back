from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from paginations import Pagination
from inventory.views import CreatedByMixin
from ..models.award_models import Award, AwardNotification
from ..serializers.award_serializers import (
    AwardSerializer,
    AwardWriteSerializer,
    AwardNotificationSerializer,
    SimpleAwardSerializer,
)
from ..filters.procurement_filters import AwardFilter


class AwardViewSet(CreatedByMixin, viewsets.ModelViewSet):
    queryset = (
        Award.objects.select_related(
            "comparative_statement", "rfq", "vendor_profile", "awarded_by"
        )
        .prefetch_related(
            "comparative_statement__approval_workflow",
            "comparative_statement__quotations",
            "comparative_statement__quotations__quotation_items__item",
        )
        .all()
    )
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["award_number", "title", "rfq__rfq_number", "status"]
    ordering_fields = ["created_at", "total_amount", "award_date"]
    ordering = ["-created_at"]
    filterset_class = AwardFilter

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return AwardWriteSerializer
        return AwardSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(awarded_by=self.request.user)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = Award.objects.all()
        from django.db.models import Sum

        data = {
            "total": qs.count(),
            "pending": qs.filter(
                status__in=["pending_notification", "Pending Notification"]
            ).count(),
            "notified": qs.filter(status__in=["notified", "Notified"]).count(),
            "accepted": qs.filter(status__in=["accepted", "Accepted"]).count(),
            "active": qs.filter(status="active").count(),
            "total_amount": qs.aggregate(total=Sum("total_amount"))["total"] or 0,
        }
        return Response(data)

    @action(detail=False, methods=["get"], url_path="simple_award")
    def simple_award(self, request):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = SimpleAwardSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = SimpleAwardSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="history")
    def history(self, request):
        qs = self.filter_queryset(self.get_queryset()).exclude(
            status__in=["draft", "Draft"]
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class AwardNotificationViewSet(viewsets.ModelViewSet):
    queryset = AwardNotification.objects.select_related("award", "vendor_profile").all()
    serializer_class = AwardNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["award", "vendor_profile", "notification_type", "is_sent"]
    ordering = ["-created_at"]
