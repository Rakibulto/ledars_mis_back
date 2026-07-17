from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Existing views
from ..views.account_views import AccountViewSet, AccountCategoryViewSet
from ..views.budget_views import BudgetViewSet
from ..views.rfq_views import (
    RFQViewSet,
    RFQVendorInvitationViewSet,
    RFQAttachmentViewSet,
)
from ..views.requisition_views import (
    MaterialRequisitionViewSet,
    MaterialItemViewSet,
    DonorCodeViewSet,
)
from ..views.views import (
    SupplierViewSet,
    PurchaseOrderViewSet,
    ItemPRViewSet,
    ItemPOViewSet,
    PurchaseRequisitionViewSet,
    SuppliersSummaryAPIView,
    ProcurementAnalyticsAPIView,
    ApprovalRequestViewSet,
    ApprovalHistoryViewSet,
    PurchaseRequisitionSummaryAPIView,
    POSummaryAPIView,
)

# New views
from ..views.quotation_views import (
    VendorQuotationViewSet,
    QuotationItemViewSet,
    QuotationOpeningViewSet,
)
from ..views.rfq_views import RFQLineItemViewSet
from ..views.comparative_views import (
    ComparativeStatementViewSet,
    ComparativeLineItemViewSet,
    ComparativeApprovalWorkflowViewSet,
    ComparativeNoteViewSet,
    ComparativeVendorEvaluationViewSet,
    ComparativeVendorFinancialViewSet,
)
from ..views.award_views import AwardViewSet, AwardNotificationViewSet
from ..views.work_order_views import (
    WorkOrderViewSet,
    WorkOrderItemViewSet,
    WorkOrderApprovalHistoryViewSet,
    WorkOrderNotificationLogViewSet,
    WorkOrderAttachmentViewSet,
    VendorAcceptanceViewSet,
)
from ..views.grn_views import (
    GoodsReceiptNoteViewSet,
    GRNItemViewSet,
    GRNVerificationViewSet,
)
from ..views.payment_requisition_views import (
    PaymentRequisitionViewSet,
    PaymentRequisitionItemViewSet,
)
from ..views.treasury_views import (
    TreasuryProcessingViewSet,
    PaymentRecordViewSet,
    PaymentTimelineViewSet,
)
from ..views.vendor_views import (
    VendorCategoryViewSet,
    VendorCategoryMappingViewSet,
    VendorEvaluationViewSet,
    VendorOnboardingViewSet,
    VendorVerificationViewSet,
    VendorPerformanceViewSet,
)
from ..views.notification_views import ProcurementNotificationViewSet
from ..views.settings_views import (
    AproverUserViewSet,
    ApprovalMatrixViewSet,
    EmailTemplateViewSet,
    ProcurementRoleViewSet,
    ProcurementUserRoleViewSet,
    NotificationSettingViewSet,
    SimpleUserViewSet,
    UserManagementViewSet,
)
from ..views.dashboard_views import ProcurementDashboardAPIView
from ..views.report_views import (
    RequisitionReportAPIView,
    RFQReportAPIView,
    VendorParticipationReportAPIView,
    VendorAwardReportAPIView,
    WorkOrderReportAPIView,
    InventoryReceivedReportAPIView,
    PaymentStatusReportAPIView,
    BudgetUtilizationReportAPIView,
)
from ..views.office_views import (
    OfficeManagementViewSet,
    OfficeStaffViewSet,
    WarehouseViewSet,
)


from ..views.fiscal_year_views import FiscalYearViewSet, AccountingPeriodViewSet
from ..views.currency_views import CurrencyViewSet, ExchangeRateViewSet
from ..views.direct_purchase_views import DirectPurchaseViewSet, ShopViewSet

router = DefaultRouter()


