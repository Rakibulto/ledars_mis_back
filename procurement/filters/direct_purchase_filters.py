import django_filters

from ..models.direct_purchase_models import DirectPurchase


class DirectPurchaseFilter(django_filters.FilterSet):
    dp_number = django_filters.CharFilter(field_name="dp_number", lookup_expr="icontains")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    priority = django_filters.CharFilter(field_name="priority", lookup_expr="iexact")
    department = django_filters.NumberFilter(field_name="department__id")
    department_name = django_filters.CharFilter(
        field_name="department__name", lookup_expr="icontains"
    )
    vendor = django_filters.NumberFilter(field_name="shop__id")
    shop = django_filters.NumberFilter(field_name="shop__id")
    category = django_filters.NumberFilter(field_name="category__id")
    budget_code = django_filters.NumberFilter(field_name="budget_code__id")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")
    delivery_after = django_filters.DateFilter(
        field_name="expected_delivery_date", lookup_expr="gte"
    )
    delivery_before = django_filters.DateFilter(
        field_name="expected_delivery_date", lookup_expr="lte"
    )
    min_amount = django_filters.NumberFilter(field_name="total_amount", lookup_expr="gte")
    max_amount = django_filters.NumberFilter(field_name="total_amount", lookup_expr="lte")

    class Meta:
        model = DirectPurchase
        fields = [
            "dp_number",
            "status",
            "priority",
            "department",
            "vendor",
            "shop",
            "category",
            "budget_code",
        ]
