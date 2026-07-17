import json

from django.db.models import OuterRef, Subquery, DecimalField

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend
from paginations import Pagination
from inventory.models import Product, Item, ProductVariant, PackagingType, ProductTemplate
from inventory.models.product import LocationStock
from inventory.serializers import (
    ProductReadSerializer,
    ProductWriteSerializer,
    ItemReadSerializer,
    ItemWriteSerializer,
    ProductVariantReadSerializer,
    ProductVariantWriteSerializer,
    PackagingTypeSerializer,
    ProductTemplateSerializer,
    LocationStockSerializer,
)
from inventory.filters import ProductFilter
from .core import CreatedByMixin


class ProductViewSet(CreatedByMixin, ModelViewSet):
    permission_classes = [AllowAny]
    pagination_class = Pagination
    queryset = Product.objects.select_related(
        "category", "subcategory", "uom", "supplier", "created_by", "office_location"
    ).all()
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_class = ProductFilter
    search_fields = ["name", "code", "category__name", "subcategory__name", "barcode"]
    ordering_fields = ["name", "code", "on_hand", "cost", "created_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return ProductReadSerializer
        return ProductWriteSerializer

    def create(self, request, *args, **kwargs):
        write_serializer = self.get_serializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        self.perform_create(write_serializer)
        instance = write_serializer.instance
        read_serializer = ProductReadSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write_serializer = self.get_serializer(instance, data=request.data, partial=partial)
        write_serializer.is_valid(raise_exception=True)
        self.perform_update(write_serializer)
        read_serializer = ProductReadSerializer(write_serializer.instance, context=self.get_serializer_context())
        return Response(read_serializer.data)

    def _get_product_read_data(self, product):
        serializer = ProductReadSerializer(product, context=self.get_serializer_context())
        return serializer.data

    def _get_requested_filenames(self, request):
        if hasattr(request.data, "getlist"):
            filenames = request.data.getlist("filenames")
            if filenames:
                return [str(name) for name in filenames if name]

        filenames = request.data.get("filenames", [])

        if isinstance(filenames, str):
            try:
                filenames = json.loads(filenames)
            except json.JSONDecodeError:
                filenames = [filenames]

        return [str(name) for name in filenames if name]

    @action(
        detail=True,
        methods=["get", "post", "delete"],
        url_path="images",
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def images(self, request, pk=None):
        product = self.get_object()

        if request.method == "GET":
            return Response({"images": product.list_images(request=request)})

        if request.method == "POST":
            uploaded_files = request.FILES.getlist("images")

            if not uploaded_files:
                return Response(
                    {"detail": "No images were provided."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            invalid_files = [
                uploaded_file.name
                for uploaded_file in uploaded_files
                if not (uploaded_file.content_type or "").startswith("image/")
            ]

            if invalid_files:
                return Response(
                    {
                        "detail": "Only image files are allowed.",
                        "files": invalid_files,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            for uploaded_file in uploaded_files:
                product.store_image(uploaded_file)

            return Response(
                self._get_product_read_data(product),
                status=status.HTTP_201_CREATED,
            )

        filenames = self._get_requested_filenames(request)

        if not filenames:
            return Response(
                {"detail": "No image names were provided for deletion."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product.delete_images(filenames)
        return Response(self._get_product_read_data(product))


class ItemViewSet(CreatedByMixin, ModelViewSet):
    permission_classes = [AllowAny]
    pagination_class = Pagination
    queryset = Item.objects.select_related(
        "category", "subcategory", "uom", "supplier", "created_by", "office_location"
    ).all()
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_class = ProductFilter
    search_fields = ["name", "code", "category__name", "subcategory__name"]
    ordering_fields = ["name", "code", "on_hand", "cost", "created_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return ItemReadSerializer
        return ItemWriteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        office_id = self.request.query_params.get("office_id")
        if office_id:
            # ── LocationStock-based filter ────────────────────────────────
            # Return only products that have a LocationStock row with
            # quantity > 0 at the requested office.  Also annotate the
            # queryset with `location_qty` so the serializer (and therefore
            # the form's `current_stock`) reflects the real per-location
            # stock rather than the global on_hand.
            ls_subquery = (
                LocationStock.objects
                .filter(product=OuterRef("pk"), office_location_id=office_id)
                .values("quantity")[:1]
            )
            # Only include products that have stock at this specific office
            product_ids = LocationStock.objects.filter(
                office_location_id=office_id, quantity__gt=0
            ).values_list("product_id", flat=True)
            qs = qs.filter(pk__in=product_ids).annotate(
                location_qty=Subquery(
                    ls_subquery,
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
        return qs

    def create(self, request, *args, **kwargs):
        write_serializer = self.get_serializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        self.perform_create(write_serializer)
        instance = write_serializer.instance
        read_serializer = ItemReadSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write_serializer = self.get_serializer(instance, data=request.data, partial=partial)
        write_serializer.is_valid(raise_exception=True)
        self.perform_update(write_serializer)
        read_serializer = ItemReadSerializer(write_serializer.instance, context=self.get_serializer_context())
        return Response(read_serializer.data)


class ProductVariantViewSet(ModelViewSet):
    queryset = ProductVariant.objects.select_related("product").order_by("-id")
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ["name", "code", "product__name"]
    filterset_fields = ["product", "is_active"]
    ordering_fields = ["id", "name", "code", "cost_adjustment"]
    ordering = ["-id"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return ProductVariantReadSerializer
        return ProductVariantWriteSerializer


class PackagingTypeViewSet(ModelViewSet):
    queryset = PackagingType.objects.order_by("-id")
    serializer_class = PackagingTypeSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ["name", "code", "barcode", "dimensions"]
    filterset_fields = ["is_active"]
    ordering_fields = ["id", "name", "code", "quantity", "weight"]
    ordering = ["-id"]


class ProductTemplateViewSet(ModelViewSet):
    queryset = ProductTemplate.objects.select_related("category", "uom").order_by("-id")
    serializer_class = ProductTemplateSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ["name", "description", "category__name", "uom__name", "tracking"]
    filterset_fields = ["category", "uom", "tracking", "expiry_tracking", "is_active"]
    ordering_fields = ["id", "name", "default_cost", "default_reorder", "default_max"]
    ordering = ["-id"]


# ─────────────────────────────────────────────────────────────────────────────
# LocationStock ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class LocationStockViewSet(ModelViewSet):
    """
    Full CRUD API for the LocationStock ledger.

    Endpoints:
      GET    /api/store-inventory/location-stocks/          – list (paginated)
      POST   /api/store-inventory/location-stocks/          – create new row
      GET    /api/store-inventory/location-stocks/{id}/     – retrieve
      PATCH  /api/store-inventory/location-stocks/{id}/     – update quantity
      DELETE /api/store-inventory/location-stocks/{id}/     – delete row

    Query params:
      search          – matches product name, product code, office name
      product         – filter by product id
      office_location – filter by office_location id
      has_stock       – 'true' → quantity > 0 only
      ordering        – quantity, -quantity, product__name, -product__name,
                        office_location__name, -office_location__name, updated_at
    """

    serializer_class = LocationStockSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "product__name",
        "product__code",
        "office_location__name",
    ]
    filterset_fields = ["product", "office_location"]
    ordering_fields = ["quantity", "product__name", "office_location__name", "updated_at"]
    ordering = ["-updated_at"]

    def get_queryset(self):
        qs = (
            LocationStock.objects
            .select_related("product", "product__uom", "office_location")
            .all()
        )
        has_stock = self.request.query_params.get("has_stock")
        if has_stock is not None and has_stock.lower() in ("true", "1", "yes"):
            qs = qs.filter(quantity__gt=0)
        return qs
