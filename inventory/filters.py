import django_filters

from .models import Category, Product, QCTemplate, QualityAlert, QualityCheck, QualityTeam


class CategoryFilter(django_filters.FilterSet):
    level = django_filters.CharFilter(field_name="level", lookup_expr="iexact")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    name = django_filters.CharFilter(field_name="name", lookup_expr="iexact")
    category_id = django_filters.CharFilter(field_name="id", lookup_expr="iexact")
    parent = django_filters.NumberFilter(field_name="parent_id")

    class Meta:
        model = Category
        fields = ["level", "status", "parent"]


class ProductFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    stock_status = django_filters.CharFilter(
        field_name="stock_status", lookup_expr="iexact"
    )
    category = django_filters.CharFilter(
        field_name="category__name", lookup_expr="iexact"
    )
    subcategory = django_filters.CharFilter(
        field_name="subcategory__name", lookup_expr="iexact"
    )
    product_type = django_filters.CharFilter(
        field_name="product_type", lookup_expr="iexact"
    )
    asset_type = django_filters.CharFilter(
        field_name="asset_type", lookup_expr="iexact"
    )
    tracking = django_filters.CharFilter(field_name="tracking", lookup_expr="iexact")
    is_active = django_filters.BooleanFilter(field_name="is_active")
    storage_location = django_filters.NumberFilter(field_name="storage_location_id")

    class Meta:
        model = Product
        fields = [
            "status",
            "stock_status",
            "category",
            "subcategory",
            "product_type",
            "asset_type",
            "tracking",
            "is_active",
            "storage_location",
        ]


class QualityCheckFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    check_type = django_filters.CharFilter(
        field_name="check_type", lookup_expr="iexact"
    )
    result = django_filters.CharFilter(field_name="result", lookup_expr="iexact")
    priority = django_filters.CharFilter(field_name="priority", lookup_expr="iexact")
    product = django_filters.NumberFilter(field_name="product_id")
    warehouse = django_filters.NumberFilter(field_name="warehouse_id")
    office_location = django_filters.NumberFilter(field_name="office_location_id")
    team = django_filters.NumberFilter(field_name="team_id")
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    created_by = django_filters.NumberFilter(field_name="created_by_id")

    class Meta:
        model = QualityCheck
        fields = [
            "status",
            "check_type",
            "result",
            "priority",
            "product",
            "warehouse",
            "office_location",
            "team",
            "date_from",
            "date_to",
            "created_by",
        ]


class QualityAlertFilter(django_filters.FilterSet):
    severity = django_filters.CharFilter(field_name="severity", lookup_expr="iexact")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    product = django_filters.NumberFilter(field_name="product_id")
    reported_by = django_filters.NumberFilter(field_name="reported_by_id")
    office_location = django_filters.NumberFilter(field_name="office_location_id")
    assigned_to = django_filters.NumberFilter(field_name="assigned_to_id")
    created_from = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    created_to = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = QualityAlert
        fields = [
            "severity", "status", "product", "reported_by",
            "office_location", "assigned_to", "created_from", "created_to",
        ]


class QualityTeamFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter(field_name="is_active")
    leader = django_filters.NumberFilter(field_name="leader_id")
    category = django_filters.NumberFilter(field_name="category_id")

    class Meta:
        model = QualityTeam
        fields = ["is_active", "leader", "category"]


class QCTemplateFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter(field_name="is_active")
    category = django_filters.NumberFilter(field_name="category_id")

    class Meta:
        model = QCTemplate
        fields = ["is_active", "category"]
