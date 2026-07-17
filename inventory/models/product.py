from pathlib import Path
from uuid import uuid4

from django.core.files.storage import default_storage
from django.db import models
from django.utils.text import slugify
from authentication.models import User
from .core import Category, UnitOfMeasure

PRODUCT_IMAGE_STORAGE_PREFIX = "inventory/products"


class Product(models.Model):
    STATUS_CHOICES = (
        ("Active", "Active"),
        ("Inactive", "Inactive"),
    )

    STOCK_STATUS_CHOICES = (
        ("In Stock", "In Stock"),
        ("Low Stock", "Low Stock"),
        ("Out of Stock", "Out of Stock"),
        ("Overstock", "Overstock"),
    )

    TRACKING_CHOICES = (
        ("none", "No Tracking"),
        ("lot", "By Lots"),
        ("serial", "By Serial Number"),
    )

    PRODUCT_TYPE_CHOICES = (
        ("storable", "Storable Product"),
        ("consumable", "Consumable"),
        ("service", "Service"),
    )

    ASSET_TYPE_CHOICES = (
        ("Fixed Asset", "Fixed Asset"),
        ("Consumable Asset", "Consumable Asset"),
    )

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    product_type = models.CharField(
        max_length=20, choices=PRODUCT_TYPE_CHOICES, default="storable"
    )
    asset_type = models.CharField(
        max_length=20, choices=ASSET_TYPE_CHOICES, default="Fixed Asset"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        limit_choices_to={"level": "Main"},
    )
    subcategory = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_products",
        limit_choices_to={"level": "Sub"},
    )
    uom = models.ForeignKey(
        UnitOfMeasure, on_delete=models.SET_NULL, null=True, blank=True
    )

    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    old_unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    on_hand = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reserved = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    available = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    tracking = models.CharField(max_length=10, choices=TRACKING_CHOICES, default="none")
    weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    barcode = models.CharField(max_length=100, null=True, blank=True, unique=True)
    expiry_tracking = models.BooleanField(default=False)

    supplier = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    storage_location = models.ForeignKey(
        "inventory.StorageLocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    office_location = models.ForeignKey(
        "procurement.OfficeManagement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    location = models.CharField(max_length=200, null=True, blank=True)
    specifications = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="Active")
    stock_status = models.CharField(
        max_length=15, choices=STOCK_STATUS_CHOICES, default="In Stock"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_products",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_image_storage_path(self):
        return f"{PRODUCT_IMAGE_STORAGE_PREFIX}/{self.pk}"

    def list_images(self, request=None):
        if not self.pk:
            return []

        image_directory = self.get_image_storage_path()

        try:
            _, image_names = default_storage.listdir(image_directory)
        except OSError:
            return []

        images = []

        for image_name in sorted(image_names):
            relative_path = f"{image_directory}/{image_name}"
            image_url = default_storage.url(relative_path)

            if request is not None:
                image_url = request.build_absolute_uri(image_url)

            images.append(
                {
                    "id": image_name,
                    "name": image_name,
                    "url": image_url,
                }
            )

        return images

    def store_image(self, uploaded_file):
        if not self.pk:
            raise ValueError("Product must be saved before storing images.")

        original_name = Path(uploaded_file.name)
        safe_stem = slugify(original_name.stem) or "product-image"
        extension = original_name.suffix.lower()
        file_name = f"{safe_stem}-{uuid4().hex[:12]}{extension}"
        stored_path = default_storage.save(
            f"{self.get_image_storage_path()}/{file_name}", uploaded_file
        )

        return Path(stored_path).name

    def delete_images(self, filenames=None):
        if not self.pk:
            return

        image_names = filenames or [image["id"] for image in self.list_images()]

        for image_name in image_names:
            default_storage.delete(f"{self.get_image_storage_path()}/{image_name}")

    def save(self, *args, **kwargs):
        if not self.code:
            last = Product.objects.order_by("-id").first()
            num = (last.id + 1) if last else 1
            self.code = f"PRD-{num:04d}"

        # Capture old_unit_price before cost changes
        if self.pk:
            try:
                old = Product.objects.get(pk=self.pk)
                if old.cost != self.cost:
                    self.old_unit_price = old.cost
            except Product.DoesNotExist:
                pass

        self.available = self.on_hand - self.reserved
        if self.on_hand <= 0:
            self.stock_status = "Out of Stock"
        elif self.reorder_level and self.on_hand <= self.reorder_level:
            self.stock_status = "Low Stock"
        elif self.max_stock and self.on_hand > self.max_stock:
            self.stock_status = "Overstock"
        else:
            self.stock_status = "In Stock"
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.delete_images()
        return super().delete(*args, **kwargs)

    class Meta:
        db_table = "inventory_item"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Item(Product):
    class Meta:
        proxy = True
        verbose_name = "Item"
        verbose_name_plural = "Items"

    @property
    def item_code(self):
        return self.code

    @property
    def item_name(self):
        return self.name

    @property
    def unit(self):
        return self.uom.name if self.uom else ""

    @property
    def unit_price(self):
        return self.cost

    @property
    def current_stock(self):
        return int(self.on_hand)

    @property
    def minimum_stock(self):
        return int(self.reorder_level)

    @property
    def maximum_stock(self):
        return int(self.max_stock)

    @property
    def reorder_quantity(self):
        return (
            int(self.max_stock - self.on_hand) if self.max_stock > self.on_hand else 0
        )


class LocationStock(models.Model):
    """
    Per-location stock ledger.
    Each record holds the quantity of a single Product at a single
    OfficeManagement location.  Product.on_hand is always the SUM of
    all LocationStock rows for that product — kept in sync by a signal.

    Rules:
    - Never modify Product records directly for internal transfers.
    - Never create duplicate Product records during a transfer.
    - All stock movements go through LocationStock rows only.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="location_stocks",
    )
    office_location = models.ForeignKey(
        "procurement.OfficeManagement",
        on_delete=models.CASCADE,
        related_name="location_stocks",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("product", "office_location")]
        verbose_name = "Location Stock"
        verbose_name_plural = "Location Stocks"

    def __str__(self):
        return f"{self.product} @ {self.office_location}: {self.quantity}"


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    attributes = models.JSONField(default=dict, blank=True)
    cost_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class PackagingType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    quantity = models.PositiveIntegerField(default=1)
    weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    dimensions = models.CharField(max_length=100, null=True, blank=True)
    barcode = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ProductTemplate(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True
    )
    uom = models.ForeignKey(
        UnitOfMeasure, on_delete=models.SET_NULL, null=True, blank=True
    )
    tracking = models.CharField(
        max_length=10, choices=Product.TRACKING_CHOICES, default="none"
    )
    expiry_tracking = models.BooleanField(default=False)
    default_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    default_reorder = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    default_max = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name