from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.db import transaction

from .models import Category, Product
from .models.product import LocationStock


def recalculate_category_counts(subcategory):
    if not subcategory:
        return
    sub_count = Product.objects.filter(subcategory=subcategory).count()
    Category.objects.filter(id=subcategory.id).update(item_count=sub_count)
    main_category = subcategory.parent
    if main_category:
        main_count = Product.objects.filter(subcategory__parent=main_category).count()
        Category.objects.filter(id=main_category.id).update(item_count=main_count)


@receiver(post_save, sender=Product)
def product_created_or_updated(sender, instance, created, **kwargs):
    with transaction.atomic():
        if instance.subcategory:
            recalculate_category_counts(instance.subcategory)


@receiver(post_delete, sender=Product)
def product_deleted(sender, instance, **kwargs):
    with transaction.atomic():
        if instance.subcategory:
            recalculate_category_counts(instance.subcategory)


# ─────────────────────────────────────────────────────────────
#  LocationStock signal
#  Whenever a LocationStock row is saved or deleted, recalculate
#  Product.on_hand = SUM(LocationStock.quantity) for that product.
#  This keeps on_hand correct without ever touching Item records
#  directly during internal transfers.
# ─────────────────────────────────────────────────────────────

def _sync_product_on_hand(product_id):
    """Recalculate and persist Product.on_hand from LocationStock rows."""
    total = (
        LocationStock.objects.filter(product_id=product_id)
        .aggregate(total=Coalesce(Sum("quantity"), Decimal("0")))
        ["total"]
    )

    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return

    new_on_hand = total
    new_available = max(Decimal("0"), new_on_hand - product.reserved)

    if new_on_hand <= 0:
        new_status = "Out of Stock"
    elif product.reorder_level and new_on_hand <= product.reorder_level:
        new_status = "Low Stock"
    elif product.max_stock and new_on_hand > product.max_stock:
        new_status = "Overstock"
    else:
        new_status = "In Stock"

    # Use .update() to avoid triggering Product.post_save again
    Product.objects.filter(pk=product_id).update(
        on_hand=new_on_hand,
        available=new_available,
        stock_status=new_status,
    )


@receiver(post_save, sender=LocationStock)
def location_stock_saved(sender, instance, **kwargs):
    _sync_product_on_hand(instance.product_id)


@receiver(post_delete, sender=LocationStock)
def location_stock_deleted(sender, instance, **kwargs):
    _sync_product_on_hand(instance.product_id)
