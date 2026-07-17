from django.urls import path, include
from rest_framework.routers import DefaultRouter
from inventory.views import (
    CategoryViewSet,
    ItemViewSet,
    ItemSummaryAPIView,
    DashboardKPIView,
    InventoryDashboardOverviewView,
    InventoryOfficeItemCountView,
    OfficeStockDetailView,
    InventoryLogAnalyticsView,
    InventoryLogHistoryView,
    InventoryLogListView,
    ABCAnalysisView,
    ForecastedStockView,
    StockAgingView,
    InventoryDashboardOverviewView,
    UnitOfMeasureViewSet,
    ProductViewSet,
    ProductVariantViewSet,
    PackagingTypeViewSet,
    ProductTemplateViewSet,
    LocationStockViewSet,
    WarehouseViewSet,
    StorageLocationViewSet,
    PutawayRuleViewSet,
    RemovalStrategyViewSet,
    OperationTypeViewSet,
    RouteViewSet,
    ShippingMethodViewSet,
    GRNViewSet,
    BackorderViewSet,
    GINViewSet,
    DropshippingViewSet,
    BatchTransferViewSet,
    CrossDockingViewSet,
    StockTransferViewSet,
    StockAdjustmentViewSet,
    CycleCountViewSet,
    LotSerialViewSet,
    StockMoveViewSet,
    InternalTransferViewSet,
    StockInBatchView,
    QualityCheckViewSet,
    QualityAlertViewSet,
    QualityControlPointViewSet,
    QualityTeamViewSet,
    QCTemplateViewSet,
    InventoryValuationViewSet,
    LandedCostViewSet,
    ScrapRecordViewSet,
    ReturnRecordViewSet,
    ReorderRuleViewSet,
    ReplenishmentViewSet,
    KittingBOMViewSet,
    DonorFundedInventoryViewSet,
    FieldDistributionViewSet,
    LossDamageClaimViewSet,
    EmergencyReserveViewSet,
    CommodityTrackingViewSet,
    PipelineTrackingViewSet,
    CustomsImportTrackingViewSet,
    HumanitarianKitViewSet,
    DisposalRecordViewSet,
    VehicleDispatchViewSet,
    BeneficiaryDistributionListViewSet,
    WaybillViewSet,
    FieldWarehouseViewSet,
    InventorySettingsViewSet,
)

router = DefaultRouter()

# Core
router.register("categories", CategoryViewSet, basename="category")
router.register("items", ItemViewSet, basename="item")
router.register("products", ProductViewSet, basename="product")
router.register("uom", UnitOfMeasureViewSet, basename="uom")
router.register("location-stocks", LocationStockViewSet, basename="location-stock")

# Product extras
router.register("product-variants", ProductVariantViewSet,
                basename="product-variant")
router.register("packaging-types", PackagingTypeViewSet,
                basename="packaging-type")
router.register(
    "product-templates", ProductTemplateViewSet, basename="product-template"
)

# Warehouse
router.register("warehouses", WarehouseViewSet, basename="warehouse")
router.register(
    "storage-locations", StorageLocationViewSet, basename="storage-location"
)
router.register("putaway-rules", PutawayRuleViewSet, basename="putaway-rule")
router.register(
    "removal-strategies", RemovalStrategyViewSet, basename="removal-strategy"
)
router.register("operation-types", OperationTypeViewSet,
                basename="operation-type")
router.register("routes", RouteViewSet, basename="route")
router.register("shipping-methods", ShippingMethodViewSet,
                basename="shipping-method")

# Operations
router.register("inventory-grn", GRNViewSet, basename="inventory-grn")
router.register("backorders", BackorderViewSet, basename="backorder")
router.register("gin", GINViewSet, basename="gin")
router.register("dropshipping", DropshippingViewSet, basename="dropshipping")
router.register("batch-transfers", BatchTransferViewSet,
                basename="batch-transfer")
router.register("cross-docking", CrossDockingViewSet, basename="cross-docking")
router.register("stock-transfers", StockTransferViewSet,
                basename="stock-transfer")
