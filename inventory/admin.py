from django.contrib import admin
from .models import (
    Category,
    Product,
    UnitOfMeasure,
    ProductVariant,
    PackagingType,
    ProductTemplate,
    Warehouse,
    StorageLocation,
    PutawayRule,
    RemovalStrategy,
    OperationType,
    Route,
    ShippingMethod,
    GRN,
    GRNLineItem,
    GIN,
    GINLineItem,
    StockTransfer,
    StockTransferLine,
    StockAdjustment,
    StockAdjustmentLine,
    LotSerial,
    StockMove,
    InternalTransferSequence,
    InternalTransfer,
    InternalTransferLine,
    QualityCheck,
    QualityAlert,
    QualityControlPoint,
    QualityTeam,
    QCTemplate,
    InventoryValuation,
    LandedCost,
    ScrapRecord,
    ReturnRecord,
    ReorderRule,
    KittingBOM,
    KittingBOMLine,
    DonorFundedInventory,
    FieldDistribution,
    InventorySettings,
    Item,
    GRNSequence,
    GINSequence,
    StockTransferSequence,
    StockAdjustmentSequence,
    LossDamageClaim,
    LossDamageClaimItem,
    EmergencyReserve,
    EmergencyReserveItem,
    CommodityTracking,
    PipelineTracking,
    CustomsImportTracking,
    HumanitarianKit,
    DisposalRecord,
    VehicleDispatch,
    VehicleDispatchCargo,
    BeneficiaryDistributionList,
    BeneficiaryDistributionItem,
    Waybill,
    WaybillItem,
    FieldWarehouse,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "code", "name", "level", "parent", "item_count", "status"]
    list_filter = ["level", "status"]
    search_fields = ["name", "code"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "code",
        "name",
        "category",
        "on_hand",
        "cost",
        "status",
        "stock_status",
    ]
    list_filter = ["status", "stock_status", "product_type"]
    search_fields = ["name", "code"]


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "is_active"]


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "code", "warehouse_type", "is_active"]
    list_filter = ["warehouse_type", "is_active"]


@admin.register(StorageLocation)
class StorageLocationAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "office", "location_type"]


class GRNLineItemInline(admin.TabularInline):
    model = GRNLineItem
    extra = 0


@admin.register(GRN)
class GRNAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "grn_number",
        "supplier",
        "receive_date",
        "status",
        "total_value",
    ]
    list_filter = ["status"]
    inlines = [GRNLineItemInline]


class GINLineItemInline(admin.TabularInline):
    model = GINLineItem
    extra = 0


@admin.register(GIN)
class GINAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "gin_number",
        "issued_to",
        "issue_date",
        "status",
        "total_value",
    ]
    list_filter = ["status"]
    inlines = [GINLineItemInline]


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ["id", "transfer_number", "from_warehouse", "to_warehouse", "status"]
    list_filter = ["status"]


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ["id", "adjustment_number", "adjustment_type", "status"]
    list_filter = ["status", "adjustment_type"]


@admin.register(QualityCheck)
class QualityCheckAdmin(admin.ModelAdmin):
    list_display = ["id", "reference", "check_type", "status"]
    list_filter = ["status", "check_type"]


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = ["id", "reference", "product", "quantity", "move_type", "date"]
    list_filter = ["move_type"]


admin.site.register(ProductVariant)
admin.site.register(PackagingType)
admin.site.register(ProductTemplate)
admin.site.register(PutawayRule)
admin.site.register(RemovalStrategy)
admin.site.register(OperationType)
admin.site.register(Route)
admin.site.register(ShippingMethod)
admin.site.register(LotSerial)
admin.site.register(QualityAlert)
admin.site.register(QualityControlPoint)
admin.site.register(QualityTeam)
admin.site.register(QCTemplate)
admin.site.register(InventoryValuation)
admin.site.register(LandedCost)
admin.site.register(ScrapRecord)
admin.site.register(ReturnRecord)
admin.site.register(ReorderRule)
admin.site.register(KittingBOM)
admin.site.register(KittingBOMLine)
admin.site.register(DonorFundedInventory)
admin.site.register(FieldDistribution)
admin.site.register(InventorySettings)

# ── Newly registered models ──
admin.site.register(Item)
admin.site.register(GRNSequence)
admin.site.register(GINSequence)
admin.site.register(StockTransferSequence)
admin.site.register(InternalTransferSequence)
admin.site.register(InternalTransfer)
admin.site.register(InternalTransferLine)
admin.site.register(StockAdjustmentSequence)
admin.site.register(LossDamageClaim)
admin.site.register(LossDamageClaimItem)
admin.site.register(EmergencyReserve)
admin.site.register(EmergencyReserveItem)
admin.site.register(CommodityTracking)
admin.site.register(PipelineTracking)
admin.site.register(CustomsImportTracking)
admin.site.register(HumanitarianKit)
admin.site.register(DisposalRecord)
admin.site.register(VehicleDispatch)
admin.site.register(VehicleDispatchCargo)
admin.site.register(BeneficiaryDistributionList)
admin.site.register(BeneficiaryDistributionItem)
admin.site.register(Waybill)
admin.site.register(WaybillItem)
admin.site.register(FieldWarehouse)
