from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status as http_status

from django.utils import timezone as tz

from paginations import Pagination
from inventory.models import ScrapRecord, ReturnRecord, StockMove
from inventory.serializers.scrap_returns import (
    ScrapRecordReadSerializer,
    ScrapRecordSerializer,
    ReturnRecordReadSerializer,
    ReturnRecordSerializer,
    _apply_scrap_stock_deduction,
)
from inventory.services.scrap_workflow import (
    get_level_users,
    get_user_level_entry,
    resolve_matched_level_for_scrap,
    user_already_approved,
)


class ScrapRecordViewSet(ModelViewSet):
    queryset = ScrapRecord.objects.select_related(
        "product", "product__uom", "warehouse", "scrapped_by", "approved_by"
    ).all()
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "reference",
        "reason",
        "disposal_method",
        "certificate_number",
        "product__name",
        "product__code",
        "warehouse__name",
        "scrapped_by__username",
    ]
    ordering_fields = ["reference", "date", "disposal_date", "created_at", "quantity"]
    ordering = ["-date", "-created_at"]
    filterset_fields = ["status", "warehouse", "product", "scrapped_by", "disposal_method"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return ScrapRecordReadSerializer
        return ScrapRecordSerializer

    def perform_destroy(self, instance):
        with transaction.atomic():
            StockMove.objects.filter(reference=instance.reference, move_type="Scrap").delete()
            instance.delete()

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """
        POST /api/scrap-records/{id}/approve/

        Workflow approval for scrap records. Follows the same pattern as GIN approval.
        """
        scrap_record = self.get_object()
        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response(
                {"detail": "Authentication is required."},
                status=http_status.HTTP_401_UNAUTHORIZED,
            )

        if scrap_record.status == "Approved":
            return Response(
                {"detail": f"Cannot approve scrap record in '{scrap_record.status}' status."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        workflow, matched_level = resolve_matched_level_for_scrap(scrap_record)

        if not workflow or not matched_level:
            return Response(
                {"detail": "No active approval workflow configured for scrap management."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        level_users = get_level_users(matched_level)
        user_entry = get_user_level_entry(level_users, user)

        if not user_entry:
            return Response(
                {"detail": "You are not an authorized approver for this scrap record."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        if user_already_approved(scrap_record, user):
            return Response(
                {"detail": "You have already approved this scrap record."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        current_approval_level = scrap_record.approval_level or 0
        min_required = matched_level.minimum_approval_required or 1
        ordered = matched_level.level_maintain_require == "yes"

        if ordered:
            next_order = current_approval_level + 1
            if user_entry.approval_order != next_order:
                return Response(
                    {
                        "detail": (
                            f"Approval order requires user with order {next_order} "
                            "to approve next."
                        )
                    },
                    status=http_status.HTTP_403_FORBIDDEN,
                )
        else:
            if current_approval_level >= min_required:
                return Response(
                    {"detail": "All required approvals have already been received."},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

        new_approval_level = current_approval_level + 1
        is_final = new_approval_level >= min_required

        log_entry = {
            "approved_at": tz.localtime().isoformat(),
            "action": "approval",
            "name": user.get_full_name() or user.username or user.email or "Unknown",
            "email": user.email or "",
            "user_id": user.id,
        }

        current_log = list(scrap_record.approval_log or [])
        current_log.append(log_entry)

        update_fields = {
            "approval_level": new_approval_level,
            "approval_log": current_log,
        }

        if is_final:
            from inventory.serializers.scrap_returns import _apply_scrap_stock_deduction

            update_fields["status"] = "Approved"
            update_fields["approved_by"] = user
            with transaction.atomic():
                ScrapRecord.objects.filter(pk=scrap_record.pk).update(**update_fields)
                scrap_record.refresh_from_db()
                _apply_scrap_stock_deduction(scrap_record)
        else:
            update_fields["status"] = "Pending Approval"
            ScrapRecord.objects.filter(pk=scrap_record.pk).update(**update_fields)
            scrap_record.refresh_from_db()

        serializer = ScrapRecordReadSerializer(scrap_record, context={"request": request})
        return Response(serializer.data)


class ReturnRecordViewSet(ModelViewSet):
    queryset = ReturnRecord.objects.select_related("product", "product__uom", "warehouse", "created_by").all()
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "reference",
        "original_reference",
        "reason",
        "condition",
        "product__name",
        "product__code",
        "warehouse__name",
        "created_by__username",
    ]
    ordering_fields = ["reference", "date", "created_at", "quantity"]
    ordering = ["-date", "-created_at"]
    filterset_fields = ["return_type", "status", "warehouse", "product", "created_by"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return ReturnRecordReadSerializer
        return ReturnRecordSerializer

    def perform_destroy(self, instance):
        with transaction.atomic():
            StockMove.objects.filter(reference=instance.reference, move_type="Return").delete()
            instance.delete()
