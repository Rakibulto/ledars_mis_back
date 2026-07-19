from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.utils import timezone

from accounting.models import (
    Journal,
    JournalEntry,
    JournalItem,
    JournalEntryAttachment,
    RecurringJournalTemplate,
    RecurringJournalLine,
)
from accounting.serializers.journal_serializers import (
    JournalSerializer,
    JournalEntryListSerializer,
    JournalEntryDetailSerializer,
    JournalEntryWriteSerializer,
    JournalEntryAttachmentSerializer,
    JournalItemSerializer,
    RecurringJournalTemplateSerializer,
)
from accounting.views.status_transition_mixin import StatusTransitionMixin


class JournalViewSet(viewsets.ModelViewSet):
    queryset = Journal.objects.all()
    serializer_class = JournalSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["journal_type", "is_active"]
    search_fields = ["name", "code"]

    @action(detail=False, methods=["post"])
    def seed(self, request):
        """Create standard accounting journals if they don't exist."""
        journals_data = [
            # Purchase journals
            {"name": "Vendor Bills Journal", "journal_type": "purchase", "sequence_prefix": "PUR"},
            {"name": "Vendor Payments Journal", "journal_type": "purchase", "sequence_prefix": "VPY"},
            # Sales journals
            {"name": "Customer Invoices Journal", "journal_type": "sales", "sequence_prefix": "SAL"},
            {"name": "Customer Receipts Journal", "journal_type": "sales", "sequence_prefix": "CRJ"},
            # Bank journals
            {"name": "Bank Payments Journal", "journal_type": "bank", "sequence_prefix": "BPY"},
            {"name": "Bank Receipts Journal", "journal_type": "bank", "sequence_prefix": "BRJ"},
            # Cash journals
            {"name": "Cash Journal", "journal_type": "cash", "sequence_prefix": "CSH"},
            # General journals
            {"name": "General Journal", "journal_type": "general", "sequence_prefix": "GEN"},
            {"name": "Miscellaneous Journal", "journal_type": "general", "sequence_prefix": "MSC"},
        ]

        created_count = 0
        for data in journals_data:
            _, is_new = Journal.objects.get_or_create(
                journal_type=data["journal_type"],
                name=data["name"],
                defaults={
                    "sequence_prefix": data["sequence_prefix"],
                    "is_active": True,
                },
            )
            if is_new:
                created_count += 1

        total = Journal.objects.count()
        return Response({
            "detail": f"Seeded {created_count} new journal(s). Total journals: {total}",
            "created": created_count,
            "total": total,
        })


class JournalEntryViewSet(StatusTransitionMixin, viewsets.ModelViewSet):
    queryset = JournalEntry.objects.select_related(
        "journal", "created_by", "ngo_project"
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["journal", "status", "date", "ngo_project"]
    search_fields = ["reference", "narration", "source_document"]
    ordering_fields = ["date", "reference", "total_debit", "created_at"]
    ordering_fields = ["date", "reference", "total_debit", "created_at", "id"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return JournalEntryListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return JournalEntryWriteSerializer
        return JournalEntryDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="post-entry")
    def post_entry(self, request, pk=None):
        """Post a journal entry — updates account balances."""
        entry = self.get_object()
        if entry.status != "draft":
            return Response({"detail": "Only draft entries can be posted."}, status=400)

        with transaction.atomic():
            for item in entry.items.select_related("account").all():
                account = item.account
                account.current_balance += item.debit - item.credit
                account.save(update_fields=["current_balance"])

            entry.status = "posted"
            entry.posted_by = request.user
            entry.posted_at = timezone.now()
            entry.save(update_fields=["status", "posted_by", "posted_at"])

        serializer = self.get_serializer(entry)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a journal entry — reverses account balances if posted."""
        entry = self.get_object()
        if entry.status == "cancelled":
            return Response({"detail": "Already cancelled."}, status=400)

        with transaction.atomic():
            if entry.status == "posted":
                for item in entry.items.select_related("account").all():
                    account = item.account
                    account.current_balance -= item.debit - item.credit
                    account.save(update_fields=["current_balance"])

            entry.status = "cancelled"
            entry.save(update_fields=["status"])

        return Response({"detail": "Journal entry cancelled."})


class JournalItemViewSet(viewsets.ModelViewSet):
    queryset = JournalItem.objects.select_related(
        "journal_entry", "journal_entry__journal",
        "account", "analytic_account", "cost_center"
    ).all()
    serializer_class = JournalItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["journal_entry", "account", "is_reconciled"]
    search_fields = ["label", "account__code", "account__name"]
    ordering_fields = ["journal_entry__date", "id", "created_at"]
    ordering = ["-journal_entry__date", "-id"]

    def get_queryset(self):
        qs = super().get_queryset()
        account_code = self.request.query_params.get("account_code")
        if account_code:
            qs = qs.filter(account__code=account_code)
        return qs


class RecurringJournalTemplateViewSet(viewsets.ModelViewSet):
    queryset = RecurringJournalTemplate.objects.select_related("journal").all()
    serializer_class = RecurringJournalTemplateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["journal", "frequency", "is_active"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        """Execute a recurring template to create a journal entry."""
        template = self.get_object()
        with transaction.atomic():
            entry = JournalEntry.objects.create(
                journal=template.journal,
                date=timezone.now().date(),
                narration=template.narration,
                status="posted" if template.auto_post else "draft",
                is_auto_generated=True,
                created_by=request.user,
            )
            total_debit = 0
            total_credit = 0
            for line in template.lines.all():
                JournalItem.objects.create(
                    journal_entry=entry,
                    account=line.account,
                    label=line.label,
                    debit=line.debit,
                    credit=line.credit,
                    analytic_account=line.analytic_account,
                )
                total_debit += line.debit
                total_credit += line.credit
            entry.total_debit = total_debit
            entry.total_credit = total_credit
            entry.save(update_fields=["total_debit", "total_credit"])

            from dateutil.relativedelta import relativedelta

            freq_map = {
                "daily": relativedelta(days=1),
                "weekly": relativedelta(weeks=1),
                "monthly": relativedelta(months=1),
                "quarterly": relativedelta(months=3),
                "yearly": relativedelta(years=1),
            }
            template.next_run_date += freq_map.get(
                template.frequency, relativedelta(months=1)
            )
            template.save(update_fields=["next_run_date"])

        return Response({"detail": f"Journal entry {entry.reference} created."})


class JournalEntryAttachmentViewSet(viewsets.ModelViewSet):
    queryset = JournalEntryAttachment.objects.select_related("journal_entry").all()
    serializer_class = JournalEntryAttachmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["journal_entry"]

    def perform_create(self, serializer):
        serializer.save()
