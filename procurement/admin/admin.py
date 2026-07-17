from django.contrib import admin
from vendorportal.models.models import VendorProfile
from ..models.direct_purchase_models import (
    Shop,
    DirectPurchase,
    DirectPurchaseItem,
    DirectPurchaseStatusLog,
)
from ..models.models import (
    POSequence,
    PurchaseOrder,
    ItemPO,
    PRSequence,
    PurchaseRequisition,
    ItemPR,
    ApprovalRequest,
    ApprovalHistory,
)
from ..models.requisition_models import (
    MRSequence,
    MaterialRequisition,
    MaterialItem,
    MaterialRequisitionApprovalStep,
)
from ..models.office_models import OfficeManagement
from ..models.rfq_models import RFQ, RFQLineItem
from ..models.account_models import AccountSequence, Account
from ..models.budget_models import BudgetSequence, Budget
from ..models.quotation_models import (
    QuotationSequence,
    VendorQuotation,
    QuotationItem,
    QuotationOpening,
)
from ..models.comparative_models import (
    CSSequence,
    ComparativeStatement,
    ComparativeLineItem,
    ComparativeApprovalWorkflow,
    ComparativeNote,
    ComparativeVendorEvaluation,
    ComparativeVendorFinancial,
)
from ..models.award_models import AwardSequence, Award, AwardNotification
from ..models.work_order_models import (
    WOSequence,
    WorkOrder,
    WorkOrderItem,
    VendorAcceptance,
)
from ..models.grn_models import GRNSequence, GoodsReceiptNote, GRNItem, GRNVerification
from ..models.payment_requisition_models import (
    PRFSequence,
    PaymentRequisition,
    PaymentRequisitionItem,
)
from ..models.treasury_models import (
    TreasurySequence,
    TreasuryProcessing,
    PaymentRecord,
    PaymentTimeline,
)
from ..models.vendor_models import (
    VendorCategory,
    VendorCategoryMapping,
    VendorEvaluation,
    VendorOnboarding,
    VendorVerification,
    VendorPerformance,
)
from ..models.notification_models import ProcurementNotification
from ..models.settings_models import (
    ApprovalMatrix,
    EmailTemplate,
    ProcurementRole,
    ProcurementUserRole,
    NotificationSetting,
)


# ── Core ────────────────────────────────────────────────
@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "status", "rating", "created_at"]
    list_filter = ["status", "rating"]
    search_fields = ["name", "code"]


class ItemPOInline(admin.TabularInline):
    model = ItemPO
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        "po_number",
        "supplier",
        "approval_status",
        "total_amount",
        "created_at",
    ]
    list_filter = ["approval_status"]
    search_fields = ["po_number", "supplier__name"]
    inlines = [ItemPOInline]


class ItemPRInline(admin.TabularInline):
    model = ItemPR
    extra = 0


@admin.register(PurchaseRequisition)
class PurchaseRequisitionAdmin(admin.ModelAdmin):
    list_display = ["pr_number", "department", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["pr_number"]
    inlines = [ItemPRInline]


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ["reference_number", "type", "status", "priority", "created_at"]
    list_filter = ["type", "status", "priority"]
    search_fields = ["reference_number"]


@admin.register(ApprovalHistory)
class ApprovalHistoryAdmin(admin.ModelAdmin):
    list_display = ["approval_request", "action", "approver", "role", "created_at"]
    list_filter = ["action"]


# ── Requisitions ────────────────────────────────────────
@admin.register(OfficeManagement)
class OfficeManagementAdmin(admin.ModelAdmin):
    list_display = ["office_id", "name", "district", "division", "status"]
    list_filter = ["district", "division", "status"]
    search_fields = ["name", "code", "office_id"]


class MaterialItemInline(admin.TabularInline):
    model = MaterialItem
    extra = 0


class MaterialRequisitionApprovalStepInline(admin.TabularInline):
    model = MaterialRequisitionApprovalStep
    extra = 0
    readonly_fields = [
        "approval_level",
        "approver",
        "status",
        "comments",
        "acted_at",
        "acted_by",
        "created_at",
    ]
    can_delete = False
    verbose_name = "Approval Step"
    verbose_name_plural = "Approval Steps"


@admin.register(MaterialRequisition)
class MaterialRequisitionAdmin(admin.ModelAdmin):
    list_display = [
        "requisition_no",
        "department",
        "status",
        "priority",
        "total_amount",
        "created_at",
    ]
    list_filter = ["status", "priority"]
    search_fields = ["requisition_no"]
    inlines = [MaterialItemInline, MaterialRequisitionApprovalStepInline]


# ── RFQ ─────────────────────────────────────────────────
class RFQLineItemInline(admin.TabularInline):
    model = RFQLineItem
    extra = 0


@admin.register(RFQ)
class RFQAdmin(admin.ModelAdmin):
    list_display = ["rfq_number", "status", "submission_deadline", "created_at"]
    list_filter = ["status"]
    search_fields = ["rfq_number"]
    inlines = [RFQLineItemInline]


# ── Accounts & Budgets ──────────────────────────────────
@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "created_at"]
    search_fields = ["code", "name"]


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "allocated_amount", "created_at"]
    search_fields = ["code", "name"]


