import django_filters
from django.db.models import Q
from ..models.quotation_models import VendorQuotation
from ..models.comparative_models import ComparativeStatement
from ..models.award_models import Award
from ..models.work_order_models import WorkOrder
from ..models.grn_models import GoodsReceiptNote
from ..models.payment_requisition_models import PaymentRequisition
from ..models.treasury_models import TreasuryProcessing, PaymentRecord
from ..models.vendor_models import VendorEvaluation, VendorPerformance


class VendorQuotationFilter(django_filters.FilterSet):
    supplier = django_filters.CharFilter(
        field_name="supplier__name", lookup_expr="icontains"
    )
    rfq = django_filters.NumberFilter(field_name="rfq__id")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    submitted_after = django_filters.DateFilter(
        field_name="submitted_date", lookup_expr="gte"
    )
    submitted_before = django_filters.DateFilter(
        field_name="submitted_date", lookup_expr="lte"
    )

    class Meta:
        model = VendorQuotation
        fields = ["supplier", "rfq", "status"]


class ComparativeStatementFilter(django_filters.FilterSet):
    rfq = django_filters.NumberFilter(field_name="rfq__id")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    recommended_supplier = django_filters.NumberFilter(
        field_name="recommended_supplier__id"
    )
    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="gte"
    )

    class Meta:
        model = ComparativeStatement
        fields = ["rfq", "status", "recommended_supplier"]


class AwardFilter(django_filters.FilterSet):
    vendor_id = django_filters.CharFilter(
        field_name="vendor_profile__id", lookup_expr="icontains"
    )

    vendor_email = django_filters.CharFilter(
        field_name="vendor_profile__email", lookup_expr="iexact"
    )
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    acceptanceStatus = django_filters.CharFilter(method="filter_acceptance_status")
    rfq = django_filters.NumberFilter(field_name="rfq__id")
    csNumber = django_filters.CharFilter(
        field_name="comparative_statement__cs_number", lookup_expr="iexact"
    )

    def filter_acceptance_status(self, queryset, name, value):
        # Support both repeated params (?acceptanceStatus=pending&acceptanceStatus=accepted)
        # and comma-separated values (?acceptanceStatus=pending,accepted)
        raw = self.request.GET.getlist("acceptanceStatus")
        values = []
        for v in raw:
            values.extend(part.strip() for part in v.split(",") if part.strip())
        return queryset.filter(acceptance_status__in=values) if values else queryset

    class Meta:
        model = Award
        fields = [
            "vendor_id",
            "vendor_email",
            "status",
            "acceptanceStatus",
            "rfq",
            "csNumber",
        ]


class WorkOrderFilter(django_filters.FilterSet):
    supplier = django_filters.CharFilter(
        field_name="award__vendor_profile__name", lookup_expr="icontains"
    )
    award_no = django_filters.CharFilter(
        field_name="award__award_number", lookup_expr="iexact"
    )
    csNumber = django_filters.CharFilter(
        field_name="award__comparative_statement__cs_number", lookup_expr="iexact"
    )
    vendor_email = django_filters.CharFilter(method="filter_vendor_email")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    approval_status = django_filters.CharFilter(
        field_name="approval_status", lookup_expr="iexact"
    )
    vendor_status = django_filters.CharFilter(method="filter_vendor_status")
    delivery_status = django_filters.CharFilter(
        field_name="delivery_status", lookup_expr="iexact"
    )
    payment_status = django_filters.CharFilter(
        field_name="payment_status", lookup_expr="iexact"
    )
    vendor = django_filters.NumberFilter(field_name="vendor")
    delivery_date_after = django_filters.DateFilter(
        field_name="delivery_date", lookup_expr="gte"
    )
    delivery_date_before = django_filters.DateFilter(
        field_name="delivery_date", lookup_expr="lte"
    )

    def filter_vendor_email(self, queryset, name, value):
   
        return queryset.filter(
            Q(vendor__email__iexact=value)
        ).distinct()

    def filter_vendor_status(self, queryset, name, value):
        normalized = (value or "").strip().lower()
        if normalized != "accepted":
            return queryset.filter(vendor_status__iexact=value)

        return queryset.filter(
            Q(vendor_status__iexact=value)
            | Q(vendor_acceptance__status__iexact="Accepted")
            | Q(
                award__acceptance_status__iexact="accepted",
                award__comparative_statement__quotations__is_direct_evaluation=True,
            )
        ).distinct()

    class Meta:
        model = WorkOrder
        fields = [
            "status",
            "approval_status",
            "vendor_status",
            "delivery_status",
            "payment_status",
            "vendor",
            "csNumber",
            "vendor_email",
        ]


class GoodsReceiptNoteFilter(django_filters.FilterSet):
    supplier = django_filters.CharFilter(
        field_name="supplier__name", lookup_expr="icontains"
    )
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    work_order = django_filters.NumberFilter(field_name="work_order__id")
    received_after = django_filters.DateFilter(
        field_name="received_date", lookup_expr="gte"
    )

    class Meta:
        model = GoodsReceiptNote
        fields = ["supplier", "status", "work_order"]


class PaymentRequisitionFilter(django_filters.FilterSet):
    supplier = django_filters.CharFilter(
        field_name="supplier__name", lookup_expr="icontains"
    )
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    priority = django_filters.CharFilter(field_name="priority", lookup_expr="iexact")
    department = django_filters.NumberFilter(field_name="department__id")
    amount_min = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="gte"
    )
    amount_max = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="lte"
    )

    class Meta:
        model = PaymentRequisition
        fields = ["supplier", "status", "priority", "department"]


class TreasuryProcessingFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    prf_number = django_filters.CharFilter(
        field_name="payment_requisition__prf_number", lookup_expr="icontains"
    )

    class Meta:
        model = TreasuryProcessing
        fields = ["status"]


class PaymentRecordFilter(django_filters.FilterSet):
    supplier = django_filters.CharFilter(
        field_name="supplier__name", lookup_expr="icontains"
    )
    payment_method = django_filters.CharFilter(
        field_name="payment_method", lookup_expr="iexact"
    )
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    payment_date_after = django_filters.DateFilter(
        field_name="payment_date", lookup_expr="gte"
    )
    payment_date_before = django_filters.DateFilter(
        field_name="payment_date", lookup_expr="lte"
    )

    class Meta:
        model = PaymentRecord
        fields = ["supplier", "payment_method", "status"]


class VendorEvaluationFilter(django_filters.FilterSet):
    supplier = django_filters.NumberFilter(field_name="supplier__id")
    min_rating = django_filters.NumberFilter(
        field_name="overall_rating", lookup_expr="gte"
    )

    class Meta:
        model = VendorEvaluation
        fields = ["supplier"]


class VendorPerformanceFilter(django_filters.FilterSet):
    supplier = django_filters.NumberFilter(field_name="supplier__id")
    period_year = django_filters.NumberFilter(field_name="period_year")
    period_month = django_filters.NumberFilter(field_name="period_month")

    class Meta:
        model = VendorPerformance
        fields = ["supplier", "period_year", "period_month"]
