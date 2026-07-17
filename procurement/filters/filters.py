
import django_filters
from vendorportal.models.models import VendorProfile
from ..models.models import PurchaseOrder, PurchaseRequisition, ItemPR, ItemPO



class SupplierFilter(django_filters.FilterSet):

    category = django_filters.CharFilter(
        field_name='categories__name',
        lookup_expr='iexact'   
    )


    status = django_filters.CharFilter(
        field_name="status", 
        lookup_expr="iexact",
        # lookup_expr='icontains',
    )

    rating = django_filters.CharFilter(
        field_name="rating", 
        lookup_expr="iexact",
        # lookup_expr='icontains',
    )

    class Meta:
        model = VendorProfile
        fields = ['category', 'status', 'rating']


class PurchaseOrderFilter(django_filters.FilterSet):

    supplier = django_filters.CharFilter(
        field_name='supplier__name',
        lookup_expr='iexact'
    )

    delivery_date = django_filters.CharFilter(
        field_name='delivery_date',
        lookup_expr='iexact'
    )
    
    approval_status = django_filters.CharFilter(
        field_name='approval_status',
        lookup_expr='iexact'
    )


    class Meta:
        model = PurchaseOrder
        fields = [
            'supplier',
            'delivery_date',
            'approval_status',
        ]



class ItemPOFilter(django_filters.FilterSet):
    po_number = django_filters.CharFilter(
        field_name='purchase_order__po_number',
        lookup_expr='exact'
    )

    class Meta:
        model = ItemPO
        fields = ['po_number']


class PurchaseRequisitionFilter(django_filters.FilterSet):

    department = django_filters.CharFilter(
        field_name='department__name',  # FK field lookup
        lookup_expr='iexact'
    )

    project = django_filters.CharFilter(
        field_name='project__name',  # FK field lookup
        lookup_expr='iexact'
    )

    items = django_filters.CharFilter(
        field_name='items__item_name',  # ManyToMany related field
        lookup_expr='iexact'
    )

    status = django_filters.CharFilter(
        field_name='status', 
        lookup_expr='iexact'
    )

    approver = django_filters.CharFilter(
        field_name='approver__employee_name',  # FK field
        lookup_expr='iexact'
    )

    created_by = django_filters.CharFilter(
        field_name='created_by__employee_name',  # FK field
        lookup_expr='iexact'
    )

    pr_number = django_filters.CharFilter(
        field_name='pr_number', 
        lookup_expr='iexact'
    )

    class Meta:
        model = PurchaseRequisition
        fields = ['department', 'project', 'items', 'status', 'approver', 'created_by', 'pr_number']
        


class ItemPRFilter(django_filters.FilterSet):
    pr_number = django_filters.CharFilter(
        field_name='purchase_requisition__pr_number',  # FK lookup
        lookup_expr='iexact'
    )

    item_name = django_filters.CharFilter(
        field_name='item__item_name',  # FK lookup
        lookup_expr='iexact'
    )

    class Meta:
        model = ItemPR
        fields = ['pr_number', 'item_name']



        
       
       