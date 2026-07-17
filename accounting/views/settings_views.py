from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from accounting.models import (
    AccountingSettings,
    NumberSequence,
    ApprovalRule,
    ApprovalWorkflow,
    AuditLog,
    PostingRule,
    IntegrationRule,
    LockDate,
)
from accounting.serializers.settings_serializers import (
    AccountingSettingsSerializer,
    NumberSequenceSerializer,
    ApprovalRuleSerializer,
    ApprovalWorkflowSerializer,
    AuditLogSerializer,
    PostingRuleSerializer,
    IntegrationRuleSerializer,
    LockDateSerializer,
)


class AccountingSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        instance, _ = AccountingSettings.objects.get_or_create(pk=1)
        return Response(AccountingSettingsSerializer(instance, context={'request': request}).data)

    def patch(self, request):
        instance, _ = AccountingSettings.objects.get_or_create(pk=1)
        serializer = AccountingSettingsSerializer(
            instance,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class NumberSequenceViewSet(viewsets.ModelViewSet):
    queryset = NumberSequence.objects.all().order_by("-id")
    serializer_class = NumberSequenceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["document_type"]
    ordering_fields = ["id"]
    ordering = ["-id"]


class ApprovalRuleViewSet(viewsets.ModelViewSet):
    queryset = ApprovalRule.objects.all()
    serializer_class = ApprovalRuleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["document_type", "is_active"]


class AuditLogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Read-only viewset for audit logs."""

    queryset = AuditLog.objects.select_related("user").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["model_name", "action", "user"]
    search_fields = ["model_name", "description"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


class PostingRuleViewSet(viewsets.ModelViewSet):
    queryset = PostingRule.objects.all().order_by("-created_at", "-id")
    serializer_class = PostingRuleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["transaction_type", "active"]
    search_fields = ["name", "condition"]
    ordering_fields = ["created_at", "name"]
    ordering = ["-created_at", "-id"]


class IntegrationRuleViewSet(viewsets.ModelViewSet):
    queryset = IntegrationRule.objects.all().order_by("-created_at", "-id")
    serializer_class = IntegrationRuleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["connected", "last_test_status"]
    search_fields = ["name", "description", "endpoint"]
    ordering_fields = ["created_at", "name"]
    ordering = ["-created_at", "-id"]


class ApprovalWorkflowViewSet(viewsets.ModelViewSet):
    queryset = ApprovalWorkflow.objects.all().order_by("-created_at", "-id")
    serializer_class = ApprovalWorkflowSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["document_type", "is_active"]
    search_fields = ["name", "escalation", "delegation"]
    ordering_fields = ["created_at", "name", "threshold"]
    ordering = ["-created_at", "-id"]


class LockDateViewSet(viewsets.ModelViewSet):
    queryset = LockDate.objects.all()
    serializer_class = LockDateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["type"]
    search_fields = ["name", "description", "scope", "applies_to"]
    ordering_fields = ["lock_date", "created_at"]
    ordering = ["-created_at"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
