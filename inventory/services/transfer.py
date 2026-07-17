"""
inventory.services.transfer
===========================
Production-ready service layer for internal stock transfers.

Rules enforced here:
- Stock lives ONLY in LocationStock(product, office_location, quantity).
- Product records are NEVER created or duplicated during a transfer.
- Product.on_hand is DERIVED — it is recalculated by the LocationStock
  post_save / post_delete signal automatically.
- All mutations are wrapped in a single atomic transaction.
"""

from decimal import Decimal

from django.db import transaction


def _get_or_seed_location_stock(product, location):
    """
    Return a select_for_update() LocationStock row for (product, location).

    Lazy-backfill / self-healing logic:
    - If a row already exists with sufficient data, return it (locked).
    - If the row exists but product.on_hand > row.quantity AND
      product.office_location == location, it means the row is stale from
      the old pre-LocationStock era — update it to match product.on_hand.
    - If no row exists AND product.office_location == location AND
      product.on_hand > 0, create the row from product.on_hand.
    - Return None if no valid stock record can be established.
    """
    from inventory.models.product import LocationStock
    from django.db.models import Sum
    from django.db.models.functions import Coalesce

    # Try to find the existing row
    try:
        ls = LocationStock.objects.select_for_update().get(
            product=product,
            office_location=location,
        )
        # Self-heal: if the row exists but product.on_hand doesn't match the
        # sum of all LocationStock rows, this row may be stale.  Recalculate
        # the row quantity from (product.on_hand - stock_at_other_locations).
        ls_sum = (
            LocationStock.objects.filter(product=product)
            .aggregate(total=Coalesce(Sum("quantity"), Decimal("0")))
            ["total"]
        )
        if product.on_hand > ls_sum:
            # There's unaccounted stock — add the difference to this row
            delta = product.on_hand - ls_sum
            ls.quantity += delta
            ls.save(update_fields=["quantity", "updated_at"])
            # Re-fetch locked
            ls = LocationStock.objects.select_for_update().get(
                product=product,
                office_location=location,
            )
        return ls
    except LocationStock.DoesNotExist:
        pass

    # Lazy-backfill: seed from Product.on_hand when office matches
    if (
        product.office_location_id is not None
        and product.office_location_id == location.pk
        and product.on_hand > 0
    ):
        LocationStock.objects.get_or_create(
            product=product,
            office_location=location,
            defaults={"quantity": product.on_hand},
        )
        # Re-fetch with lock after creation
        return LocationStock.objects.select_for_update().get(
            product=product,
            office_location=location,
        )

    return None


def transfer_stock(source_location, destination_location, product, quantity):
    """
    Atomically move *quantity* of *product* from *source_location* to
    *destination_location* by adjusting LocationStock records only.

    Args:
        source_location  : procurement.OfficeManagement instance (source)
        destination_location : procurement.OfficeManagement instance (dest)
        product          : inventory.models.product.Product instance
        quantity         : numeric — units to move (must be > 0)

    Returns:
        (source_ls, dest_ls)  — the updated LocationStock instances.

    Raises:
        ValueError: quantity ≤ 0, insufficient source stock, or missing source record.
    """
    from inventory.models.product import LocationStock

    qty = Decimal(str(quantity))

    if qty <= 0:
        raise ValueError("Transfer quantity must be positive.")

    if source_location == destination_location:
        raise ValueError("Source and destination locations must differ.")

    with transaction.atomic():
        # ── 1. Fetch & lock source row (lazy-backfill if needed) ──────────
        source_ls = _get_or_seed_location_stock(product, source_location)
        if source_ls is None:
            raise ValueError(
                f"No stock record for '{product.name}' at "
                f"'{source_location.name}'. Cannot deduct."
            )

        # ── 2. Validate available quantity ────────────────────────────────
        if source_ls.quantity < qty:
            raise ValueError(
                f"Insufficient stock for '{product.name}': "
                f"requested {qty}, available {source_ls.quantity} "
                f"at '{source_location.name}'."
            )

        # ── 3. Deduct from source ─────────────────────────────────────────
        source_ls.quantity -= qty
        source_ls.save(update_fields=["quantity", "updated_at"])
        # Signal fires → Product.on_hand recalculated automatically.

        # ── 4. Add to destination (get-or-create, never a new Product) ────
        dest_qs = LocationStock.objects.filter(
            product=product,
            office_location=destination_location,
        )
        if dest_qs.exists():
            dest_ls = LocationStock.objects.select_for_update().get(
                product=product,
                office_location=destination_location,
            )
            dest_ls.quantity += qty
            dest_ls.save(update_fields=["quantity", "updated_at"])
        else:
            dest_ls = LocationStock.objects.create(
                product=product,
                office_location=destination_location,
                quantity=qty,
            )
        # Signal fires → Product.on_hand recalculated automatically.

        return source_ls, dest_ls


def deduct_location_stock(location, product, quantity):
    """
    Deduct *quantity* from a LocationStock row (e.g. Draft → In Transit).
    If no LocationStock row exists yet but the product's on_hand is positive
    and its office_location matches *location*, the row is seeded automatically
    (lazy backfill for products created before the LocationStock system).

    Raises:
        ValueError: insufficient stock or no stock record.
    """
    from inventory.models.product import LocationStock

    qty = Decimal(str(quantity))

    if qty <= 0:
        raise ValueError("Deduct quantity must be positive.")

    with transaction.atomic():
        ls = _get_or_seed_location_stock(product, location)
        if ls is None:
            raise ValueError(
                f"No stock record for '{product.name}' at "
                f"'{location.name}'. Cannot deduct."
            )

        if ls.quantity < qty:
            raise ValueError(
                f"Insufficient stock for '{product.name}': "
                f"requested {qty}, available {ls.quantity} at '{location.name}'."
            )

        ls.quantity -= qty
        ls.save(update_fields=["quantity", "updated_at"])
        return ls


def restore_location_stock(location, product, quantity):
    """
    Return *quantity* back to a LocationStock row (cancellation / reversal).
    Creates the row if it no longer exists (e.g. was zeroed out and cleaned up).
    """
    from inventory.models.product import LocationStock

    qty = Decimal(str(quantity))

    if qty <= 0:
        raise ValueError("Restore quantity must be positive.")

    with transaction.atomic():
        ls, _ = LocationStock.objects.get_or_create(
            product=product,
            office_location=location,
            defaults={"quantity": Decimal("0")},
        )
        ls.quantity += qty
        ls.save(update_fields=["quantity", "updated_at"])
        return ls


def add_location_stock(location, product, quantity):
    """
    Add *quantity* to a destination LocationStock row (In Transit → Received).
    Creates the row if it does not exist.
    """
    from inventory.models.product import LocationStock

    qty = Decimal(str(quantity))

    if qty <= 0:
        raise ValueError("Add quantity must be positive.")

    with transaction.atomic():
        dest_ls, created = LocationStock.objects.get_or_create(
            product=product,
            office_location=location,
            defaults={"quantity": Decimal("0")},
        )
        if not created:
            dest_ls = LocationStock.objects.select_for_update().get(
                product=product,
                office_location=location,
            )
        dest_ls.quantity += qty
        dest_ls.save(update_fields=["quantity", "updated_at"])
        return dest_ls
