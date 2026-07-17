import django_filters
from ..models.requisition_models import MaterialRequisition


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
