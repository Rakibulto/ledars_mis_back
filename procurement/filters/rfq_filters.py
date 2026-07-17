import django_filters
from ..models.requisition_models import MaterialRequisition
from ..models.rfq_models import RFQ, RFQVendorInvitation, RFQAttachment


class MaterialRequisitionFilter(django_filters.FilterSet):
    requisition_no = django_filters.CharFilter(field_name="requisition_no", lookup_expr="icontains")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    priority = django_filters.CharFilter(field_name="priority", lookup_expr="iexact")
    department = django_filters.NumberFilter(field_name="department__id")
    department_name = django_filters.CharFilter(
        field_name="department__name", lookup_expr="icontains"
    )
    category = django_filters.NumberFilter(field_name="category__id")
    budget_code = django_filters.NumberFilter(field_name="budget_code__id")
    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateFilter(
        field_name="created_at", lookup_expr="lte"
    )
    delivery_after = django_filters.DateFilter(
        field_name="delivery_date", lookup_expr="gte"
    )
    delivery_before = django_filters.DateFilter(
        field_name="delivery_date", lookup_expr="lte"
    )
    min_amount = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="gte"
    )
    max_amount = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="lte"
    )

    class Meta:
        model = MaterialRequisition
        fields = [
            "requisition_no",
            "status",
            "priority",
            "department",
            "department_name",
            "category",
            "budget_code",
        ]

class RFQFilter(django_filters.FilterSet):
    rfq_number = django_filters.CharFilter(field_name="rfq_number", lookup_expr="icontains")
    rfq_title = django_filters.CharFilter(field_name="rfq_title", lookup_expr="icontains")
    title = django_filters.CharFilter(field_name="rfq_title", lookup_expr="icontains")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    category = django_filters.CharFilter(field_name="rfq_category__name", lookup_expr="icontains")
    rfq_category = django_filters.CharFilter(field_name="rfq_category__name", lookup_expr="icontains")
    category_name = django_filters.CharFilter(field_name="rfq_category__name", lookup_expr="icontains")
    invited_vendor_user_id = django_filters.NumberFilter(
        field_name="vendor_invitations__vendor__user__id", lookup_expr="exact"
    )
    invited_vendor_username = django_filters.CharFilter(
        field_name="vendor_invitations__vendor__user__username", lookup_expr="icontains"
    )
    invited_vendor_email = django_filters.CharFilter(
        field_name="vendor_invitations__vendor__user__email", lookup_expr="icontains"
    )

    class Meta:
        model = RFQ
        fields = [
            "rfq_number",
            "rfq_title",
            "title",
            "status",
            "category",
            "category_name",
            "rfq_category",
            "invited_vendor_user_id",
            "invited_vendor_username",
            "invited_vendor_email",
        ]

class RFQInvitedVendorFilter(django_filters.FilterSet):
    rfq = django_filters.CharFilter(field_name="rfq__rfq_number", lookup_expr="icontains")
    vendor = django_filters.NumberFilter(field_name="vendor__id")

    class Meta:
        model = RFQVendorInvitation
        fields = [
            "rfq",
            "vendor",
        ]


class RFQAttachmentFilter(django_filters.FilterSet):
    rfq_number = django_filters.CharFilter(field_name="rfq__rfq_number", lookup_expr="icontains")
    rfq_title = django_filters.CharFilter(field_name="rfq__rfq_title", lookup_expr="icontains")
    created_by_username = django_filters.CharFilter(
        field_name="created_by__username", lookup_expr="icontains"
    )
    created_by_email = django_filters.CharFilter(
        field_name="created_by__email", lookup_expr="icontains"
    )

    class Meta:
        model = RFQAttachment
        fields = [
            "rfq_number",
            "rfq_title",
            "created_by_username",
            "created_by_email",
        ]