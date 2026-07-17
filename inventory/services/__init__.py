from inventory.models import Product, Category


def item_summary():
    return {
        "total_items": Product.objects.count(),
        "total_active_items": Product.objects.filter(status="Active").count(),
        "total_low_stock_items": Product.objects.filter(stock_status="Low Stock").count(),
        "total_categories": Category.objects.filter(level="Main").count(),
    }
