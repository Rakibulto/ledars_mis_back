from rest_framework import serializers
from django.db import transaction
from employee.models import Department
from inventory.models import Item
from project_managements.models import ProjectManagementProject
from donor.models import Donor
from ..models.requisition_models import (
    DonorCode,
    MaterialRequisition,
    MaterialItem,
    MaterialRequisitionAttachment,
    MaterialRequisitionStatusLog,
    MaterialRequisitionApprovalStep,
)


class DonorCodeSerializer(serializers.ModelSerializer):

    class Meta:
        model = DonorCode
        fields = ["id", "code", "name", "description", "is_active", "created_at"]
        read_only_fields = ["id", "code", "created_at"]

    def create(self, validated_data):
        validated_data["code"] = DonorCode.generate_code()
        return super().create(validated_data)


class MaterialRequisitionAttachmentSerializer(serializers.ModelSerializer):

    filename = serializers.SerializerMethodField()

    class Meta:
        model = MaterialRequisitionAttachment
        fields = ["id", "file", "filename", "created_at"]
        read_only_fields = ["id", "file", "filename", "created_at"]

    def get_filename(self, obj):
        return obj.filename


class MaterialRequisitionStatusLogSerializer(serializers.ModelSerializer):

    acted_by_name = serializers.CharField(source="acted_by.username", read_only=True)

    class Meta:
        model = MaterialRequisitionStatusLog
        fields = [
            "id",
            "from_status",
            "to_status",
            "action",
            "comments",
            "acted_by",
            "acted_by_name",
            "created_at",
        ]
        read_only_fields = fields


class MaterialRequisitionApprovalStepSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(
        source="approver.employee_name", read_only=True
    )
    approver_designation = serializers.CharField(
        source="approver.designation.name", read_only=True, default=None
    )
    acted_by_name = serializers.CharField(
        source="acted_by.username", read_only=True, default=None
    )

    class Meta:
        model = MaterialRequisitionApprovalStep
        fields = [
            "id",
            "approval_level",
            "approval_mode",
            "approver",
            "approver_name",
            "approver_designation",
            "status",
            "comments",
            "acted_at",
            "acted_by",
            "acted_by_name",
            "created_at",
        ]
        read_only_fields = fields


class MaterialItemSerializer(serializers.ModelSerializer):

    item = serializers.PrimaryKeyRelatedField(
        queryset=Item.objects.all(), required=False, allow_null=True
    )

    requisition_no = serializers.SlugRelatedField(
        queryset=MaterialRequisition.objects.all(),
        slug_field="requisition_no",
        source="material_requisition",
        write_only=True,
        required=False,
    )

    requisition_no_display = serializers.CharField(
        source="material_requisition.requisition_no", read_only=True
    )

    is_manual_entry = serializers.SerializerMethodField()
    item_code = serializers.SerializerMethodField()
    item_name = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    subcategory = serializers.SerializerMethodField()
    specifications = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    current_stock = serializers.SerializerMethodField()
    unit_price = serializers.SerializerMethodField()

    total_price = serializers.SerializerMethodField()

    class Meta:
        model = MaterialItem
        fields = [
            "id",
            "requisition_no",
            "requisition_no_display",
            "item",
            "is_manual_entry",
            "requested_item_name",
            "requested_item_description",
            "requested_unit",
            "requested_unit_price",
            "remarks",
            "item_code",
            "item_name",
            "category",
            "subcategory",
            "specifications",
            "unit",
            "current_stock",
            "quantity",
            "unit_price",
            "total_price",
        ]

    def validate(self, attrs):
        item = attrs.get("item")
        requested_item_name = attrs.get("requested_item_name")
        requested_unit = attrs.get("requested_unit")

        if not item and not requested_item_name:
            raise serializers.ValidationError(
                {"item": "Select an inventory item or enter a new item request."}
            )

        if not item and not requested_unit:
            raise serializers.ValidationError(
                {"requested_unit": "Unit is required for a new item request."}
            )

        return attrs

    def get_is_manual_entry(self, obj):
        return obj.is_manual_entry

    def get_item_code(self, obj):
        if obj.item:
            return obj.item.item_code
        return "NEW-ITEM"

    def get_item_name(self, obj):
        if obj.item:
            return obj.item.item_name
        return obj.requested_item_name

    def get_category(self, obj):
        if obj.item and obj.item.category:
            return str(obj.item.category)
        if obj.material_requisition and obj.material_requisition.category:
            return str(obj.material_requisition.category)
        return None

    def get_subcategory(self, obj):
        if obj.item and obj.item.subcategory:
            return str(obj.item.subcategory)
        return None

    def get_specifications(self, obj):
        if obj.item:
            return obj.item.specifications
        return None

    def get_unit(self, obj):
        if obj.item:
            return obj.item.unit
        return obj.requested_unit

    def get_current_stock(self, obj):
        if obj.item:
            return obj.item.current_stock
        return "Pending procurement"

    def get_unit_price(self, obj):
        """Inventory reference price (item.cost)."""
        return obj.inventory_unit_price

    def get_total_price(self, obj):
        """quantity × requested_unit_price (fallback: inventory cost)."""
        if obj.quantity is None:
            return 0
        return obj.quantity * obj.effective_unit_price


