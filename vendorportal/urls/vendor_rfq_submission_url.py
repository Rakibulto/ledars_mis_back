from django.urls import path, include
from rest_framework.routers import DefaultRouter

from views.vendor_rfq_submission_views import VendorRFQSubmissionViewSet

router = DefaultRouter()
router.register(
    r"vendor-rfq-submission",
    VendorRFQSubmissionViewSet,
    basename="vendor-rfq-submission",
)

urlpatterns = [
    path("api/", include(router.urls)),
]

# ─────────────────────────────────────────────────────────────────────────────
# Generated endpoints
# ─────────────────────────────────────────────────────────────────────────────
#
#   POST   /api/vendor-rfq-submission/                          create
#   GET    /api/vendor-rfq-submission/                          list  (+ ?status=draft&vendor_id=1)
#   GET    /api/vendor-rfq-submission/{id}/                     retrieve
#   PUT    /api/vendor-rfq-submission/{id}/                     full update
#   PATCH  /api/vendor-rfq-submission/{id}/                     partial update
#   DELETE /api/vendor-rfq-submission/{id}/                     delete submission
#   DELETE /api/vendor-rfq-submission/{id}/documents/{doc_id}/  delete one document