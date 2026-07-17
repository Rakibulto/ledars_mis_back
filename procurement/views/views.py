from django.shortcuts import render
from django.db import transaction
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView, Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from inventory.views import CreatedByMixin
from paginations import Pagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from vendorportal.models.models import VendorProfile
from ..models.models import (
    PurchaseOrder,
    ItemPR,
    ItemPO,
    PurchaseRequisition,
    ApprovalRequest,
    ApprovalHistory,
)
from ..serializers.serializers import (
    SupplierSummarySerializer,
    POSummarySerializer,
    SupplierSerializer,
    PurchaseOrderSerializer,
    ItemPRSerializer,
    PurchaseRequisitionSerializer,
    ItemPOSerializer,
    ProcurementAnalyticsSerializer,
    ApprovalRequestSerializer,
    ApprovalHistorySerializer,
    PurchaseRequisitionSummarySerializer,
)
from ..filters.filters import (
    SupplierFilter,
    PurchaseOrderFilter,
    PurchaseRequisitionFilter,
    ItemPRFilter,
    ItemPOFilter,
)
from ..services.services import supplier_summary, procurement_analytics, po_summary
from employee.models import Employee


class PurchaseRequisitionSummaryAPIView(APIView):

    def get(self, request):
        total = PurchaseRequisition.objects.count()

        draft = PurchaseRequisition.objects.filter(status="Draft").count()
        submitted = PurchaseRequisition.objects.filter(status="Submitted").count()
        approved = PurchaseRequisition.objects.filter(status="Approved").count()
        po_created = PurchaseRequisition.objects.filter(status="PO Created").count()

        data = {
            "total_prs": total,
            "draft": draft,
            "submitted": submitted,
            "approved": approved,
            "po_created": po_created,
        }

        serializer = PurchaseRequisitionSummarySerializer(data)
        return Response(serializer.data)


class ProcurementAnalyticsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        data = procurement_analytics()
        serializer = ProcurementAnalyticsSerializer(data)
        return Response(serializer.data)


class SuppliersSummaryAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        data = supplier_summary()
        serializer = SupplierSummarySerializer(data)
        return Response(serializer.data)


class POSummaryAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        data = po_summary()
        serializer = POSummarySerializer(data)
        return Response(serializer.data)


class SupplierViewSet(CreatedByMixin, ModelViewSet):
    queryset = VendorProfile.objects.select_related("created_by", "user").prefetch_related("categories").all()
    permission_classes = [AllowAny]
    pagination_class = Pagination

    serializer_class = SupplierSerializer

    # 🔥 Filter + Search + Ordering
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_class = SupplierFilter

    search_fields = [
        "name",
        "code",
        "categories__name",
        "contact_person",
        "phone",
        "email",
        "address",
        "active_contracts",
        "tax_id",
        "status",
        "registration_date",
    ]

    ordering_fields = [
        "name",
        "created_at",
        "item_count",
    ]

    ordering = ["-created_at"]


class PurchaseOrderViewSet(CreatedByMixin, ModelViewSet):
    queryset = (
        PurchaseOrder.objects.select_related("supplier", "created_by")
        .prefetch_related("po_items__item")
        .all()
    )
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    serializer_class = PurchaseOrderSerializer

    # Filter + Search + Ordering
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_class = PurchaseOrderFilter

    search_fields = ["po_number", "supplier__name", "approval_status"]

    ordering_fields = [
        "created_at",
    ]

    ordering = ["-created_at"]


class ItemPOViewSet(ModelViewSet):
    queryset = ItemPO.objects.select_related("purchase_order", "item").all()
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    serializer_class = ItemPOSerializer

    # Filter + Search + Ordering
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_class = ItemPOFilter


class PurchaseRequisitionViewSet(ModelViewSet):

    queryset = PurchaseRequisition.objects.prefetch_related(
        "pr_items__item"
    ).select_related(
        "created_by",
        "created_by__department",
        "created_by__designation",
        "department",
        "project",
        "approver",
    )
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    serializer_class = PurchaseRequisitionSerializer

    # Filter + Search + Ordering
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_class = PurchaseRequisitionFilter

    search_fields = [
        "pr_number",
        "department__name",
        "project__name",
        "items__item_name",
        "status",
        "approver__employee_name",
        "created_by__employee_name",
    ]

    ordering_fields = [
        "created_at",
    ]
    ordering = ["-created_at"]

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        employee = Employee.objects.filter(user=user).first()

        serializer.save(
            created_by=employee,
        )

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()


class ItemPRViewSet(ModelViewSet):
    queryset = ItemPR.objects.all()
    permission_classes = [AllowAny]
    pagination_class = Pagination
    serializer_class = ItemPRSerializer

    # Filter + Search + Ordering
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ItemPRFilter
    # ordering = ['-created_at']

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        # Check if list
        if isinstance(request.data, list):
            serializer = self.get_serializer(data=request.data, many=True)
        else:
            serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


# class RFQViewSet(CreatedByMixin, ModelViewSet):

#     queryset = RFQ.objects.all()
#     permission_classes = [IsAuthenticated]
#     pagination_class = Pagination
#     serializer_class = RFQSerializer

#     # 🔥 Filter + Search + Ordering
#     filter_backends = [
#         DjangoFilterBackend,
#         SearchFilter,
#         OrderingFilter
#     ]

#     filterset_class = RFQFilter

#     search_fields = [
#         'rfq_number', 'title', 'description', 'status', 'suppliers_count',
#         'items__item_name', 'total_estimated_value', 'created_by__username', 'created_by__email',
#     ]
#     ordering_fields = ['created_at',]
#     ordering = ['-created_at']

#     @action(detail=False, methods=["get"], url_path="summary")
#     def rfq_summary(self, request):
#         stats = get_rfq_summary()
#         return Response(stats)


class ApprovalRequestViewSet(CreatedByMixin, ModelViewSet):

    queryset = ApprovalRequest.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    serializer_class = ApprovalRequestSerializer

    # 🔥 Filter + Search + Ordering
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    # filterset_class = RFQFilter

    search_fields = [
        "reference_number",
        "type",
        "department",
        "project",
        "submitted_date",
        "approval_level",
        "priority",
        "status",
        "current_approver__username",
        "created_by__username",
    ]

    ordering_fields = [
        "created_at",
    ]

    ordering = ["-created_at"]


class ApprovalHistoryViewSet(ModelViewSet):

    queryset = ApprovalHistory.objects.all()
    permission_classes = [AllowAny]
    pagination_class = Pagination
    serializer_class = ApprovalHistorySerializer

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(approver=user if user.is_authenticated else None)

    # 🔥 Filter + Search + Ordering
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    # filterset_class = RFQFilter

    search_fields = [
        "approval_request__reference_number",
        "approver__current_approver",
        "department",
        "role",
        "action",
        "comments",
        "level",
        "created_at",
    ]

    ordering_fields = [
        "created_at",
    ]

    ordering = ["-created_at"]
