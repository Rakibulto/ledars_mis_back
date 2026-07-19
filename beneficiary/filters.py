import django_filters
from .models import (
    Beneficiary,
    ServiceRH,
    ServiceCategory,
    ServiceDelivery,
    ComplaintsFeedback,
    CaseFile,
    VulnerabilityType,
)



class BeneficiaryFilter(django_filters.FilterSet):

    project = django_filters.CharFilter(
        field_name='projects__name',
        lookup_expr='iexact'
    )
    name = django_filters.CharFilter(
        field_name="name",
        lookup_expr='icontains',
    )
    district = django_filters.CharFilter(
        field_name="district",
        lookup_expr="iexact",
    )
    upazila = django_filters.CharFilter(
        field_name="upazila",
        lookup_expr="iexact",
    )
    union = django_filters.CharFilter(
        field_name="union",
        lookup_expr="iexact",
    )
    village = django_filters.CharFilter(
        field_name="village",
        lookup_expr="iexact",
    )
    sex = django_filters.CharFilter(
        field_name="sex",
        lookup_expr="iexact",
    )
    household_type = django_filters.CharFilter(
        field_name="household_type",
        lookup_expr="iexact",
    )
    education_level = django_filters.CharFilter(
        field_name="education_level",
        lookup_expr="iexact",
    )

    class Meta:
        model = Beneficiary
        fields = [
            'project', 'name', 'district', 'upazila',
            'union', 'village', 'sex', 'household_type', 'education_level',
        ]




class ServiceRHFilter(django_filters.FilterSet):
    project = django_filters.CharFilter(
        field_name='project__name',
        lookup_expr='iexact'
    )
    name = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains"
    )
    beneficiary_code = django_filters.CharFilter(
        field_name="beneficiary__ben_code",
        lookup_expr="iexact"
    )
    beneficiary_name = django_filters.CharFilter(
        field_name="beneficiary__name",
        lookup_expr="icontains"
    )
    status = django_filters.CharFilter(
        field_name="status",
        lookup_expr="iexact"
    )
    value = django_filters.CharFilter(
        field_name="value",
        lookup_expr="iexact"
    )
    staff = django_filters.CharFilter(
        field_name="staff",
        lookup_expr="icontains"
    )
    class Meta:
        model = ServiceRH
        fields = [
            'project',
            'name',
            'beneficiary_code',
            'beneficiary_name',
            'status',
            'value',
            'staff'
        ]

class ServiceCategoryFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(
        field_name='status',
        lookup_expr='iexact'
    )
    class Meta:
        model = ServiceCategory
        fields = [
            'status'
        ]


class VulnerabilityTypeFilter(django_filters.FilterSet):
    status = django_filters.BooleanFilter(field_name="status")

    class Meta:
        model = VulnerabilityType
        fields = ["status"]


class ServiceDeliveryFilter(django_filters.FilterSet):
    beneficiary_id = django_filters.CharFilter(
        field_name='beneficiary__id',
        lookup_expr='iexact'
    )
    beneficiary_code = django_filters.CharFilter(
        field_name="beneficiary__ben_code",
        lookup_expr="iexact"
    )
    beneficiary_name = django_filters.CharFilter(
        field_name="beneficiary__name",
        lookup_expr="icontains"
    )
    service_type = django_filters.CharFilter(
        field_name="service_type",
        lookup_expr="icontains"
    )
    status = django_filters.CharFilter(
        field_name="status",
        lookup_expr="iexact"
    )
    category = django_filters.CharFilter(
        field_name="category__name",
        lookup_expr="iexact"
    )
    location = django_filters.CharFilter(
        field_name="location",
        lookup_expr="icontains"
    )
    class Meta:
        model = ServiceDelivery
        fields = [
            'beneficiary_id',
            'beneficiary_code',
            'beneficiary_name',
            'service_type',
            'status',
            'category',
            'location'
        ]

class CaseFileFilter(django_filters.FilterSet):
    beneficiary_id = django_filters.CharFilter(
        field_name='beneficiary__id',
        lookup_expr='iexact'
    )
    beneficiary_code = django_filters.CharFilter(
        field_name="beneficiary__ben_code",
        lookup_expr="iexact"
    )
    beneficiary_name = django_filters.CharFilter(
        field_name="beneficiary__name",
        lookup_expr="icontains"
    )
    case_type = django_filters.CharFilter(
        field_name="case_type",
        lookup_expr="iexact"
    )
    priority = django_filters.CharFilter(
        field_name="priority",
        lookup_expr="iexact"
    )
    case_worker = django_filters.CharFilter(
        field_name="case_worker__employee_name",
        lookup_expr="iexact"
    )
    next_follow_up = django_filters.CharFilter(
        field_name="next_follow_up",
        lookup_expr="iexact"
    )
    class Meta:
        model = CaseFile
        fields = [
            'status'
        ]



class ComplaintsFeedbackFilter(django_filters.FilterSet):
    beneficiary_id = django_filters.CharFilter(
        field_name='beneficiary__id',
        lookup_expr='iexact'
    )
    beneficiary_code = django_filters.CharFilter(
        field_name="beneficiary__ben_code",
        lookup_expr="iexact"
    )
    beneficiary_name = django_filters.CharFilter(
        field_name="beneficiary__name",
        lookup_expr="icontains"
    )
    type = django_filters.CharFilter(
        field_name="type",
        lookup_expr="iexact"
    )
    category = django_filters.CharFilter(
        field_name="category",
        lookup_expr="iexact"
    )
    subject = django_filters.CharFilter(
        field_name="subject",
        lookup_expr="icontains"
    )
    status =django_filters.CharFilter(
        field_name="status",
        lookup_expr="iexact"
    )
    priority = django_filters.CharFilter(
        field_name="priority",
        lookup_expr="iexact"
    )
    satisfaction = django_filters.CharFilter(
        field_name="satisfaction",
        lookup_expr="iexact"
    )
    class Meta:
        model = ComplaintsFeedback
        fields = [
            'beneficiary_id', 'beneficiary_code', 'beneficiary_name',
            'type', 'category', 'subject', 'status', 'priority', 'satisfaction',

        ]
