from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Sum, Q
from django.utils import timezone

from accounting.models import (
    FinancialReportTemplate,
    ReportLine,
    GeneratedReport,
    GeneratedReportData,
    Account,
    JournalItem,
)
from accounting.serializers.report_serializers import (
    FinancialReportTemplateSerializer,
    GeneratedReportListSerializer,
    GeneratedReportDetailSerializer,
)


class FinancialReportTemplateViewSet(viewsets.ModelViewSet):
    queryset = FinancialReportTemplate.objects.all()
    serializer_class = FinancialReportTemplateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["report_type", "is_active"]
    search_fields = ["name"]


class GeneratedReportViewSet(viewsets.ModelViewSet):
    queryset = GeneratedReport.objects.select_related("template", "generated_by").all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["template", "status"]
    ordering_fields = ["generated_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return GeneratedReportListSerializer
        return GeneratedReportDetailSerializer

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Generate a financial report."""
        template_id = request.data.get("template_id")
        date_from = request.data.get("date_from")
        date_to = request.data.get("date_to")

        if not all([template_id, date_from, date_to]):
            return Response(
                {"detail": "template_id, date_from, and date_to are required."},
                status=400,
            )

        try:
            template = FinancialReportTemplate.objects.get(id=template_id)
        except FinancialReportTemplate.DoesNotExist:
            return Response({"detail": "Template not found."}, status=404)

        report = GeneratedReport.objects.create(
            template=template,
            title=f"{template.name} ({date_from} to {date_to})",
            period_from=date_from,
            period_to=date_to,
            generated_by=request.user,
            status="generating",
        )

        report_lines = template.lines.order_by("sequence").all()
        computed_values = {}

        for line in report_lines:
            value = self._compute_line(line, date_from, date_to, computed_values)
            computed_values[line.id] = value
            GeneratedReportData.objects.create(
                report=report,
                report_line=line,
                label=line.name,
                current_amount=value,
                sequence=line.sequence,
            )

        report.status = "completed"
        report.save(update_fields=["status"])

        serializer = GeneratedReportDetailSerializer(report)
        return Response(serializer.data, status=201)

    def _compute_line(self, line, date_from, date_to, computed_values):
        """Compute value for a report line based on its computation type."""
        if line.computation_type == "sum_of_accounts":
            account_ids = line.account_codes.split(",") if line.account_codes else []
            account_ids = [a.strip() for a in account_ids if a.strip()]
            if not account_ids:
                return 0
            result = JournalItem.objects.filter(
                account__code__in=account_ids,
                journal_entry__date__gte=date_from,
                journal_entry__date__lte=date_to,
                journal_entry__status="posted",
            ).aggregate(
                total_debit=Sum("debit"),
                total_credit=Sum("credit"),
            )
            debit = result["total_debit"] or 0
            credit = result["total_credit"] or 0
            return float(debit - credit)

        elif line.computation_type == "sum_of_lines":
            # Sum child lines (lines whose parent is this line)
            child_line_ids = list(
                ReportLine.objects.filter(parent=line).values_list("id", flat=True)
            )
            total = 0
            for cid in child_line_ids:
                total += computed_values.get(cid, 0)
            return total

        elif line.computation_type == "total":
            return sum(computed_values.values())

        return 0

    @action(detail=False)
    def trial_balance(self, request):
        """Quick trial balance report."""
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if not date_from or not date_to:
            return Response({"detail": "date_from and date_to required."}, status=400)

        accounts = Account.objects.filter(is_active=True).order_by("code")
        data = []
        for account in accounts:
            totals = JournalItem.objects.filter(
                account=account,
                journal_entry__date__gte=date_from,
                journal_entry__date__lte=date_to,
                journal_entry__status="posted",
            ).aggregate(
                total_debit=Sum("debit"),
                total_credit=Sum("credit"),
            )
            debit = totals["total_debit"] or 0
            credit = totals["total_credit"] or 0
            if debit or credit:
                data.append(
                    {
                        "account_code": account.code,
                        "account_name": account.name,
                        "debit": float(debit),
                        "credit": float(credit),
                        "balance": float(debit - credit),
                    }
                )

        total_debit = sum(d["debit"] for d in data)
        total_credit = sum(d["credit"] for d in data)

        return Response(
            {
                "date_from": date_from,
                "date_to": date_to,
                "lines": data,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "is_balanced": abs(total_debit - total_credit) < 0.01,
            }
        )
