# -------------
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from attendance.models import AttendanceData
from .serializers import AttendanceDataSerializer
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# ADMS Push Views (called by ZKTeco device)
# ─────────────────────────────────────────────


@method_decorator(csrf_exempt, name="dispatch")
class CDataView(View):

    def get(self, request):
        """Device handshake"""
        sn = request.GET.get("SN", "unknown")
        logger.info(f"[ADMS] Device handshake: SN={sn}")
        return HttpResponse("OK")

    def post(self, request):
        """Device pushes attendance logs"""
        sn = request.GET.get("SN", "unknown")
        body = request.body.decode("utf-8")
        logger.info(f"[ADMS] Raw data from {sn}:\n{body}")

        saved, skipped = 0, 0

        for line in body.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("ATTLOG") or line.startswith("SN="):
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                continue

            try:
                rfid_or_machine_code = parts[0]
                timestamp = parse_datetime(parts[1].replace(" ", "T"))
                if not timestamp:
                    logger.warning(f"[ADMS] Could not parse timestamp: {parts[1]}")
                    skipped += 1
                    continue

                # Ensure timestamp is timezone-aware
                if timezone.is_naive(timestamp):
                    timestamp = timezone.make_aware(
                        timestamp, timezone.get_current_timezone()
                    )

                # Avoid duplicate punches (same user + same timestamp)
                already_exists = AttendanceData.objects.filter(
                    rfid_or_machine_code=rfid_or_machine_code,
                    timestamp=timestamp,
                ).exists()

                if already_exists:
                    skipped += 1
                    continue

                AttendanceData.objects.create(
                    rfid_or_machine_code=rfid_or_machine_code,
                    timestamp=timestamp,
                    device_serial_number=sn,
                    login_type="Device Login",
                    # employee + attendance_status resolved in model.save()
                )
                saved += 1

            except Exception as e:
                logger.error(f"[ADMS] Failed to parse line: '{line}' | {e}")
                skipped += 1

        logger.info(f"[ADMS] Saved={saved} Skipped={skipped}")
        return HttpResponse("OK")


@method_decorator(csrf_exempt, name="dispatch")
class GetRequestView(View):
    def get(self, request):
        return HttpResponse("OK")


@method_decorator(csrf_exempt, name="dispatch")
class DeviceCmdView(View):
    def post(self, request):
        return HttpResponse("OK")


# ─────────────────────────────────────────────
# AttendanceData ViewSet (REST API)
# ─────────────────────────────────────────────


class AttendanceDataViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceDataSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "employee",
        "attendance_status",
        "login_type",
        "device_serial_number",
    ]
    search_fields = ["employee__user__email", "rfid_or_machine_code"]
    ordering_fields = ["timestamp", "created_at"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        user = self.request.user
        qs = AttendanceData.objects.select_related("employee__user", "created_by__user")

        # Custom permission-based filtering
        if user.has_perm("attendance.view_subordinate_attendance"):
            return qs  # managers/HR see all
        elif user.has_perm("attendance.view_own_attendance"):
            return qs.filter(employee__user=user)  # employee sees own only
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(
            login_type="Manual Entry",
            created_by=self.request.user.employee,  # assumes user has employee profile
        )

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user.employee)

    # ── Extra actions ──

    @action(detail=False, methods=["get"], url_path="my-attendance")
    def my_attendance(self, request):
        """Shortcut: current user's own attendance"""
        qs = AttendanceData.objects.filter(employee__user=request.user).order_by(
            "-timestamp"
        )
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """Quick count breakdown by status for a given employee"""
        employee_id = request.query_params.get("employee_id")
        if not employee_id:
            return Response(
                {"detail": "employee_id query param required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = AttendanceData.objects.filter(employee_id=employee_id)
        summary = {
            "total": qs.count(),
            "present": qs.filter(attendance_status="Present").count(),
            "late": qs.filter(attendance_status="Late").count(),
            "absent": qs.filter(attendance_status="Absent").count(),
            "early_leave": qs.filter(attendance_status="Early Leave").count(),
            "overtime": qs.filter(attendance_status="Overtime").count(),
            "not_detected": qs.filter(attendance_status="Not Detected").count(),
        }
        return Response(summary)