class MaterialRequisitionSerializer(serializers.ModelSerializer):

    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True
    )
    department_name = serializers.CharField(source="department.name", read_only=True)

    project = serializers.PrimaryKeyRelatedField(
        queryset=ProjectManagementProject.objects.all(), required=False, allow_null=True
    )
    project_info = serializers.SerializerMethodField()

    donor_code = serializers.PrimaryKeyRelatedField(
        queryset=Donor.objects.all(), required=False, allow_null=True
    )
    donor_code_info = serializers.SerializerMethodField()

    category_name = serializers.SerializerMethodField()

    budget_code_display = serializers.SerializerMethodField()
    account_code_display = serializers.SerializerMethodField()

    requesting_office_info = serializers.SerializerMethodField()
    delivery_location_info = serializers.SerializerMethodField()

    created_by = serializers.SerializerMethodField()
    approver1_info = serializers.SerializerMethodField()
    approver2_info = serializers.SerializerMethodField()
    attachments = MaterialRequisitionAttachmentSerializer(many=True, read_only=True)
    status_logs = MaterialRequisitionStatusLogSerializer(many=True, read_only=True)
    approval_steps = MaterialRequisitionApprovalStepSerializer(
        many=True, read_only=True
    )
    attachment_files = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False
    )

    mr_items = MaterialItemSerializer(source="material_items", many=True)
    item_count = serializers.IntegerField(source="material_items.count", read_only=True)

    class Meta:
        model = MaterialRequisition
        fields = [
            "id",
            "requisition_no",
            # Phase 1 – Basic Info
            "department",
            "department_name",
            "project",
            "project_info",
            "donor_code",
            "donor_code_info",
            "category",
            "category_name",
            "priority",
            "fiscal_year",
            "purpose",
            # Phase 2 – Budget
            "budget_code",
            "budget_code_display",
            "account_code",
            "account_code_display",
            # Phase 3 – BOQ items
            "mr_items",
            "item_count",
            "total_amount",
            # Phase 4 – Specifications
            "specifications",
            "preferred_brand",
            "alternative_brands",
            "warranty_period",
            "country_of_origin",
            "quality_standards",
            # Phase 5 – Delivery
            "requesting_office",
            "requesting_office_info",
            "delivery_location",
            "delivery_location_info",
            "delivery_date",
            "contact_person",
            "contact_phone",
            "special_instruction",
            # Phase 6 – Attachments
            "attachment",
            "attachments",
            "attachment_files",
            # Workflow
            "status",
            "approver1",
            "approver1_info",
            "approver2",
            "approver2_info",
            "approval_steps",
            "status_logs",
            "created_by",
            "version",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "requisition_no",
            "created_by",
            "total_amount",
            "version",
            "created_at",
            "updated_at",
        ]

    def get_category_name(self, obj):
        if obj.category:
            return str(obj.category)
        return None

    def get_project_info(self, obj):
        if obj.project:
            return {
                "id": obj.project.id,
                "code": obj.project.code,
                "name": obj.project.title,
                "donor": obj.project.donor_id,
            }
        return None

    def get_donor_code_info(self, obj):
        if obj.donor_code:
            return {
                "id": obj.donor_code.id,
                "code": obj.donor_code.donor_code,
                "name": obj.donor_code.name,
            }
        return None

    def get_budget_code_display(self, obj):
        if obj.budget_code:
            return {
                "id": obj.budget_code.id,
                # "name": str(obj.budget_code),
                "name": obj.budget_code.name,
                "code": obj.budget_code.code,
            }
        return None

    def get_account_code_display(self, obj):
        if obj.account_code:
            return {
                "id": obj.account_code.id,
                "name": str(obj.account_code),
            }
        return None

    def get_requesting_office_info(self, obj):
        if obj.requesting_office:
            return {
                "id": obj.requesting_office.id,
                "name": obj.requesting_office.name,
                "address": obj.requesting_office.address,
            }
        return None

    def get_delivery_location_info(self, obj):
        if obj.delivery_location:
            return {
                "id": obj.delivery_location.id,
                "name": obj.delivery_location.name,
                "address": obj.delivery_location.address,
            }
        return None

    def get_created_by(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "email": obj.created_by.email,
            }
        return None

    def get_approver1_info(self, obj):
        if obj.approver1:
            return {
                "id": obj.approver1.pk,
                "user_id": obj.approver1.user_id,
                "employee_id": obj.approver1.employee_id,
                "employee_name": obj.approver1.employee_name,
                "department": (
                    obj.approver1.department.name if obj.approver1.department else None
                ),
                "designation": (
                    obj.approver1.designation.name
                    if obj.approver1.designation
                    else None
                ),
            }
        return None

    def get_approver2_info(self, obj):
        if obj.approver2:
            return {
                "id": obj.approver2.pk,
                "user_id": obj.approver2.user_id,
                "employee_id": obj.approver2.employee_id,
                "employee_name": obj.approver2.employee_name,
                "department": (
                    obj.approver2.department.name if obj.approver2.department else None
                ),
                "designation": (
                    obj.approver2.designation.name
                    if obj.approver2.designation
                    else None
                ),
            }
        return None

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("material_items", [])
        attachment_files = validated_data.pop("attachment_files", None)
        mr = MaterialRequisition.objects.create(**validated_data)
        for item_data in items_data:
            MaterialItem.objects.create(material_requisition=mr, **item_data)
        self._create_attachments(mr, attachment_files)
        mr.calculate_total_amount()
        MaterialRequisitionStatusLog.objects.create(
            material_requisition=mr,
            from_status=None,
            to_status=mr.status or "Draft",
            action="Created",
            comments="Requisition created",
            acted_by=mr.created_by,
        )
        return mr

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop("material_items", None)
        attachment_files = validated_data.pop("attachment_files", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            instance.material_items.all().delete()
            for item_data in items_data:
                MaterialItem.objects.create(material_requisition=instance, **item_data)
            instance.calculate_total_amount()

        if attachment_files:
            self._create_attachments(instance, attachment_files)

        return instance

    def _create_attachments(self, requisition, attachment_files=None):
        request = self.context.get("request")
        files = list(attachment_files or [])

        if request is not None:
            files.extend(request.FILES.getlist("attachment_files"))

        if not files:
            return

        user = request.user if request and request.user.is_authenticated else None

        for attachment_file in files:
            MaterialRequisitionAttachment.objects.create(
                material_requisition=requisition,
                file=attachment_file,
                uploaded_by=user,
            )
