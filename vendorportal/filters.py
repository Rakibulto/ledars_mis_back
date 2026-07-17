import django_filters
from .models.models import VendorBlacklist, VendorEnlistment, VendorDocument, VendorProfile
from procurement.models.vendor_models import (
    VendorCategory,
    VendorCategoryMapping,
    VendorEvaluation,
    VendorOnboarding,
    VendorVerification,
    VendorPerformance,
)


class SupplierVendorFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    verification_state = django_filters.CharFilter(
        field_name="verification_state", lookup_expr="iexact"
    )
    category = django_filters.CharFilter(
        field_name="categories__name", lookup_expr="icontains"
    )
    
    registration_date_from = django_filters.DateFilter(
        field_name="registration_date", lookup_expr="gte"
    )
    registration_date_to = django_filters.DateFilter(
        field_name="registration_date", lookup_expr="lte"
    )

    class Meta:
        model = VendorProfile
        fields = ["status", "verification_state", "category"]


class VendorCategoryFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter(field_name="is_active")

    class Meta:
        model = VendorCategory
        fields = ["is_active"]


class VendorCategoryMappingFilter(django_filters.FilterSet):
    supplier = django_filters.NumberFilter(field_name="supplier__id")
    category = django_filters.NumberFilter(field_name="category__id")
    category_name = django_filters.CharFilter(
        field_name="category__name", lookup_expr="icontains"
    )

    class Meta:
        model = VendorCategoryMapping
        fields = ["supplier", "category"]


class VendorEvaluationFilter(django_filters.FilterSet):
    supplier = django_filters.NumberFilter(field_name="supplier__id")
    evaluation_date_from = django_filters.DateFilter(
        field_name="evaluation_date", lookup_expr="gte"
    )
    evaluation_date_to = django_filters.DateFilter(
        field_name="evaluation_date", lookup_expr="lte"
    )
    min_rating = django_filters.NumberFilter(
        field_name="overall_rating", lookup_expr="gte"
    )

    class Meta:
        model = VendorEvaluation
        fields = ["supplier"]


class VendorOnboardingFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    supplier = django_filters.NumberFilter(field_name="supplier__id")

    class Meta:
        model = VendorOnboarding
        fields = ["status", "supplier"]


class VendorVerificationFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    supplier = django_filters.NumberFilter(field_name="supplier__id")
    documents_verified = django_filters.BooleanFilter(field_name="documents_verified")

    class Meta:
        model = VendorVerification
        fields = ["status", "supplier", "documents_verified"]


class VendorPerformanceFilter(django_filters.FilterSet):
    supplier = django_filters.NumberFilter(field_name="supplier__id")
    period_month = django_filters.NumberFilter(field_name="period_month")
    period_year = django_filters.NumberFilter(field_name="period_year")

    class Meta:
        model = VendorPerformance
        fields = ["supplier", "period_month", "period_year"]


class VendorBlacklistFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    category = django_filters.CharFilter(field_name="category", lookup_expr="iexact")
    supplier = django_filters.NumberFilter(field_name="supplier__id")
    blacklisted_date_from = django_filters.DateFilter(
        field_name="blacklisted_date", lookup_expr="gte"
    )
    blacklisted_date_to = django_filters.DateFilter(
        field_name="blacklisted_date", lookup_expr="lte"
    )

    class Meta:
        model = VendorBlacklist
        fields = ["status", "category", "supplier"]


class VendorEnlistmentFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    category = django_filters.CharFilter(
        field_name="category", lookup_expr="icontains"
    )
    submitted_date_from = django_filters.DateFilter(
        field_name="submitted_date", lookup_expr="gte"
    )
    submitted_date_to = django_filters.DateFilter(
        field_name="submitted_date", lookup_expr="lte"
    )

    class Meta:
        model = VendorEnlistment
        fields = ["status", "category"]


class VendorDocumentFilter(django_filters.FilterSet):
    supplier = django_filters.NumberFilter(field_name="vendor__id")
    doc_type = django_filters.CharFilter(field_name="doc_type", lookup_expr="iexact")
    review_status = django_filters.CharFilter(
        field_name="review_status", lookup_expr="iexact"
    )

    class Meta:
        model = VendorDocument
        fields = ["supplier", "doc_type", "review_status"]
