from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from accounting.models import (
    Account,
    JournalEntry,
    Voucher,
    Bill,
    Invoice,
    Payment,
    Budget,
    BankAccount,
)


class AccountingDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)

        # Account summaries
        accounts = Account.objects.filter(is_active=True)
        total_assets = (
            accounts.filter(account_type__classification="asset").aggregate(
                total=Sum("current_balance")
            )["total"]
            or 0
        )
        total_liabilities = (
            accounts.filter(account_type__classification="liability").aggregate(
                total=Sum("current_balance")
            )["total"]
            or 0
        )
        total_income = (
            accounts.filter(account_type__classification="income").aggregate(
                total=Sum("current_balance")
            )["total"]
            or 0
        )
        total_expense = (
            accounts.filter(account_type__classification="expense").aggregate(
                total=Sum("current_balance")
            )["total"]
            or 0
        )

        # Journal entries this month
        journal_this_month = JournalEntry.objects.filter(
            date__gte=month_start, date__lte=today
        ).aggregate(
            count=Count("id"),
            total_debit=Sum("total_debit"),
        )

        # Voucher stats
        voucher_stats = Voucher.objects.aggregate(
            pending=Count("id", filter=Q(status="pending")),
            approved=Count("id", filter=Q(status="approved")),
            draft=Count("id", filter=Q(status="draft")),
        )

        # Payables
        payable_stats = Bill.objects.filter(
            status__in=["approved", "partial"]
        ).aggregate(
            count=Count("id"),
            total=Sum("total_amount"),
            paid=Sum("amount_paid"),
        )
        outstanding_payables = (payable_stats["total"] or 0) - (
            payable_stats["paid"] or 0
        )

        # Receivables
        receivable_stats = Invoice.objects.filter(
            status__in=["sent", "partial", "overdue"]
        ).aggregate(
            count=Count("id"),
            total=Sum("total_amount"),
            paid=Sum("amount_paid"),
        )
        outstanding_receivables = (receivable_stats["total"] or 0) - (
            receivable_stats["paid"] or 0
        )

        # Overdue bills
        overdue_bills = Bill.objects.filter(
            status__in=["approved", "partial"],
            due_date__lt=today,
        ).count()

        # Overdue invoices
        overdue_invoices = Invoice.objects.filter(
            status__in=["sent", "partial"],
            due_date__lt=today,
        ).count()

        # Recent payments
        recent_payments = Payment.objects.filter(
            date__gte=today - timedelta(days=30)
        ).aggregate(
            inbound=Sum("amount", filter=Q(direction="inbound")),
            outbound=Sum("amount", filter=Q(direction="outbound")),
        )

        # Bank balances
        bank_balances = list(
            BankAccount.objects.filter(status="active").values(
                "name", "bank_name", "current_balance"
            )
        )

        # Budget utilization
        active_budgets = Budget.objects.filter(status="validated")
        budget_summary = active_budgets.aggregate(
            total_planned=Sum("total_planned"),
            total_actual=Sum("total_actual"),
        )

        return Response(
            {
                "summary": {
                    "total_assets": float(total_assets),
                    "total_liabilities": float(total_liabilities),
                    "total_income": float(total_income),
                    "total_expense": float(total_expense),
                    "net_income": float(total_income) - float(total_expense),
                    "net_worth": float(total_assets) - float(total_liabilities),
                },
                "journal_entries": {
                    "this_month_count": journal_this_month["count"] or 0,
                    "this_month_total": float(journal_this_month["total_debit"] or 0),
                },
                "vouchers": voucher_stats,
                "payables": {
                    "outstanding_count": payable_stats["count"] or 0,
                    "outstanding_amount": float(outstanding_payables),
                    "overdue_count": overdue_bills,
                },
                "receivables": {
                    "outstanding_count": receivable_stats["count"] or 0,
                    "outstanding_amount": float(outstanding_receivables),
                    "overdue_count": overdue_invoices,
                },
                "cash_flow": {
                    "inbound_30d": float(recent_payments["inbound"] or 0),
                    "outbound_30d": float(recent_payments["outbound"] or 0),
                },
                "bank_accounts": bank_balances,
                "budget": {
                    "total_planned": float(budget_summary["total_planned"] or 0),
                    "total_actual": float(budget_summary["total_actual"] or 0),
                    "utilization_pct": (
                        round(
                            float(budget_summary["total_actual"] or 0)
                            / float(budget_summary["total_planned"])
                            * 100,
                            1,
                        )
                        if budget_summary["total_planned"]
                        else 0
                    ),
                },
            }
        )
