from django.db import transaction
from rest_framework import serializers

from inventory.models import Item
from procurement.models.requisition_models import MaterialItem, MaterialRequisition
from ..models.rfq_models import (
    RFQ,
    RFQAttachment,
    RFQLineItem,
    RFQVendorInvitation,
)
from vendorportal.models.models import VendorProfile
from vendorportal.serializers.vendor_serializers import SimpleVendorProfileSerializer, VendorUserSerializer


class RFQAttachmentSerializer(serializers.ModelSerializer):
    rfq_number = serializers.CharField(source="rfq.rfq_number", read_only=True)
    rfq_id = serializers.PrimaryKeyRelatedField(source="rfq", queryset=RFQ.objects.all(), write_only=True, required=True)
    created_by = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = RFQAttachment
        fields = [
            "id",
            "rfq_id",
            "rfq_number",
            "files",
            "file_url",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "rfq_number", "file_url", "created_by", "created_at", "updated_at"]

    def get_created_by(self, obj):
        if obj.created_by:
            return obj.created_by.username or obj.created_by.email
        return None

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.files and request:
            return request.build_absolute_uri(obj.files.url)
        return None


class RFQInvitedVendorSerializer(serializers.ModelSerializer):
    vendor = SimpleVendorProfileSerializer(read_only=True)

    class Meta:
        model = RFQVendorInvitation
        fields = [
            "id",
            "vendor",
            "invite_status",
            "submitted_status",
            "email_status",
            "invited_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "vendor",
            "invite_status",
            "submitted_status",
            "email_status",
            "invited_at",
            "updated_at",
        ]


class RFQVendorInvitationSerializer(serializers.ModelSerializer):
    vendor = SimpleVendorProfileSerializer(read_only=True)
    rfq_number = serializers.CharField(source="rfq.rfq_number", read_only=True)
    rfq_title = serializers.CharField(source="rfq.rfq_title", read_only=True)
    rfq_status = serializers.CharField(source="rfq.status", read_only=True)
    rfq_category = serializers.SerializerMethodField()
    rfq_deadline = serializers.DateTimeField(source="rfq.submission_deadline", read_only=True)
    vendor_id = serializers.PrimaryKeyRelatedField(
        queryset=VendorProfile.objects.all(),
        source="vendor",
        write_only=True,
        required=False,
        allow_null=True,
    )
    rfq_id = serializers.PrimaryKeyRelatedField(
        queryset=RFQ.objects.all(),
        source="rfq",
        write_only=True,
        required=True,
    )
    submitted_status = serializers.BooleanField(required=False)

    class Meta:
        model = RFQVendorInvitation
        fields = [
            "id",
            "rfq_id",
            "rfq_number",
            "rfq_title",
            "rfq_status",
            "rfq_category",
            "rfq_deadline",
            "vendor",
            "vendor_id",
            "invite_status",
            "submitted_status",
            "email_status",
            "invited_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "rfq_number",
            "rfq_title",
            "rfq_status",
            "rfq_category",
            "rfq_deadline",
            "vendor",
            "invited_at",
            "updated_at",
        ]

    def get_rfq_category(self, obj):
        if obj.rfq and obj.rfq.rfq_category:
            return obj.rfq.rfq_category.name
        return None


class RFQInvitedVendorSummaryVendorSerializer(serializers.ModelSerializer):
    user = VendorUserSerializer(read_only=True)

    class Meta:
        model = VendorProfile
        fields = ["id", "code", "name", "company_name_bn", "user"]


class InvitedVendorSummarySerializer(serializers.ModelSerializer):
    vendor = RFQInvitedVendorSummaryVendorSerializer(read_only=True)

    class Meta:
        model = RFQVendorInvitation
        fields = ["vendor", "submitted_status"]


class RFQInvitedVendorsSummarySerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="rfq_title", read_only=True)
    category_name = serializers.CharField(source="rfq_category.name", read_only=True)
    requisition_no = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    submitted_vendors_count = serializers.SerializerMethodField()
    total_item_count = serializers.SerializerMethodField()
    published_date = serializers.DateTimeField(source="published_at", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    invited_vendors = InvitedVendorSummarySerializer(
        source="vendor_invitations", many=True, read_only=True
    )

    class Meta:
        model = RFQ
        fields = [
            "id",
            "rfq_number",
            "rfq_title",
            "title",
            "requisition_no",
            "department_name",
            "category_name",
            "total_estimated_value",
            "submission_deadline",
            "published_date",
            "vendors_count",
            "submitted_vendors_count",
            "total_item_count",
            "status",
            "urgency",
            "created_by_name",
            "invited_vendors",
        ]

    def get_requisition_no(self, obj):
        requisition = obj.requisitions.first()
        return requisition.requisition_no if requisition else None

    def get_department_name(self, obj):
        requisition = obj.requisitions.first()
        return requisition.department.name if requisition and requisition.department else None

    def get_submitted_vendors_count(self, obj):
        return obj.vendor_invitations.filter(submitted_status=True).count()

    def get_total_item_count(self, obj):
        return obj.line_items.count()


class RFQLineItemSerializer(serializers.ModelSerializer):
    rfq_number = serializers.CharField(source="rfq.rfq_number", read_only=True)
    requisition_id = serializers.IntegerField(source="requisition.id", read_only=True)
    requisition_no = serializers.CharField(source="requisition.requisition_no", read_only=True)
    item_id = serializers.IntegerField(source="item.id", read_only=True)
    source_material_item_id = serializers.IntegerField(source="source_material_item.id", read_only=True)
    specifications = serializers.SerializerMethodField()
    estimated_total = serializers.SerializerMethodField()

    class Meta:
        model = RFQLineItem
        fields = [
            "id",
            "rfq_number",
            "requisition_id",
            "requisition_no",
            "source_material_item_id",
            "item_id",
            "item_name",
            "specifications",
            "quantity",
            "unit",
            "estimated_unit_price",
            "estimated_total",
            "sort_order",
        ]

    def _normalize_name(self, value):
        if not value:
            return ""
        return " ".join(str(value).split()).casefold()

    def _get_rfq_specifications_map(self, obj):
        cache = getattr(self, "_rfq_specifications_map", None)
        if cache is None:
            cache = {}
            self._rfq_specifications_map = cache

        if obj.rfq_id in cache:
            return cache[obj.rfq_id]

        specification_map = {}
        rfq = obj.rfq

        for requisition in rfq.requisitions.all():
            for material_item in requisition.material_items.all():
                specification = None
                names = [material_item.requested_item_name]

                if material_item.item_id and material_item.item:
                    specification = material_item.item.specifications
                    names.extend(
                        [
                            getattr(material_item.item, "item_name", None),
                            getattr(material_item.item, "name", None),
                        ]
                    )

                if not specification:
                    continue

                for name in names:
                    normalized_name = self._normalize_name(name)
                    if normalized_name and normalized_name not in specification_map:
                        specification_map[normalized_name] = specification

        for item in rfq.items.all():
            specification = getattr(item, "specifications", None)
            if not specification:
                continue

            for name in (getattr(item, "item_name", None), getattr(item, "name", None)):
                normalized_name = self._normalize_name(name)
                if normalized_name and normalized_name not in specification_map:
                    specification_map[normalized_name] = specification

        cache[obj.rfq_id] = specification_map
        return specification_map

    def _resolve_specification(self, obj):
        if obj.specification:
            return obj.specification
        if obj.source_material_item_id and obj.source_material_item:
            source_item = obj.source_material_item.item
            if source_item and source_item.specifications:
                return source_item.specifications
        if obj.item_id and obj.item and obj.item.specifications:
            return obj.item.specifications
        specification_map = self._get_rfq_specifications_map(obj)
        return specification_map.get(self._normalize_name(obj.item_name))

    def get_specification(self, obj):
        return self._resolve_specification(obj)

    def get_specifications(self, obj):
        return self._resolve_specification(obj)

    def get_estimated_total(self, obj):
        return obj.estimated_total


class RFQSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="rfq_title", read_only=True)
    category_name = serializers.CharField(source="rfq_category.name", read_only=True)
    invited_vendors = RFQInvitedVendorSerializer(source="vendor_invitations", many=True, read_only=True)
    requisitions = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    requisition_no = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    submitted_vendors_count = serializers.SerializerMethodField()
    line_items = RFQLineItemSerializer(many=True, read_only=True)
    total_item_count = serializers.SerializerMethodField()
    rfq_attachments = RFQAttachmentSerializer(source="rfq_attachment", many=True, read_only=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = RFQ
        fields = [
            "id",
            "rfq_number",
            "rfq_category",
            "category_name",
            "rfq_title",
            "title",
            "description",
            "submission_deadline",
            "status",
            "urgency",
            "payment_terms",
            "incoterm",
            "tax_terms",
            "delivery_commitment_days",
            "required_documents",
            "published_at",
            "items",
            "requisitions",
            "requisition_no",
            "invited_vendors",
            "vendors_count",
            "submitted_vendors_count",
            "department_name",
            "responses_received",
            "total_estimated_value",
            "total_item_count",
            "line_items",
            "rfq_attachments",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "rfq_number",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
            "vendors_count",
            "responses_received",
            "total_estimated_value",
            "total_item_count",
        ]

    def get_requisition_no(self, obj):
        requisition = obj.requisitions.first()
        return requisition.requisition_no if requisition else None

    def get_department_name(self, obj):
        requisition = obj.requisitions.first()
        return requisition.department.name if requisition and requisition.department else None

    def get_submitted_vendors_count(self, obj):
        return obj.vendor_invitations.filter(submitted_status=True).count()

    def get_total_item_count(self, obj):
        return obj.line_items.count()


class SimpleRFQSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="rfq_title", read_only=True)
    requisition_no = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="rfq_category.name", read_only=True)
    published_date = serializers.DateTimeField(source="published_at", read_only=True)
    submitted_vendors_count = serializers.SerializerMethodField()
    total_item_count = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = RFQ
        fields = [
            "id",
            "rfq_number",
            "rfq_title",
            "title",
            "requisition_no",
            "department_name",
            "category_name",
            "total_estimated_value",
            "submission_deadline",
            "published_date",
            "vendors_count",
            "submitted_vendors_count",
            "total_item_count",
            "status",
            "urgency",
            "created_by_name",
        ]

    def get_requisition_no(self, obj):
        requisition = obj.requisitions.first()
        return requisition.requisition_no if requisition else None

    def get_department_name(self, obj):
        requisition = obj.requisitions.first()
        return requisition.department.name if requisition and requisition.department else None

    def get_submitted_vendors_count(self, obj):
        return obj.vendor_invitations.filter(submitted_status=True).count()

    def get_total_item_count(self, obj):
        return obj.line_items.count()


class RFQCreateUpdateSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="rfq_title", required=False, allow_blank=True, allow_null=True)
    material_requisitions = serializers.PrimaryKeyRelatedField(
        queryset=MaterialRequisition.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )
    items = serializers.PrimaryKeyRelatedField(
        queryset=Item.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )
    invited_vendors = serializers.PrimaryKeyRelatedField(
        queryset=VendorProfile.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )
    required_documents = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        style={"base_template": "textarea.html"},
    )
    line_items = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        write_only=True,
        allow_null=True,
        style={"base_template": "textarea.html"},
    )

    class Meta:
        model = RFQ
        fields = [
            "id",
            "rfq_category",
            "title",
            "rfq_title",
            "description",
            "submission_deadline",
            "status",
            "urgency",
            "payment_terms",
            "incoterm",
            "tax_terms",
            "delivery_commitment_days",
            "required_documents",
            "published_at",
            "material_requisitions",
            "items",
            "invited_vendors",
            "line_items",
        ]
        read_only_fields = [
            "id",
            "rfq_number",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        title = attrs.get("rfq_title") or getattr(self.instance, "rfq_title", None)
        if not title:
            raise serializers.ValidationError({"title": "RFQ title is required."})
        return attrs

    def create(self, validated_data):
        invited_vendor_ids = validated_data.pop("invited_vendors", [])
        line_items = validated_data.pop("line_items", [])
        items = validated_data.pop("items", [])
        requisitions = self._resolve_material_requisitions(validated_data)

        request = self.context.get("request")
        validated_data["created_by"] = request.user if request else None

        instance = RFQ.objects.create(**validated_data)
        if requisitions is not None:
            instance.requisitions.set(requisitions)
        if items:
            instance.items.set(items)
        self._sync_invited_vendors(instance, invited_vendor_ids)
        self._sync_line_items(instance, line_items)
        instance.sync_aggregates()
        return instance

    def update(self, instance, validated_data):
        invited_vendor_ids = validated_data.pop("invited_vendors", None)
        line_items = validated_data.pop("line_items", None)
        items = validated_data.pop("items", None)
        requisitions = self._resolve_material_requisitions(validated_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if requisitions is not None:
            instance.requisitions.set(requisitions)
        if items is not None:
            instance.items.set(items)
        if invited_vendor_ids is not None:
            self._sync_invited_vendors(instance, invited_vendor_ids)
        if line_items is not None:
            self._sync_line_items(instance, line_items)
        instance.sync_aggregates()
        return instance

    def _resolve_material_requisitions(self, validated_data):
        many = validated_data.pop("material_requisitions", None)
        if many is None:
            return None
        return list(many)

    def _sync_invited_vendors(self, instance, invited_vendors):
        instance.vendor_invitations.all().delete()
        invitations = []
        for vendor in invited_vendors:
            vendor_id = vendor.pk if hasattr(vendor, "pk") else vendor
            invitations.append(
                RFQVendorInvitation(
                    rfq=instance,
                    vendor_id=vendor_id,
                    invite_status="sent",
                )
            )
        if invitations:
            RFQVendorInvitation.objects.bulk_create(invitations)

    def _sync_line_items(self, instance, line_items):
        if line_items is None:
            return
        instance.line_items.all().delete()
        if not line_items:
            return

        objects = []
        for index, raw in enumerate(line_items, start=1):
            requisition = None
            if raw.get("requisition"):
                requisition = MaterialRequisition.objects.filter(pk=raw.get("requisition")).first()

            source_material_item = None
            if raw.get("source_material_item"):
                source_material_item = MaterialItem.objects.filter(pk=raw.get("source_material_item")).first()
                if not requisition and source_material_item:
                    requisition = source_material_item.material_requisition

            item = None
            if raw.get("item"):
                item = Item.objects.filter(pk=raw.get("item")).first()
            elif source_material_item and source_material_item.item_id:
                item = source_material_item.item

            item_name = raw.get("item_name")
            if not item_name:
                if item is not None:
                    item_name = item.item_name
                elif source_material_item is not None:
                    item_name = (
                        source_material_item.item.item_name
                        if source_material_item.item_id and source_material_item.item
                        else source_material_item.requested_item_name
                    )

            if not item_name:
                continue

            specification = raw.get("specification") or raw.get("specifications")
            if specification is None:
                if source_material_item and source_material_item.item_id and source_material_item.item:
                    specification = source_material_item.item.specifications
                elif item is not None:
                    specification = item.specifications

            objects.append(
                RFQLineItem(
                    rfq=instance,
                    requisition=requisition,
                    source_material_item=source_material_item,
                    item=item,
                    item_name=item_name,
                    specification=specification,
                    quantity=raw.get("quantity") or 1,
                    unit=raw.get("unit"),
                    estimated_unit_price=raw.get("estimated_unit_price"),
                    sort_order=index,
                )
            )

        if objects:
            RFQLineItem.objects.bulk_create(objects)