router.register("internal-transfers", InternalTransferViewSet,
                basename="internal-transfer")
router.register(
    "stock-adjustments", StockAdjustmentViewSet, basename="stock-adjustment"
)
router.register("cycle-counts", CycleCountViewSet, basename="cycle-count")
router.register("stock-moves", StockMoveViewSet, basename="stock-move")
router.register("lot-serials", LotSerialViewSet, basename="lot-serial")

# Quality
router.register("quality-checks", QualityCheckViewSet,
                basename="quality-check")
router.register("quality-alerts", QualityAlertViewSet,
                basename="quality-alert")
router.register(
    "quality-control-points",
    QualityControlPointViewSet,
    basename="quality-control-point",
)
router.register("quality-teams", QualityTeamViewSet, basename="quality-team")
router.register("qc-templates", QCTemplateViewSet, basename="qc-template")

# Valuation
router.register(
    "inventory-valuations", InventoryValuationViewSet, basename="inventory-valuation"
)
router.register("landed-costs", LandedCostViewSet, basename="landed-cost")

# Scrap & Returns
router.register("scrap-records", ScrapRecordViewSet, basename="scrap-record")
router.register("return-records", ReturnRecordViewSet,
                basename="return-record")

# Reorder & BOM
router.register("reorder-rules", ReorderRuleViewSet, basename="reorder-rule")
router.register("replenishments", ReplenishmentViewSet,
                basename="replenishment")
router.register("kitting-bom", KittingBOMViewSet, basename="kitting-bom")

# NGO
router.register(
    "donor-funded-inventory",
    DonorFundedInventoryViewSet,
    basename="donor-funded-inventory",
)
router.register(
    "field-distributions", FieldDistributionViewSet, basename="field-distribution"
)
router.register(
    "loss-damage-claims", LossDamageClaimViewSet, basename="loss-damage-claim"
)
router.register(
    "emergency-reserves", EmergencyReserveViewSet, basename="emergency-reserve"
)
router.register(
    "commodity-tracking", CommodityTrackingViewSet, basename="commodity-tracking"
)
router.register(
    "pipeline-tracking", PipelineTrackingViewSet, basename="pipeline-tracking"
)
router.register(
    "customs-import-tracking",
    CustomsImportTrackingViewSet,
    basename="customs-import-tracking",
)
router.register(
    "humanitarian-kits", HumanitarianKitViewSet, basename="humanitarian-kit"
)
router.register("disposal-records", DisposalRecordViewSet,
                basename="disposal-record")
router.register(
    "vehicle-dispatches", VehicleDispatchViewSet, basename="vehicle-dispatch"
)
router.register(
    "beneficiary-distribution-lists",
    BeneficiaryDistributionListViewSet,
    basename="beneficiary-distribution-list",
)
router.register("waybills", WaybillViewSet, basename="waybill")
router.register("field-warehouses", FieldWarehouseViewSet,
                basename="field-warehouse")

# Settings
router.register(
    "inventory-settings", InventorySettingsViewSet, basename="inventory-setting"
)

urlpatterns = [
    path("", include(router.urls)),
    path('stock-in/', StockInBatchView.as_view(), name='stock-in-batch'),
    path("item_summary/", ItemSummaryAPIView.as_view()),
    path("dashboard-kpi/", DashboardKPIView.as_view()),
    path("inventory-dashboard/overview/",
         InventoryDashboardOverviewView.as_view()),
    path("inventory-dashboard/office-item-counts/",
         InventoryOfficeItemCountView.as_view()),
    path("inventory-dashboard/office-stock-detail/",
         OfficeStockDetailView.as_view()),
    path("inventory-log/", InventoryLogListView.as_view()),
    path("inventory-log/analytics/", InventoryLogAnalyticsView.as_view()),
    path("inventory-log/history/", InventoryLogHistoryView.as_view()),
    path("abc-analysis/", ABCAnalysisView.as_view()),
    path("forecasted-stock/", ForecastedStockView.as_view()),
    path("stock-aging/", StockAgingView.as_view()),
]
