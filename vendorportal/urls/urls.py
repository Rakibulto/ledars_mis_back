from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ..views.invitation_rfq_views import Invitation_rfqViewSet
from ..views.apply_rfq_views import (
    ApplyRFQViewSet,
    ApplyRFQAttachmentViewSet,
    ApplyRFQStatusLogViewSet,
    PriceProposalViewSet
)
from ..views.vendor_rfq_submission_views import VendorRFQSubmissionViewSet
from ..views.vendor_views import VendorProfileViewSet, VendorDocumentViewSet

router = DefaultRouter()
router.register(r'invitation_rfq', Invitation_rfqViewSet, basename='invitation_rfq')
router.register(r'apply_rfq', ApplyRFQViewSet, basename='apply_rfq')
router.register(r'apply_rfq_attachments', ApplyRFQAttachmentViewSet, basename='apply_rfq_attachments')
router.register(r'apply_rfq_status_logs', ApplyRFQStatusLogViewSet, basename='apply_rfq_status_logs')
router.register(r'price_proposals', PriceProposalViewSet, basename='price_proposals')
router.register(r'vendor-rfq-submission', VendorRFQSubmissionViewSet, basename='vendor-rfq-submission')

# Vendor Management
router.register(r'vendors', VendorProfileViewSet, basename='vendors')
router.register(r'vendor_documents', VendorDocumentViewSet, basename='vendor_documents')



urlpatterns = [
    path("", include(router.urls)),
]