# ── Quotations ──────────────────────────────────────────
class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 0


@admin.register(VendorQuotation)
class VendorQuotationAdmin(admin.ModelAdmin):
    list_display = [
        "quotation_number",
        "rfq",
        "vendor",
        "status",
        "grand_total",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["quotation_number", "vendor__name"]
    inlines = [QuotationItemInline]


@admin.register(QuotationOpening)
class QuotationOpeningAdmin(admin.ModelAdmin):
    list_display = ["rfq", "opening_date", "opened_by"]


# ── Comparative Statements ──────────────────────────────
class ComparativeLineItemInline(admin.TabularInline):
    model = ComparativeLineItem
    extra = 0


@admin.register(ComparativeStatement)
class ComparativeStatementAdmin(admin.ModelAdmin):
    list_display = ["cs_number", "rfq", "status", "recommended_vendor", "created_at"]
    list_filter = ["status"]
    search_fields = ["cs_number", "rfq__rfq_number", "title"]
    inlines = [ComparativeLineItemInline]


# ── Awards ──────────────────────────────────────────────
@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    list_display = [
        "award_number",
        "vendor_profile",
        "status",
        "total_amount",
        "award_date",
    ]
    list_filter = ["status"]
    search_fields = ["award_number", "vendor_profile__name"]


@admin.register(AwardNotification)
class AwardNotificationAdmin(admin.ModelAdmin):
    list_display = [
        "award",
        "notification_type",
        "vendor_profile",
        "is_sent",
        "is_acknowledged",
    ]
    list_filter = ["notification_type", "is_sent", "is_acknowledged"]


# ── Work Orders ─────────────────────────────────────────
class WorkOrderItemInline(admin.TabularInline):
    model = WorkOrderItem
    extra = 0


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ["wo_number", "award", "status", "total_amount", "delivery_date"]
    list_filter = ["status"]
    search_fields = ["wo_number"]
    inlines = [WorkOrderItemInline]


@admin.register(VendorAcceptance)
class VendorAcceptanceAdmin(admin.ModelAdmin):
    list_display = ["work_order", "status", "response_date"]
    list_filter = ["status"]


# ── GRN ─────────────────────────────────────────────────
class GRNItemInline(admin.TabularInline):
    model = GRNItem
    extra = 0


@admin.register(GoodsReceiptNote)
class GoodsReceiptNoteAdmin(admin.ModelAdmin):
    list_display = ["grn_number", "work_order", "supplier", "status", "receipt_date"]
    list_filter = ["status"]
    search_fields = ["grn_number", "supplier__name"]
    inlines = [GRNItemInline]


@admin.register(GRNVerification)
class GRNVerificationAdmin(admin.ModelAdmin):
    list_display = ["grn", "verified_by", "inspection_date", "status"]
    list_filter = ["status"]


# ── Payment Requisitions ────────────────────────────────
class PaymentRequisitionItemInline(admin.TabularInline):
    model = PaymentRequisitionItem
    extra = 0


@admin.register(PaymentRequisition)
class PaymentRequisitionAdmin(admin.ModelAdmin):
    list_display = [
        "prf_number",
        "supplier",
        "status",
        "priority",
        "total_amount",
        "created_at",
    ]
    list_filter = ["status", "priority"]
    search_fields = ["prf_number", "supplier__name"]
    inlines = [PaymentRequisitionItemInline]


# ── Treasury ────────────────────────────────────────────
@admin.register(TreasuryProcessing)
class TreasuryProcessingAdmin(admin.ModelAdmin):
    list_display = [
        "processing_number",
        "payment_requisition",
        "status",
        "approved_amount",
    ]
    list_filter = ["status"]
    search_fields = ["processing_number"]


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = [
        "reference_number",
        "supplier",
        "payment_method",
        "amount",
        "status",
        "payment_date",
    ]
    list_filter = ["payment_method", "status"]
    search_fields = ["reference_number", "supplier__name"]


@admin.register(PaymentTimeline)
class PaymentTimelineAdmin(admin.ModelAdmin):
    list_display = ["payment_requisition", "stage", "timestamp"]
    list_filter = ["stage"]


# ── Vendor Management ──────────────────────────────────
@admin.register(VendorCategory)
class VendorCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]