# ── Core procurement ──
router.register("supplier", SupplierViewSet, basename="supplier")
router.register("item_po", ItemPOViewSet, basename="item_po")
router.register("purchase_order", PurchaseOrderViewSet, basename="purchase_order")
router.register("item_pr", ItemPRViewSet, basename="item_purchase_requisition")
router.register(
    "purchase_requisition", PurchaseRequisitionViewSet, basename="purchase_requisition"
)
router.register("approval_request", ApprovalRequestViewSet, basename="approval_request")
router.register("approval_history", ApprovalHistoryViewSet, basename="approval_history")
router.register(r"budgets", BudgetViewSet, basename="budgets")
router.register(r"accounts", AccountViewSet, basename="accounts")
router.register(r"acc-categories", AccountCategoryViewSet, basename="categories")

# ── Direct Purchases ──
router.register(r"direct-purchases", DirectPurchaseViewSet, basename="direct-purchases")
router.register(r"shops", ShopViewSet, basename="shops")

# ── Requisitions ──
router.register(r"donor-codes", DonorCodeViewSet, basename="donor-codes")
router.register(
    r"material_requisitions",
    MaterialRequisitionViewSet,
    basename="material_requisitions",
)
router.register(r"material_items", MaterialItemViewSet, basename="material_items")

# ── RFQ ──
router.register(r"rfq", RFQViewSet, basename="rfq")
router.register(
    r"rfq_invitation", RFQVendorInvitationViewSet, basename="rfq_invitation"
)
router.register(r"rfq_attachments", RFQAttachmentViewSet, basename="rfq_attachments")
router.register(r"rfq_line_items", RFQLineItemViewSet, basename="rfq_line_items")

# ── Quotations ──
router.register(r"quotations", VendorQuotationViewSet, basename="quotations")
router.register(r"quotation-items", QuotationItemViewSet, basename="quotation-items")
router.register(
    r"quotation-openings", QuotationOpeningViewSet, basename="quotation-openings"
)

# ── Comparative Statements ──
router.register(
    r"comparative_statements",
    ComparativeStatementViewSet,
    basename="comparative_statements",
)
router.register(
    r"comparative_line_items",
    ComparativeLineItemViewSet,
    basename="comparative_line_items",
)
router.register(
    r"comparative_approval_workflow",
    ComparativeApprovalWorkflowViewSet,
    basename="comparative_approval_workflow",
)
router.register(
    r"comparative-notes",
    ComparativeNoteViewSet,
    basename="comparative-notes",
)
router.register(
    r"comparative-vendor-evaluations",
    ComparativeVendorEvaluationViewSet,
    basename="comparative-vendor-evaluations",
)
router.register(
    r"comparative-vendor-financials",
    ComparativeVendorFinancialViewSet,
    basename="comparative-vendor-financials",
)

# ── Awards ──
router.register(r"awards", AwardViewSet, basename="awards")
router.register(
    r"award-notifications", AwardNotificationViewSet, basename="award-notifications"
)


# ── Work Orders ──
router.register(r"work-orders", WorkOrderViewSet, basename="work-orders")
router.register(r"work-order-items", WorkOrderItemViewSet, basename="work-order-items")
router.register(
    r"work-order-approvals",
    WorkOrderApprovalHistoryViewSet,
    basename="work-order-approvals",
)
router.register(
    r"work-order-notifications",
    WorkOrderNotificationLogViewSet,
    basename="work-order-notifications",
)
router.register(
    r"work-order-attachments",
    WorkOrderAttachmentViewSet,
    basename="work-order-attachments",
)
router.register(
    r"vendor-acceptances", VendorAcceptanceViewSet, basename="vendor-acceptances"
)

# ── GRN ──
router.register(r"grn", GoodsReceiptNoteViewSet, basename="grn")
router.register(r"grn-items", GRNItemViewSet, basename="grn-items")
router.register(
    r"grn-verifications", GRNVerificationViewSet, basename="grn-verifications"
)

# ── Payment Requisitions ──
router.register(
    r"payment-requisitions", PaymentRequisitionViewSet, basename="payment-requisitions"
)
router.register(
    r"payment-requisition-items",
    PaymentRequisitionItemViewSet,
    basename="payment-requisition-items",
)

# ── Treasury ──
router.register(r"treasury", TreasuryProcessingViewSet, basename="treasury")
router.register(r"payment-records", PaymentRecordViewSet, basename="payment-records")
router.register(
    r"payment-timelines", PaymentTimelineViewSet, basename="payment-timelines"
)

