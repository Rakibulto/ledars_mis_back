from inventory.models import GIN, GRN, StockTransfer, StockMove
from procurement.models.grn_models import GoodsReceiptNote


def get_stock_move_direction(stock_move):
    if stock_move.move_type in {"Receipt", "Return"}:
        return "In"

    if stock_move.move_type in {"Delivery", "Scrap"}:
        return "Out"

    if stock_move.move_type == "Transfer":
        return "Internal"

    if stock_move.move_type == "Adjustment":
        source_location = (stock_move.source_location or "").strip().lower()
        destination_location = (stock_move.destination_location or "").strip().lower()

        if source_location == "adjustment increase":
            return "In"

        if destination_location == "adjustment decrease":
            return "Out"

    if stock_move.move_type == "Status Change":
        return "Status"

    return stock_move.move_type


def get_stock_move_history_status(stock_move):
    direction = get_stock_move_direction(stock_move)

    if direction == "In":
        return "Stock_in"

    if direction == "Out":
        return "Stock_out"

    if direction == "Internal":
        return "Stock_transfer"

    if direction == "Status":
        return "Status_change"

    return stock_move.move_type or "Unknown"


def build_stock_move_document_cache(instances):
    if isinstance(instances, StockMove):
        instances = [instances]
    elif instances is None:
        instances = []

    delivery_references = {
        stock_move.reference
        for stock_move in instances
        if isinstance(stock_move, StockMove)
        and stock_move.move_type == "Delivery"
        and stock_move.reference
    }
    receipt_references = {
        stock_move.reference
        for stock_move in instances
        if isinstance(stock_move, StockMove)
        and stock_move.move_type == "Receipt"
        and stock_move.reference
    }
    transfer_references = {
        stock_move.reference
        for stock_move in instances
        if isinstance(stock_move, StockMove)
        and stock_move.move_type == "Transfer"
        and stock_move.reference
    }

    document_cache = {}

    for gin in GIN.objects.filter(gin_number__in=delivery_references).only("id", "gin_number"):
        document_cache[("Delivery", gin.gin_number)] = {
            "type": "gin",
            "id": gin.id,
        }

    for grn in GoodsReceiptNote.objects.filter(grn_number__in=receipt_references).only(
        "id", "grn_number"
    ):
        document_cache[("Receipt", grn.grn_number)] = {
            "type": "procurement_grn",
            "id": grn.id,
        }

    for grn in GRN.objects.filter(grn_number__in=receipt_references).only("id", "grn_number"):
        document_cache.setdefault(("Receipt", grn.grn_number), {
            "type": "grn",
            "id": grn.id,
        })

    for transfer in StockTransfer.objects.filter(transfer_number__in=transfer_references).only(
        "id", "transfer_number"
    ):
        document_cache[("Transfer", transfer.transfer_number)] = {
            "type": "stock_transfer",
            "id": transfer.id,
        }

    return document_cache


def resolve_stock_move_document(stock_move, document_cache):
    if not stock_move or not stock_move.reference:
        return None

    return document_cache.get((stock_move.move_type, stock_move.reference))