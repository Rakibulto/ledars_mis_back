from rest_framework import serializers
from django.db import transaction
from rest_framework.exceptions import ValidationError
from inventory.models import Category, Item
from employee.models import Employee, Department, Designation
from projects.models import Project
from vendorportal.models.models import VendorProfile
from ..models.models import (
    PurchaseOrder,
    ItemPO,
    PurchaseRequisition,
    ApprovalRequest,
    ApprovalHistory,
    ItemPR,
)


class PurchaseRequisitionSummarySerializer(serializers.Serializer):
    total_prs = serializers.IntegerField()
    draft = serializers.IntegerField()
    submitted = serializers.IntegerField()
    approved = serializers.IntegerField()
    po_created = serializers.IntegerField()


class ProcurementAnalyticsSerializer(serializers.Serializer):
    total_prs = serializers.IntegerField()
    total_pos = serializers.IntegerField()


class SupplierSummarySerializer(serializers.Serializer):
    total_suppliers = serializers.IntegerField()
    active_suppliers = serializers.IntegerField()
    active_contracts = serializers.IntegerField()
    avg_rating = serializers.IntegerField()


class POSummarySerializer(serializers.Serializer):
    total_pos = serializers.IntegerField()
    pending_pos = serializers.IntegerField()
    approved_pos = serializers.IntegerField()


class SupplierSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(level="Main"),
        write_only=True,
        allow_null=True,
        required=False,
    )
    category = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    category_ids = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(level="Main"),
        many=True,
        required=False,
        write_only=True,
    )

    # Alias fields for frontend compatibility
    company_name = serializers.CharField(
        source="name",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    tin_number = serializers.CharField(
        source="tax_id",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    contact_number = serializers.CharField(
        source="phone",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    category_name = serializers.SerializerMethodField()

    def get_category(self, obj):
        first_category = obj.categories.order_by("id").first()
        return first_category.name if first_category else None

    def get_categories(self, obj):
        return list(obj.categories.values_list("name", flat=True))

    def get_category_name(self, obj):
        return self.get_category(obj)

    def _set_categories(self, instance, category_id, category_ids):
        if category_id is serializers.empty and category_ids is serializers.empty:
            return

        selected_categories = []
        if category_id not in (serializers.empty, None):
            selected_categories.append(category_id)
        if category_ids is not serializers.empty:
            selected_categories.extend(category_ids)

        deduped_categories = []
        seen_ids = set()
        for category in selected_categories:
            if category.pk in seen_ids:
                continue
            seen_ids.add(category.pk)
            deduped_categories.append(category)

        instance.categories.set(deduped_categories)

    def create(self, validated_data):
        category_id = validated_data.pop("category_id", serializers.empty)
        category_ids = validated_data.pop("category_ids", serializers.empty)
        instance = super().create(validated_data)
        self._set_categories(instance, category_id, category_ids)
        return instance

    def update(self, instance, validated_data):
        category_id = validated_data.pop("category_id", serializers.empty)
        category_ids = validated_data.pop("category_ids", serializers.empty)
        instance = super().update(instance, validated_data)
        self._set_categories(instance, category_id, category_ids)
        return instance

    class Meta:
        model = VendorProfile
        fields = "__all__"
        read_only_fields = ["code", "created_by", "created_at", "updated_at"]


class ItemPOSerializer(serializers.ModelSerializer):
    po_number = serializers.PrimaryKeyRelatedField(
        queryset=PurchaseOrder.objects.all(),
        source="purchase_order",
        write_only=True,
        required=False,
    )

    po_number_display = serializers.CharField(
        source="purchase_order.po_number", read_only=True
    )

    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    category = serializers.CharField(source="item.category", read_only=True)
    subcategory = serializers.CharField(source="item.subcategory", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)
    current_stock = serializers.CharField(source="item.current_stock", read_only=True)
    unit_price = serializers.DecimalField(
        source="item.unit_price", max_digits=10, decimal_places=2, read_only=True
    )
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = ItemPO
        fields = [
            "id",
            "po_number",
            "po_number_display",
            "item",
            "item_code",
            "item_name",
            "category",
            "subcategory",
            "unit",
            "current_stock",
            "quantity",
            "unit_price",
            "total_price",
        ]

    # Method to calculate total_price
    def get_total_price(self, obj):
        if obj.item is None or obj.quantity is None:
            return 0
        return obj.quantity * obj.item.unit_price


class PurchaseOrderSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()

    supplier = serializers.PrimaryKeyRelatedField(
        queryset=VendorProfile.objects.all(), write_only=True
    )
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    po_items = ItemPOSerializer(many=True)
    item_count = serializers.IntegerField(source="po_items.count", read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = "__all__"
        read_only_fields = [
            "po_number",
            "total_amount",
            "created_by",
            "created_at",
            "updated_at",
        ]

    # SerializerMethodField
    def get_created_by(self, obj):
        if not obj.created_by:
            return None

        return {
            "employee_name": obj.created_by.employee_name,
            "department": (
                obj.created_by.department.name if obj.created_by.department else None
            ),
            "designation": (
                obj.created_by.designation.name if obj.created_by.designation else None
            ),
        }

    @transaction.atomic
    def create(self, validated_data):
        po_items_data = validated_data.pop("po_items", [])
        request = self.context.get("request")
        employee = None

        if request and request.user.is_authenticated:
            employee = Employee.objects.filter(user=request.user).first()
            validated_data["created_by"] = employee

        purchase_order = PurchaseOrder.objects.create(**validated_data)

        for item_data in po_items_data:
            item_obj = item_data.get("item")
            if not item_obj:
                continue
            ItemPO.objects.create(purchase_order=purchase_order, **item_data)

        purchase_order.calculate_total_amount()
        return purchase_order

    @transaction.atomic
    def update(self, instance, validated_data):
        po_items_data = validated_data.pop("po_items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if po_items_data is not None:
            existing_items = {item.id: item for item in instance.po_items.all()}
            merged_payload = {}

            for item_data in po_items_data:
                item_obj = item_data.get("item")
                item_id = item_data.get("id")
                if not item_obj:
                    continue

                key = item_obj.id if hasattr(item_obj, "id") else item_obj
                if key in merged_payload:
                    merged_payload[key]["quantity"] += item_data.get("quantity", 0)
                else:
                    merged_payload[key] = item_data.copy()

            payload_ids = []

            for item_data in merged_payload.values():
                item_id = item_data.get("id")
                item_obj = item_data.get("item")

                if item_id and item_id in existing_items:
                    item_instance = existing_items[item_id]
                    for attr, value in item_data.items():
                        setattr(item_instance, attr, value)
                    item_instance.save()
                    payload_ids.append(item_id)
                else:
                    existing_same_item = instance.po_items.filter(item=item_obj).first()
                    if existing_same_item:
                        existing_same_item.quantity += item_data.get("quantity", 0)
                        existing_same_item.save()
                        payload_ids.append(existing_same_item.id)
                    else:
                        new_item = ItemPO.objects.create(
                            purchase_order=instance, **item_data
                        )
                        payload_ids.append(new_item.id)

            for item_id, item_instance in existing_items.items():
                if item_id not in payload_ids:
                    item_instance.delete()

        instance.calculate_total_amount()
        return instance


class ItemPRSerializer(serializers.ModelSerializer):

    pr_number = serializers.SlugRelatedField(
        queryset=PurchaseRequisition.objects.all(),
        slug_field="pr_number",
        source="purchase_requisition",
        write_only=True,
        required=False,
    )

    pr_number_display = serializers.CharField(
        source="purchase_requisition.pr_number", read_only=True
    )

    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    category = serializers.CharField(source="item.category", read_only=True)
    subcategory = serializers.CharField(source="item.subcategory", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)
    current_stock = serializers.CharField(source="item.current_stock", read_only=True)
    unit_price = serializers.DecimalField(
        source="item.unit_price", max_digits=10, decimal_places=2, read_only=True
    )
    total_price = serializers.SerializerMethodField()

    # item = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = ItemPR
        fields = [
            "id",
            "pr_number",
            "pr_number_display",
            "item",
            "item_code",
            "item_name",
            "category",
            "subcategory",
            "unit",
            "current_stock",
            "quantity",
            "unit_price",
            "total_price",
        ]

    def get_total_price(self, obj):
        if obj.item is None or obj.quantity is None:
            return 0
        return obj.quantity * obj.item.unit_price


class PurchaseRequisitionSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), write_only=True, required=False, allow_null=True
    )
    project_name = serializers.CharField(source="project.name", read_only=True)

    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    department_name = serializers.CharField(source="department.name", read_only=True)
    approver = serializers.SerializerMethodField()
    pr_items = ItemPRSerializer(many=True)
    item_count = serializers.IntegerField(source="pr_items.count", read_only=True)
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseRequisition
        fields = [
            "id",
            "pr_number",
            "department",
            "department_name",
            "project",
            "project_name",
            "created_by",
            "approver",
            "status",
            "estimated_amount",
            "pr_items",
            "item_count",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "department_name",
            "project_name",
            "estimated_amount",
            "pr_number",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_created_by(self, obj):
        if not obj.created_by:
            return None

        return {
            "employee_name": obj.created_by.employee_name,
            "department": (
                obj.created_by.department.name if obj.created_by.department else None
            ),
            "designation": (
                obj.created_by.designation.name if obj.created_by.designation else None
            ),
        }

    def get_approver(self, obj):
        if not obj.approver:
            return None

        return {
            "employee_name": obj.approver.employee_name,
            "department": (
                obj.approver.department.name if obj.approver.department else None
            ),
            "designation": (
                obj.approver.designation.name if obj.approver.designation else None
            ),
        }

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        employee = None

        if request and request.user.is_authenticated:
            employee = Employee.objects.filter(user=request.user).first()
            if not employee:
                raise ValidationError("Employee profile not found.")

        validated_data["created_by"] = employee

        pr_items_data = validated_data.pop("pr_items")
        purchase_requisition = PurchaseRequisition.objects.create(**validated_data)

        for item_data in pr_items_data:
            ItemPR.objects.create(
                purchase_requisition=purchase_requisition, **item_data
            )

        # HERE WE CALL AUTO CALCULATION
        purchase_requisition.calculate_estimated_amount()

        return purchase_requisition

    @transaction.atomic
    def update(self, instance, validated_data):
        request = self.context.get("request")
        employee = None

        if request and request.user.is_authenticated:
            employee = Employee.objects.filter(user=request.user).first()

        pr_items_data = validated_data.pop("pr_items", None)

        # Update main fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Handle approver based on status change
        if "status" in validated_data:
            if instance.status in ["Approved", "Rejected"]:
                instance.approver = employee
            else:
                instance.approver = None

        instance.save()

        if pr_items_data is not None:

            existing_items = {item.id: item for item in instance.pr_items.all()}

            # Step 1: Merge duplicate items from payload (same item FK)
            merged_payload = {}

            for item_data in pr_items_data:
                item_obj = item_data.get("item")
                item_id = item_data.get("id")
                if not item_obj:
                    continue  # skip invalid / empty item

                key = item_obj.id if hasattr(item_obj, "id") else item_obj

                if key in merged_payload:
                    # sum quantity
                    merged_payload[key]["quantity"] += item_data.get("quantity", 0)
                else:
                    merged_payload[key] = item_data.copy()

            payload_ids = []

            # Step 2: Process merged payload
            for item_data in merged_payload.values():
                item_id = item_data.get("id", None)

                if item_id and item_id in existing_items:
                    # UPDATE
                    item_instance = existing_items[item_id]

                    for attr, value in item_data.items():
                        setattr(item_instance, attr, value)

                    item_instance.save()
                    payload_ids.append(item_id)

                else:
                    # CHECK if same item already exists in DB
                    existing_same_item = instance.pr_items.filter(
                        item=item_data.get("item")
                    ).first()

                    if existing_same_item:
                        # sum quantity in DB
                        existing_same_item.quantity += item_data.get("quantity", 0)
                        existing_same_item.save()
                        payload_ids.append(existing_same_item.id)
                    else:
                        # CREATE new
                        new_item = ItemPR.objects.create(
                            purchase_requisition=instance, **item_data
                        )
                        payload_ids.append(new_item.id)

            # Step 3: Delete items not in payload
            for item_id, item_instance in existing_items.items():
                if item_id not in payload_ids:
                    item_instance.delete()
        # HERE WE CALL AUTO CALCULATION

        instance.calculate_estimated_amount()
        return instance


# class RFQSerializer(serializers.ModelSerializer):
#     items_count = serializers.IntegerField(read_only=True)

#     created_by = serializers.CharField(source='created_by.username', read_only=True)
#     items = serializers.SlugRelatedField(
#         many=True,
#         read_only=True,
#         slug_field='item_name'   # তোমার Item model এ যেই field এ নাম আছে
#     )

#     item_ids = serializers.PrimaryKeyRelatedField(
#         many=True,
#         queryset=Item.objects.all(),
#         source='items',
#         write_only=True
#     )

#     class Meta:
#         model = RFQ
#         fields = "__all__"
#         read_only_fields = ['rfq_number', 'created_by', 'created_at', 'updated_at']


class ApprovalRequestSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    # current_approver = serializers.CharField(source='current_approver.username', read_only=True)
    class Meta:
        model = ApprovalRequest
        fields = "__all__"
        read_only_fields = [
            "reference_number",
            "created_by",
            "submitted_date",
            "created_at",
            "updated_at",
        ]


class ApprovalHistorySerializer(serializers.ModelSerializer):
    approver = serializers.CharField(source="approver.username", read_only=True)

    class Meta:
        model = ApprovalHistory
        fields = "__all__"
        read_only_fields = ["approver", "created_at"]
