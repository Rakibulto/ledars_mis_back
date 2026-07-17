from django.db.models import Count, Sum, Avg
from vendorportal.models.models import VendorProfile
from ..models.models import PurchaseOrder, PurchaseRequisition


def procurement_analytics():
    total_prs = PurchaseRequisition.objects.count()
    total_pos = PurchaseOrder.objects.count()
    return {
        "total_prs" : total_prs,
        "total_pos" : total_pos,
    }


def supplier_summary():
    total_suppliers = VendorProfile.objects.count()

    active_suppliers = VendorProfile.objects.filter(status='Active').count()

    aggregation = VendorProfile.objects.aggregate(
        active_contracts=Sum('active_contracts'), avg_rating=Avg('rating'), 
        )

    return {
        "total_suppliers": total_suppliers,
        "active_suppliers": active_suppliers,
        "active_contracts": aggregation['active_contracts'] or 0,
        "avg_rating": round(aggregation['avg_rating'] or 0, 2)
    }

def po_summary():
    total_pos = PurchaseOrder.objects.count()
    pending_pos = PurchaseOrder.objects.filter(approval_status='Pending Approval').count()
    approved_pos = PurchaseOrder.objects.filter(approval_status='Approved').count()
    
    return {
        "total_pos": total_pos,
        "pending_pos": pending_pos,
        "approved_pos": approved_pos,
    }


