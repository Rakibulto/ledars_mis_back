from rest_framework import serializers
from inventory.models import (
    Product,
    Item,
    ProductVariant,
    PackagingType,
    ProductTemplate,
)
from inventory.models.product import LocationStock


class ProductImageMixin:
    def get_images(self, obj):
        request = self.context.get("request")
        return obj.list_images(request=request)


class ProductReadSerializer(ProductImageMixin, serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    subcategory_name = serializers.CharField(source="subcategory.name", read_only=True)
    uom_name = serializers.CharField(source="uom.name", read_only=True)
    uom_code = serializers.CharField(source="uom.name", read_only=True)
    supplier_name = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )
    storage_location_name = serializers.CharField(
        source="storage_location.name", read_only=True
    )
    storage_location_office_name = serializers.CharField(
        source="storage_location.office.name", read_only=True
    )
    storage_location_office_type = serializers.CharField(
        source="storage_location.office.type", read_only=True
    )
    office_location_name = serializers.CharField(
        source="office_location.name", read_only=True
    )
    office_location_type = serializers.CharField(
        source="office_location.type", read_only=True
    )
    images = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "code",
            "name",
            "description",
            "product_type",
            "asset_type",
            "category",
            "category_name",
            "subcategory",
            "subcategory_name",
            "uom",
            "uom_name",
            "uom_code",
            "cost",
            "sale_price",
            "on_hand",
            "reserved",
            "available",
            "reorder_level",
            "max_stock",
            "tracking",
            "weight",
            "barcode",
            "expiry_tracking",
            "supplier",
            "supplier_name",
            "storage_location",
            "storage_location_name",
            "storage_location_office_name",
            "storage_location_office_type",
            "office_location",
            "office_location_name",
            "office_location_type",
            "location",
            "images",
            "specifications",
            "is_active",
            "status",
            "stock_status",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def get_supplier_name(self, obj):
        return obj.supplier.name if obj.supplier else None


class ProductWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "product_type",
            "asset_type",
            "category",
            "subcategory",
            "uom",
            "cost",
            "sale_price",
            "on_hand",
            "reserved",
            "reorder_level",
            "max_stock",
            "tracking",
            "weight",
            "barcode",
            "expiry_tracking",
            "supplier",
            "storage_location",
            "office_location",
            "location",
            "specifications",
            "is_active",
            "status",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        cat = attrs.get("category")
        sub = attrs.get("subcategory")
        if sub and cat and sub.parent != cat:
            raise serializers.ValidationError(
                {"subcategory": "Subcategory must belong to selected category."}
            )
        if sub and not cat:
            attrs["category"] = sub.parent
        return attrs


class ItemReadSerializer(ProductImageMixin, serializers.ModelSerializer):
    category = serializers.CharField(source="category.name", read_only=True)
    subcategory = serializers.CharField(source="subcategory.name", read_only=True)
    supplier = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )

    item_code = serializers.CharField(source="code", read_only=True)
    item_name = serializers.CharField(source="name", read_only=True)
    unit = serializers.SerializerMethodField()
    unit_price = serializers.DecimalField(
        source="cost", max_digits=12, decimal_places=2, read_only=True
    )
    old_unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    current_stock = serializers.SerializerMethodField()
    minimum_stock = serializers.IntegerField(source="reorder_level", read_only=True)
    maximum_stock = serializers.IntegerField(source="max_stock", read_only=True)
    images = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    office_location_name = serializers.CharField(
        source="office_location.name", read_only=True
    )
    office_location_type = serializers.CharField(
        source="office_location.type", read_only=True
    )

    class Meta:
        model = Item
        fields = [
            "id",
            "item_code",
            "item_name",
            "barcode",
            "product_type",
            "asset_type",
            "description",
            "category_id",
            "category",
            "subcategory_id",
            "subcategory",
            "uom_id",
            "unit",
            "unit_price",
            "old_unit_price",
            "sale_price",
            "reorder_level",
            "current_stock",
            "minimum_stock",
            "maximum_stock",
            "office_location",
            "office_location_name",
            "office_location_type",
            "location",
            "supplier_id",
            "supplier",
            "images",
            "specifications",
            "status",
            "stock_status",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def get_supplier(self, obj):
        return obj.supplier.name if obj.supplier else None

    def get_current_stock(self, obj):
        # When the viewset annotates `location_qty` (office_id filter),
        # return the per-location quantity instead of global on_hand.
        location_qty = getattr(obj, "location_qty", None)
        if location_qty is not None:
            return float(location_qty)
        return float(obj.on_hand or 0)

    def get_unit(self, obj):
        return obj.uom.name if obj.uom else ""

    def get_location(self, obj):
        if obj.office_location:
            type_label = "Warehouse" if obj.office_location.type == "warehouse" else "Office"
            return f"{obj.office_location.name} ({type_label})"
        return None


class ItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = [
            "id",
            "name",
            "description",
            "asset_type",
            "category",
            "subcategory",
            "uom",
            "cost",
            "sale_price",
            "on_hand",
            "reorder_level",
            "max_stock",
            "barcode",
            "office_location",
            "supplier",
            "specifications",
            "status",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        cat = attrs.get("category")
        sub = attrs.get("subcategory")
        if sub and cat and sub.parent != cat:
            raise serializers.ValidationError(
                {"subcategory": "Subcategory must belong to selected category."}
            )
        if sub and not cat:
            attrs["category"] = sub.parent
        return attrs


class ProductVariantReadSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    variant_name = serializers.CharField(source="name", read_only=True)
    sku = serializers.CharField(source="code", read_only=True)
    attribute_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "product",
            "product_id",
            "product_name",
            "name",
            "variant_name",
            "code",
            "sku",
            "attributes",
            "attribute_count",
            "cost_adjustment",
            "is_active",
        ]

    def get_attribute_count(self, obj):
        return len(obj.attributes or {})


class ProductVariantWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "product",
            "name",
            "code",
            "attributes",
            "cost_adjustment",
            "is_active",
        ]
        read_only_fields = ["id"]


class PackagingTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackagingType
        fields = [
            "id",
            "name",
            "code",
            "quantity",
            "weight",
            "dimensions",
            "barcode",
            "is_active",
        ]
        read_only_fields = ["id"]


class ProductTemplateSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    uom_name = serializers.CharField(source="uom.name", read_only=True)

    class Meta:
        model = ProductTemplate
        fields = "__all__"


# ─────────────────────────────────────────────────────────────────────────────
# LocationStock
# ─────────────────────────────────────────────────────────────────────────────

class LocationStockSerializer(serializers.ModelSerializer):
    """Read / write serializer for the LocationStock ledger.

    Read-only extras:
      product_name, product_code, product_on_hand,
      office_location_name, office_location_type

    Writable fields:
      product (FK id), office_location (FK id), quantity

    On create the (product, office_location) pair must be unique.
    On update only `quantity` can be changed; changing the pair is not
    allowed — delete the row and create a new one instead.
    """

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    product_uom = serializers.CharField(source="product.uom.name", read_only=True)
    product_on_hand = serializers.DecimalField(
        source="product.on_hand", max_digits=12, decimal_places=2, read_only=True
    )
    office_location_name = serializers.CharField(
        source="office_location.name", read_only=True
    )
    office_location_type = serializers.CharField(
        source="office_location.type", read_only=True
    )

    class Meta:
        model = LocationStock
        fields = [
            "id",
            "product",
            "product_name",
            "product_code",
            "product_uom",
            "product_on_hand",
            "office_location",
            "office_location_name",
            "office_location_type",
            "quantity",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def validate(self, attrs):
        product = attrs.get("product")
        office_location = attrs.get("office_location")
        instance = self.instance  # None on create

        if instance is None:
            # Creating – enforce uniqueness (the DB constraint will also catch it,
            # but we give a friendlier message here)
            if product and office_location:
                if LocationStock.objects.filter(
                    product=product, office_location=office_location
                ).exists():
                    raise serializers.ValidationError(
                        "A LocationStock entry for this product at this office/warehouse "
                        "already exists. Use PATCH to update its quantity instead."
                    )
        else:
            # Updating – disallow changing the (product, office_location) pair
            if product and product != instance.product:
                raise serializers.ValidationError(
                    {"product": "Cannot change product on an existing LocationStock row."}
                )
            if office_location and office_location != instance.office_location:
                raise serializers.ValidationError(
                    {
                        "office_location": (
                            "Cannot change office_location on an existing LocationStock row. "
                            "Delete this entry and create a new one."
                        )
                    }
                )

        if "quantity" in attrs and attrs["quantity"] < 0:
            raise serializers.ValidationError(
                {"quantity": "Quantity cannot be negative."}
            )

        return attrs
