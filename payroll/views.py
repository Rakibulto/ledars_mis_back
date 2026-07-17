from django.shortcuts import render
from rest_framework.generics import ListAPIView, RetrieveAPIView
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from payroll.models import Payroll
from payroll.serializers import (
    LockPayrollSerializer,
    PayrollSerializer,
    GeneratePayrollSerializer,
)
from payroll.utils import generate_payroll, generate_payroll_async
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

# Create your views here.


class PayrollListViewSet(ListAPIView):
    """Return payroll queryset, optionally narrowed by filters.

    The returned queryset is additionally trimmed based on the requesting
    user's permissions (see the permission block at the end of the method).

    Supported query parameters (all optional):

    * **employee** – string that is matched case-insensitively against
        ``employee.employee_id`` or ``employee.employee_name`` (``icontains``).
        Useful for searching by either ID or name.
    * **payroll_month** – the month name (e.g. "March").  Comparison is
        case-insensitive; partial matches are *not* allowed (``iexact``).
    * **payroll_year** – integer year (e.g. ``2026``).  Non-numeric values
        are ignored silently.

    These filters are applied *before* permission restrictions so that a
    supervisor querying for a particular month/year sees only matching rows
    within their allowed subset.
    """

    serializer_class = PayrollSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Get the current user from the request
        user = self.request.user

        # Base queryset
        queryset = Payroll.objects.select_related("creator", "employee").all()

        emp_filter = self.request.query_params.get("employee")
        month_filter = self.request.query_params.get("payroll_month")
        year_filter = self.request.query_params.get("payroll_year")

        if emp_filter:
            queryset = queryset.filter(
                Q(employee__employee_id__icontains=emp_filter)
                | Q(employee__employee_name__icontains=emp_filter)
            )

        if month_filter:
            queryset = queryset.filter(payroll_month__iexact=month_filter)

        if year_filter:
            try:
                year_val = int(year_filter)
                queryset = queryset.filter(payroll_year=year_val)
            except ValueError:
                pass

        # permission-based restriction remains unchanged
        if user.has_perm("payroll.view_payroll"):
            return queryset
        else:
            return queryset.filter(employee__user=user)


class PayrollDetailViewSet(RetrieveAPIView):
    serializer_class = PayrollSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Get the current user from the request
        user = self.request.user

        # Get queryset
        queryset = Payroll.objects.select_related("creator", "employee").all()

        if user.has_perm("payroll.view_payroll"):
            return queryset
        else:
            return queryset.filter(employee__user=user)


class GeneratePayrollView(APIView):
    """
    POST /api/payrolls/generate/

    Generates (or updates) payroll for active employees.


    Payload (JSON):

        {
            "month": <int>,                   # 1-12 (required if not using date range)
            "year": <int>,                    # e.g. 2026 (required if not using date range)
            "start_date": "<YYYY-MM-DD>",   # optional — explicit range start (takes precedence)
            "end_date": "<YYYY-MM-DD>",     # optional — explicit range end
            "basic_payroll": <bool>,          # include basic payroll (required, usually true)
            "festival_bonus": <bool>,         # include festival bonus (optional, default false)
            "performance_bonus": <bool>,      # include performance bonus (optional, default false)
            "employee_ids": [<int>, ...],     # optional — generate for specific employees only
            "async_generation": <bool>        # optional — run in background thread (default false)
        }

    Behavior:

    - If payroll for the month/year (or for the date range) already exists for an employee it will be
      **updated**; otherwise a new record will be **created**.
    - When a `start_date`/`end_date` pair is provided, payroll is generated for the
      explicit date range and takes precedence over `month`/`year`.
    - When ``employee_ids`` is supplied, only those employees (if active) are
      processed.  When omitted, **all** active employees are included.
    - When ``async_generation`` is true the request returns immediately with
      HTTP 202 and the payroll is generated in a background thread.  A
      notification is created for the requesting user on completion or failure.
    - The salary record used for each employee is the one whose
      ``effective_date`` is on or before the payroll month end date (or the
      payroll range end). If no ``effective_date`` is set, the most recently
      created salary is used.
    - Only users with the ``payroll.add_payroll`` permission may call this endpoint.

    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.has_perm("payroll.add_payroll"):
            raise PermissionDenied("You do not have permission to generate payroll.")

        serializer = GeneratePayrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Prefer explicit date range when provided
        start_date = serializer.validated_data.get("start_date")
        end_date = serializer.validated_data.get("end_date")
        month = serializer.validated_data.get("month")
        year = serializer.validated_data.get("year")

        include_festival = serializer.validated_data.get("festival_bonus", False)
        include_performance = serializer.validated_data.get("performance_bonus", False)
        employee_ids = serializer.validated_data.get("employee_ids") or None
        async_generation = serializer.validated_data.get("async_generation", False)

        if async_generation:
            generate_payroll_async(
                month=month,
                year=year,
                start_date=start_date,
                end_date=end_date,
                creator_id=request.user.pk,
                include_festival_bonus=include_festival,
                include_performance_bonus=include_performance,
                employee_ids=employee_ids,
            )

            resp_payload = {
                "message": "Payroll generation started in the background.",
                "async": True,
            }
            if start_date and end_date:
                resp_payload.update(
                    {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                    }
                )
            else:
                resp_payload.update({"month": month, "year": year})

            return Response(resp_payload, status=status.HTTP_202_ACCEPTED)

        try:
            payrolls = generate_payroll(
                month=month,
                year=year,
                start_date=start_date,
                end_date=end_date,
                creator=request.user,
                include_festival_bonus=include_festival,
                include_performance_bonus=include_performance,
                employee_ids=employee_ids,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        result = PayrollSerializer(payrolls, many=True).data

        resp_payload = {
            "message": f"Payroll generated for {len(payrolls)} employee(s).",
            "count": len(payrolls),
            "payrolls": result,
        }
        if start_date and end_date:
            resp_payload.update(
                {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}
            )
        else:
            resp_payload.update({"month": month, "year": year})

        return Response(resp_payload, status=status.HTTP_200_OK)


class LockPayrollView(APIView):
    """Locks or unlocks all payrolls for a given month/year.

    POST payload:

        {
            "month": "March" or 3,
            "year": 2026,
            "is_lock": true
        }

    Only users with ``payroll.change_payroll`` permission may call this.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.has_perm("payroll.change_payroll"):
            raise PermissionDenied("You do not have permission to lock payrolls.")

        serializer = LockPayrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        month_name = serializer.validated_data["month"]
        year = serializer.validated_data["year"]
        lock = serializer.validated_data["is_lock"]

        qs = Payroll.objects.filter(payroll_month=month_name, payroll_year=year)
        updated = qs.update(is_locked=lock)

        return Response(
            {
                "month": month_name,
                "year": year,
                "locked_count": updated,
                "is_locked": lock,
            },
            status=status.HTTP_200_OK,
        )