# ── Vendor Management ──
router.register(
    r"vendor-categories", VendorCategoryViewSet, basename="vendor-categories"
)
router.register(
    r"vendor-category-mappings",
    VendorCategoryMappingViewSet,
    basename="vendor-category-mappings",
)
router.register(
    r"vendor-evaluations", VendorEvaluationViewSet, basename="vendor-evaluations"
)
router.register(
    r"vendor-onboardings", VendorOnboardingViewSet, basename="vendor-onboardings"
)
router.register(
    r"vendor-verifications", VendorVerificationViewSet, basename="vendor-verifications"
)
router.register(
    r"vendor-performance", VendorPerformanceViewSet, basename="vendor-performance"
)

# ── Notifications ──
router.register(
    r"procurement-notifications",
    ProcurementNotificationViewSet,
    basename="procurement-notifications",
)

# ── Settings ──
router.register(r"approval-matrix", ApprovalMatrixViewSet, basename="approval-matrix")
router.register(r"email-templates", EmailTemplateViewSet, basename="email-templates")
router.register(
    r"procurement-roles", ProcurementRoleViewSet, basename="procurement-roles"
)
router.register(
    r"procurement-user-roles",
    ProcurementUserRoleViewSet,
    basename="procurement-user-roles",
)
router.register(
    r"notification-settings",
    NotificationSettingViewSet,
    basename="notification-settings",
)
router.register(
    r"user-management",
    UserManagementViewSet,
    basename="user-management",
)
router.register(r"simple-user", SimpleUserViewSet, basename="simple-user")
router.register(r"aprover_user", AproverUserViewSet, basename="aprover-user")

# ── Fiscal Year ──
router.register(r"fiscal-year", FiscalYearViewSet, basename="fiscal-year")
router.register(
    r"accounting-periods", AccountingPeriodViewSet, basename="accounting-period"
)

# ── Currency ──
router.register(r"currencies", CurrencyViewSet, basename="currency")
router.register(r"exchange-rates", ExchangeRateViewSet, basename="exchange-rate")


# ── Office Management ──
router.register(
    r"office_management", OfficeManagementViewSet, basename="office_management"
)
router.register(r"office_staff", OfficeStaffViewSet, basename="office_staff")
router.register(r"warehouse", WarehouseViewSet, basename="warehouse")


urlpatterns = [
    path("", include(router.urls)),
    # Legacy summary endpoints
    path("pr_summary/", PurchaseRequisitionSummaryAPIView.as_view(), name="pr_summary"),
    path("supplier_summary/", SuppliersSummaryAPIView.as_view()),
    path("procurement_analytics/", ProcurementAnalyticsAPIView.as_view()),
    path("po_summary/", POSummaryAPIView.as_view()),
    # Dashboard
    path(
        "pro_dashboard/",
        ProcurementDashboardAPIView.as_view(),
        name="procurement-dashboard",
    ),
    # Reports
    path(
        "reports/requisitions/",
        RequisitionReportAPIView.as_view(),
        name="report-requisitions",
    ),
    path("reports/rfq/", RFQReportAPIView.as_view(), name="report-rfq"),
    path(
        "reports/vendor-participation/",
        VendorParticipationReportAPIView.as_view(),
        name="report-vendor-participation",
    ),
    path(
        "reports/vendor-awards/",
        VendorAwardReportAPIView.as_view(),
        name="report-vendor-awards",
    ),
    path(
        "reports/work-orders/",
        WorkOrderReportAPIView.as_view(),
        name="report-work-orders",
    ),
    path(
        "reports/inventory-received/",
        InventoryReceivedReportAPIView.as_view(),
        name="report-inventory-received",
    ),
    path(
        "reports/payment-status/",
        PaymentStatusReportAPIView.as_view(),
        name="report-payment-status",
    ),
    path(
        "reports/budget-utilization/",
        BudgetUtilizationReportAPIView.as_view(),
        name="report-budget-utilization",
    ),
]