@admin.register(VendorCategoryMapping)
class VendorCategoryMappingAdmin(admin.ModelAdmin):
    list_display = ["supplier", "category"]


@admin.register(VendorEvaluation)
class VendorEvaluationAdmin(admin.ModelAdmin):
    list_display = ["supplier", "overall_rating", "evaluation_date", "evaluated_by"]
    list_filter = ["evaluation_date"]


@admin.register(VendorOnboarding)
class VendorOnboardingAdmin(admin.ModelAdmin):
    list_display = ["supplier", "status", "created_at"]
    list_filter = ["status"]


@admin.register(VendorVerification)
class VendorVerificationAdmin(admin.ModelAdmin):
    list_display = ["supplier", "status", "verification_date", "verified_by"]
    list_filter = ["status"]


@admin.register(VendorPerformance)
class VendorPerformanceAdmin(admin.ModelAdmin):
    list_display = [
        "supplier",
        "period_year",
        "period_month",
        "total_orders",
        "total_spent",
    ]
    list_filter = ["period_year"]


# ── Notifications ───────────────────────────────────────
@admin.register(ProcurementNotification)
class ProcurementNotificationAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "recipient",
        "notification_type",
        "priority",
        "is_read",
        "created_at",
    ]
    list_filter = ["notification_type", "priority", "is_read"]
    search_fields = ["title"]


# ── Settings ────────────────────────────────────────────
@admin.register(ApprovalMatrix)
class ApprovalMatrixAdmin(admin.ModelAdmin):
    list_display = [
        "module",
        "approval_level",
        "approver_role",
        "approval_mode",
        "is_active",
    ]
    list_filter = ["module", "approval_mode", "is_active"]


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "module", "is_active"]
    list_filter = ["module", "is_active"]


@admin.register(ProcurementRole)
class ProcurementRoleAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]


@admin.register(ProcurementUserRole)
class ProcurementUserRoleAdmin(admin.ModelAdmin):
    list_display = ["user", "role"]


@admin.register(NotificationSetting)
class NotificationSettingAdmin(admin.ModelAdmin):
    list_display = [
        "module",
        "event_name",
        "email_enabled",
        "in_app_enabled",
        "is_active",
    ]
    list_filter = ["module", "is_active"]


# ── Sequence Models ──
admin.site.register(POSequence)
admin.site.register(PRSequence)
admin.site.register(MRSequence)
admin.site.register(AccountSequence)
admin.site.register(BudgetSequence)
admin.site.register(QuotationSequence)
admin.site.register(CSSequence)
admin.site.register(AwardSequence)
admin.site.register(WOSequence)
admin.site.register(GRNSequence)
admin.site.register(PRFSequence)
admin.site.register(TreasurySequence)

# ── Line Item Models ──
admin.site.register(ItemPO)
admin.site.register(ItemPR)
admin.site.register(MaterialItem)
admin.site.register(QuotationItem)
admin.site.register(ComparativeLineItem)
admin.site.register(WorkOrderItem)
admin.site.register(GRNItem)
admin.site.register(PaymentRequisitionItem)


# ── Direct Purchase ───────────────────────────────────────────────────────────
class DirectPurchaseItemInline(admin.TabularInline):
    model = DirectPurchaseItem
    extra = 0


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "email", "created_at"]
    search_fields = ["name", "phone", "email"]


@admin.register(DirectPurchase)
class DirectPurchaseAdmin(admin.ModelAdmin):
    list_display = [
        "dp_number",
        "shop",
        "department",
        "status",
        "priority",
        "total_amount",
        "purchase_date",
        "created_at",
    ]
    list_filter = ["status", "priority"]
    search_fields = ["dp_number", "shop__name", "contact_person"]
    inlines = [DirectPurchaseItemInline]


admin.site.register(DirectPurchaseStatusLog)
