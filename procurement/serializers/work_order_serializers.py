from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework import serializers
from django.db import transaction

from vendorportal.models.models import VendorProfile
from authentication.models import User as AuthUser
from ..models.work_order_models import (
    WorkOrder,
    WorkOrderItem,
    WorkOrderApprovalHistory,
    WorkOrderNotificationLog,
    WorkOrderAttachment,
    VendorAcceptance,
)


def _normalize_str(value):
    return str(value).strip().lower() if value is not None else ""


def _find_award_item(award, item=None, item_data=None):
    if not award or not award.items:
        return None
    award_items = award.items or []
    lookup_values = set()

    if item is not None:
        lookup_values.update(
            [
                _normalize_str(getattr(item, "item_name", "")),
                _normalize_str(getattr(item, "item_code", "")),
                _normalize_str(getattr(item, "id", "")),
            ]
        )
    if item_data is not None:
        lookup_values.update(
            [
                _normalize_str(item_data.get("description", "")),
                _normalize_str(item_data.get("specification", "")),
                _normalize_str(item_data.get("item_code", "")),
                _normalize_str(item_data.get("itemCode", "")),
            ]
        )
    lookup_values = {v for v in lookup_values if v}

    for award_item in award_items:
        if not isinstance(award_item, dict):
            continue

        award_keys = {
            _normalize_str(award_item.get("description", "")),
            _normalize_str(award_item.get("specification", "")),
            _normalize_str(award_item.get("item_code", "")),
            _normalize_str(award_item.get("itemCode", "")),
            _normalize_str(award_item.get("code", "")),
            _normalize_str(award_item.get("itemId", "")),
            _normalize_str(award_item.get("item_id", "")),
        }

        if lookup_values & award_keys:
            return award_item
    return None


# ── Sub-serializers ──────────────────────────────────────────────────────────


class WorkOrderItemSerializer(serializers.ModelSerializer):
    work_order_number = serializers.CharField(
        source="work_order.wo_number", read_only=True
    )
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    specification = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    unitPrice = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    delivered = serializers.IntegerField(read_only=True)
    deliveryStatus = serializers.CharField(
        source="item_delivery_status", read_only=True
    )

    class Meta:
        model = WorkOrderItem
        fields = [
            "id",
            "work_order_number",
            "name",
            "description",
            "specification",
            "unit",
            "quantity",
            "unitPrice",
            "total",
            "delivered",
            "deliveryStatus",
        ]
        read_only_fields = fields

    def _find_award_item(self, obj):
        if not obj:
            return None
        award = obj.item or getattr(obj.work_order, "award", None)
        if not award:
            return None
        award_items = award.items or []

        obj_description = _normalize_str(obj.description)
        obj_specification = _normalize_str(obj.specification)

        for award_item in award_items:
            if not isinstance(award_item, dict):
                continue

            award_description = _normalize_str(
                award_item.get("description")
                or award_item.get("item_name")
                or award_item.get("name")
            )
            award_specification = _normalize_str(award_item.get("specification"))
            award_codes = {
                _normalize_str(award_item.get("item_code")),
                _normalize_str(award_item.get("itemCode")),
                _normalize_str(award_item.get("code")),
                _normalize_str(award_item.get("itemId")),
                _normalize_str(award_item.get("item_id")),
            }

            if obj_description and obj_description == award_description:
                return award_item
            if obj_description and obj_description == award_specification:
                return award_item
            if obj_specification and obj_specification == award_description:
                return award_item
            if obj_specification and obj_specification == award_specification:
                return award_item
            if (
                _normalize_str(getattr(obj, "item_code", None))
                and _normalize_str(obj.item_code) in award_codes
            ):
                return award_item

        # Fallback: align line items to award items by order if descriptions are empty or unmatched.
        try:
            work_order_items = list(obj.work_order.work_order_items.order_by("id"))
            index = work_order_items.index(obj)
            if 0 <= index < len(award_items):
                candidate = award_items[index]
                if isinstance(candidate, dict):
                    return candidate
        except ValueError:
            pass

        return None

    def _resolve_value(self, award_item, key, fallback=None):
        if not award_item:
            return fallback
        value = award_item.get(key)
        if value is None and key == "unitPrice":
            value = award_item.get("unit_price")
        return value if value is not None else fallback

    def get_name(self, obj):
        award_item = self._find_award_item(obj)
        name = (
            self._resolve_value(award_item, "name")
            or self._resolve_value(award_item, "item_name")
            or self._resolve_value(award_item, "description")
            or self._resolve_value(award_item, "itemName")
            or obj.description
        )
        if name:
            return name

        # Fallback to RFQ line item name by position when award item has no explicit name.
        award = obj.item or getattr(obj.work_order, "award", None)
        if award and getattr(award, "rfq", None):
            try:
                work_order_items = list(obj.work_order.work_order_items.order_by("id"))
                index = work_order_items.index(obj)
                rfq_lines = list(award.rfq.line_items.order_by("id"))
                if 0 <= index < len(rfq_lines):
                    return getattr(rfq_lines[index], "item_name", None)
            except ValueError:
                pass
        return ""

    def get_description(self, obj):
        award_item = self._find_award_item(obj)
        return (
            self._resolve_value(award_item, "description")
            or self._resolve_value(award_item, "item_name")
            or obj.description
        )

    def get_specification(self, obj):
        award_item = self._find_award_item(obj)
        return self._resolve_value(award_item, "specification") or obj.specification

    def get_unit(self, obj):
        award_item = self._find_award_item(obj)
        return self._resolve_value(award_item, "unit")

    def get_quantity(self, obj):
        award_item = self._find_award_item(obj)
        quantity = self._resolve_value(award_item, "quantity")
        try:
            return int(quantity)
        except (TypeError, ValueError):
            return 0

    def get_unitPrice(self, obj):
        award_item = self._find_award_item(obj)
        unit_price = self._resolve_value(award_item, "unitPrice")
        if unit_price is None:
            return "0.00"
        try:
            return str(Decimal(unit_price))
        except (TypeError, ValueError, InvalidOperation):
            return "0.00"

    def get_total(self, obj):
        award_item = self._find_award_item(obj)
        total_value = self._resolve_value(award_item, "total")
        if total_value is not None:
            try:
                return float(total_value)
            except (TypeError, ValueError):
                pass
        quantity = self.get_quantity(obj) or 0
        try:
            unit_price = Decimal(self.get_unitPrice(obj) or 0)
        except (TypeError, ValueError, InvalidOperation):
            unit_price = Decimal("0.00")
        return float(quantity * unit_price)


class WorkOrderItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkOrderItem
        fields = [
            "work_order",
            "item",
            "description",
            "specification",
            "delivered",
            "item_delivery_status",
        ]


class WorkOrderApprovalHistorySerializer(serializers.ModelSerializer):
    workOrderNumber = serializers.CharField(
        source="work_order.wo_number", read_only=True
    )

    class Meta:
        model = WorkOrderApprovalHistory
        fields = [
            "id",
            "workOrderNumber",
            "approver",
            "role",
            "action",
            "date",
            "comments",
        ]
        read_only_fields = ["id", "workOrderNumber"]


class WorkOrderNotificationLogSerializer(serializers.ModelSerializer):
    workOrderNumber = serializers.CharField(
        source="work_order.wo_number", read_only=True
    )
    sentAt = serializers.DateTimeField(source="created_at", read_only=True)
    email = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrderNotificationLog
        fields = [
            "id",
            "workOrderNumber",
            "channel",
            "date",
            "status",
            "recipient",
            "email",
            "sentAt",
        ]
        read_only_fields = ["id", "workOrderNumber", "email", "sentAt"]

    def get_email(self, obj):
        """Extract email from recipient string. Handles 'Name <email>' and plain 'email' formats."""
        if not obj.recipient:
            return None
        recipient = obj.recipient.strip()
        # "Name <email@example.com>" format
        if "<" in recipient and recipient.endswith(">"):
            return recipient.split("<")[-1].rstrip(">").strip()
        # plain email
        if "@" in recipient:
            return recipient
        return None


class WorkOrderAttachmentSerializer(serializers.ModelSerializer):
    work_order_number = serializers.SlugRelatedField(
        source="work_order",
        slug_field="wo_number",
        queryset=WorkOrder.objects.all(),
    )
    file_url = serializers.SerializerMethodField()
    upload_date = serializers.DateField(read_only=True)

    class Meta:
        model = WorkOrderAttachment
        fields = [
            "id",
            "work_order_number",
            "document_type",
            "name",
            "file",
            "file_url",
            "upload_date",
        ]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def validate_file(self, value):
        allowed_extensions = {
            "pdf",
            "xls",
            "xlsx",
            "csv",
            "doc",
            "docx",
            "txt",
            "png",
            "jpg",
            "jpeg",
            "gif",
            "svg",
            "webp",
            "bmp",
            "ppt",
            "pptx",
            "zip",
            "rar",
            "odt",
            "ods",
            "odp",
        }
        extension = value.name.rsplit(".", 1)[-1].lower()
        if extension not in allowed_extensions:
            raise serializers.ValidationError(
                f"Unsupported file extension '{extension}'. Allowed extensions: {', '.join(sorted(allowed_extensions))}."
            )
        return value

    def create(self, validated_data):
        return super().create(validated_data)


# ── Lean read serializer (dropdown / list) ──────────────────────────────────


class WorkOrderLeanSerializer(serializers.ModelSerializer):
    """Lightweight serializer for dropdowns and list views.
    Returns only the fields needed to populate a work order selector."""

    workOrderNumber = serializers.CharField(source="wo_number", read_only=True)
    vendor = serializers.SerializerMethodField()
    totalAmount = serializers.SerializerMethodField()
    approvalStatus = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrder
        fields = [
            "id",
            "workOrderNumber",
            "title",
            "category",
            "status",
            "approvalStatus",
            "vendor",
            "vendor_status",
            "totalAmount",
            "order_date",
            "delivery_date",
        ]

    def get_vendor(self, obj):
        if not obj.vendor:
            return None
        return {"id": obj.vendor.id, "name": obj.vendor.name}

    def get_totalAmount(self, obj):
        return obj.total_amount or 0

    def get_approvalStatus(self, obj):
        return obj.get_approval_status_display()


# ── Read serializer ──────────────────────────────────────────────────────────


class WorkOrderSerializer(serializers.ModelSerializer):
    workOrderNumber = serializers.CharField(source="wo_number", read_only=True)
    awardNumber = serializers.CharField(
        source="award.award_number", read_only=True, default=None
    )
    awardId = serializers.SerializerMethodField()
    rfqNumber = serializers.SerializerMethodField()
    csNumber = serializers.SerializerMethodField()
    requisitionNumber = serializers.SerializerMethodField()

    vendor = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()
    budgetCode = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    termsAndConditions = serializers.SerializerMethodField()
    approvalLevel = serializers.CharField(source="approval_level", read_only=True)
    approvalChain = WorkOrderApprovalHistorySerializer(
        source="approval_history", many=True, read_only=True
    )

    approver = serializers.SerializerMethodField()

    items = serializers.SerializerMethodField()
    notificationLog = WorkOrderNotificationLogSerializer(
        source="notification_log", many=True, read_only=True
    )
    attachments = WorkOrderAttachmentSerializer(many=True, read_only=True)

    totalItems = serializers.SerializerMethodField()
    deliveredItems = serializers.SerializerMethodField()

    autoGenerated = serializers.BooleanField(source="auto_generated", read_only=True)
    deliveryLocation = serializers.CharField(source="delivery_address", read_only=True)
    paymentTerms = serializers.CharField(source="payment_terms", read_only=True)
    warrantyPeriod = serializers.CharField(source="warranty_period", read_only=True)
    tcTemplate = serializers.CharField(source="tc_template", read_only=True)
    notes = serializers.CharField(source="special_instructions", read_only=True)
    acceptanceDeadline = serializers.DateField(
        source="acceptance_deadline", read_only=True
    )
    notificationSent = serializers.BooleanField(
        source="notification_sent", read_only=True
    )
    notificationChannel = serializers.CharField(
        source="notification_channel", read_only=True
    )

    status = serializers.CharField(read_only=True)
    approvalStatus = serializers.SerializerMethodField()
    vendorStatus = serializers.CharField(source="vendor_status", read_only=True)
    deliveryStatus = serializers.CharField(source="delivery_status", read_only=True)
    paymentStatus = serializers.CharField(source="payment_status", read_only=True)

    orderDate = serializers.DateField(source="order_date", read_only=True)
    vendorAcceptanceDate = serializers.DateField(
        source="vendor_acceptance_date", read_only=True
    )
    deliveryDeadline = serializers.DateField(source="delivery_date", read_only=True)
    totalAmount = serializers.SerializerMethodField()
    taxRate = serializers.SerializerMethodField()
    amountPaid = serializers.DecimalField(
        source="amount_paid", max_digits=15, decimal_places=2, read_only=True
    )

    approvedBy = serializers.SerializerMethodField()
    approvedDate = serializers.DateTimeField(source="approved_date", read_only=True)

    created_by = serializers.CharField(source="created_by.username", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = WorkOrder
        fields = [
            "id",
            "workOrderNumber",
            "awardNumber",
            "awardId",
            "csNumber",
            "rfqNumber",
            "requisitionNumber",
            "title",
            "category",
            "budgetCode",
            "project",
            "autoGenerated",
            "status",
            "approvalStatus",
            "approvalLevel",
            "approver",
            "approvedBy",
            "approvedDate",
            "vendorStatus",
            "deliveryStatus",
            "paymentStatus",
            "orderDate",
            "vendorAcceptanceDate",
            "deliveryDeadline",
            "acceptanceDeadline",
            "totalAmount",
            "amountPaid",
            "totalItems",
            "deliveredItems",
            "notificationSent",
            "notificationChannel",
            "deliveryLocation",
            "paymentTerms",
            "warrantyPeriod",
            "tcTemplate",
            "notes",
            "organization",
            "vendor",
            "taxRate",
            "items",
            "termsAndConditions",
            "approvalChain",
            "notificationLog",
            "attachments",
            "created_by",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "workOrderNumber",
            "awardNumber",
            "totalAmount",
            "created_by",
            "createdAt",
            "updatedAt",
        ]

    def _normalize_str(self, value):
        return str(value).strip().lower() if value is not None else ""

    def get_approver(self, obj):
        if not obj.approver:
            return None
        user = obj.approver
        return {
            "id": user.id,
            "username": user.username,
            "fullName": user.get_full_name(),
            "email": user.email,
        }

    def get_approvalStatus(self, obj):
        return obj.get_approval_status_display()

    def get_totalAmount(self, obj):
        if getattr(obj, "total_amount", None) and obj.total_amount != 0:
            return obj.total_amount

        total = Decimal("0.00")
        award = getattr(obj, "award", None)
        award_items = award.items if award and award.items else []

        if not award_items and award and getattr(award, "comparative_statement", None):
            cs = award.comparative_statement
            direct_quote = (
                cs.quotations.filter(is_direct_evaluation=True).order_by("-id").first()
            )
            if direct_quote is None:
                direct_quote = (
                    cs.quotations.filter(vendor__isnull=True).order_by("-id").first()
                )
            if direct_quote is not None:
                award_items = [
                    {
                        "quantity": getattr(item, "quantity", 0),
                        "unitPrice": getattr(item, "unit_price", 0),
                        "unit_price": getattr(item, "unit_price", 0),
                        "total": getattr(item, "total", None),
                    }
                    for item in direct_quote.quotation_items.all()
                ]

        for award_item in award_items or []:
            if not isinstance(award_item, dict):
                continue
            item_total = award_item.get("total")
            if item_total is None:
                quantity = award_item.get("quantity") or 0
                unit_price = award_item.get("unitPrice")
                if unit_price is None:
                    unit_price = award_item.get("unit_price")
                try:
                    item_total = Decimal(str(quantity)) * Decimal(str(unit_price))
                except (TypeError, ValueError, InvalidOperation):
                    item_total = Decimal("0.00")
            try:
                total += Decimal(str(item_total))
            except (TypeError, ValueError, InvalidOperation):
                continue
        return total

    def get_taxRate(self, obj):
        """Derive the effective VAT rate (%) from the linked comparative
        statement's financials (vat / subtotal * 100). Falls back to 0."""
        award = getattr(obj, "award", None)
        cs = getattr(award, "comparative_statement", None) if award else None
        if not cs:
            return 0
        financial = cs.vendor_financials.first()
        if not financial or not financial.subtotal:
            return 0
        try:
            rate = (
                Decimal(str(financial.vat)) / Decimal(str(financial.subtotal))
            ) * 100
            return float(round(rate, 2))
        except (TypeError, ValueError, InvalidOperation, ZeroDivisionError):
            return 0

    def get_approvedBy(self, obj):
        if not obj.approved_by:
            return None
        emp = obj.approved_by
        designation = getattr(emp, "designation", None)
        if designation is not None and not isinstance(designation, str):
            designation = getattr(designation, "name", None) or str(designation)

        if not designation:
            linked_employee = getattr(emp, "employee", None)
            linked_designation = (
                getattr(linked_employee, "designation", None)
                if linked_employee
                else None
            )
            if linked_designation is not None:
                designation = getattr(linked_designation, "name", None) or str(
                    linked_designation
                )

        return {
            "id": emp.id,
            "name": getattr(emp, "employee_name", None) or getattr(emp, "name", None),
            "designation": designation,
            "email": getattr(emp, "email", None),
        }

    def get_totalItems(self, obj):
        total_quantity = 0
        for item in self.get_items(obj):
            try:
                total_quantity += int(item.get("quantity") or 0)
            except (AttributeError, TypeError, ValueError):
                continue
        return total_quantity

    def get_rfqNumber(self, obj):
        try:
            return obj.award.rfq.rfq_number if obj.award and obj.award.rfq else None
        except Exception:
            return None

    def get_csNumber(self, obj):
        try:
            return (
                obj.award.comparative_statement.cs_number
                if obj.award and obj.award.comparative_statement
                else None
            )
        except Exception:
            return None

    def get_awardId(self, obj):
        try:
            return obj.award_id if obj.award_id else None
        except Exception:
            return None

    def get_requisitionNumber(self, obj):
        try:
            rfq = obj.award.rfq if obj.award else None
            if rfq:
                req = rfq.requisitions.first()
                return req.requisition_no if req else None
        except Exception:
            return None

    def get_budgetCode(self, obj):
        if obj.award and obj.award.comparative_statement:
            if obj.award.comparative_statement.budget_code:
                return obj.award.comparative_statement.budget_code
        try:
            rfq = obj.award.rfq if obj.award else None
            if rfq:
                req = rfq.requisitions.first()
                if req and req.budget_code:
                    return getattr(req.budget_code, "code", None)
        except Exception:
            return None
        return None

    def get_project(self, obj):
        if obj.award and obj.award.comparative_statement:
            if obj.award.comparative_statement.project:
                return obj.award.comparative_statement.project
        try:
            rfq = obj.award.rfq if obj.award else None
            if rfq:
                req = rfq.requisitions.first()
                if req and req.project:
                    return getattr(req.project, "name", None)
        except Exception:
            return None
        return None

    def get_organization(self, obj):
        if obj.award:
            organization = obj.award.organization_info
            if isinstance(organization, dict):
                return organization
            try:
                rfq = obj.award.rfq
                if rfq:
                    req = rfq.requisitions.select_related(
                        "requesting_office",
                        "requesting_office__office_contact_person",
                    ).first()
                    if req and req.requesting_office:
                        office = req.requesting_office
                        contact_user = getattr(office, "office_contact_person", None)
                        return {
                            "name": office.name,
                            "contactPerson": getattr(contact_user, "username", None),
                            "email": office.email,
                            "phone": office.phone,
                            "address": office.address,
                        }
            except Exception:
                pass
        return None

    def _get_direct_vendor_info(self, obj):
        award = getattr(obj, "award", None)
        if not award or not getattr(award, "comparative_statement", None):
            return None

        cs = award.comparative_statement
        direct_quote = (
            cs.quotations.filter(is_direct_evaluation=True).order_by("-id").first()
        )
        if direct_quote is None:
            direct_quote = (
                cs.quotations.filter(vendor__isnull=True).order_by("-id").first()
            )
        if not direct_quote:
            return None

        return {
            "id": None,
            "name": direct_quote.direct_vendor_name,
            "contactPerson": direct_quote.direct_vendor_name,
            "email": direct_quote.direct_vendor_email,
            "phone": direct_quote.direct_vendor_phone,
            "address": direct_quote.direct_vendor_address,
            "is_direct_evaluation": True,
        }

    def get_vendor(self, obj):
        # Use Work Order's own vendor first (copied at creation time)
        # Only fall back to Award's vendor if Work Order has no vendor set
        vendor = None
        if obj.vendor:
            vendor = obj.vendor
        elif obj.award and obj.award.vendor_profile:
            vendor = obj.award.vendor_profile
        if vendor:
            return {
                "id": vendor.id,
                "name": vendor.name,
                "contactPerson": getattr(vendor, "contact_person", None),
                "email": getattr(vendor, "email", None),
                "phone": getattr(vendor, "phone", None),
                "address": getattr(vendor, "address", None),
                "is_direct_evaluation": False,
            }
        return self._get_direct_vendor_info(obj)

    def _build_items_from_direct_evaluation(self, obj):
        award = getattr(obj, "award", None)
        if not award or not getattr(award, "comparative_statement", None):
            return []

        cs = award.comparative_statement
        direct_quote = (
            cs.quotations.filter(is_direct_evaluation=True)
            .prefetch_related("quotation_items__item")
            .order_by("-id")
            .first()
        )
        if direct_quote is None:
            direct_quote = (
                cs.quotations.filter(vendor__isnull=True)
                .prefetch_related("quotation_items__item")
                .order_by("-id")
                .first()
            )
        if direct_quote is None:
            return []

        delivered_map = {}
        for line in obj.work_order_items.all():
            key = self._normalize_str(line.description)
            if key:
                delivered_map[key] = {
                    "delivered": line.delivered,
                    "deliveryStatus": line.item_delivery_status,
                }

        normalized = []
        for index, quotation_item in enumerate(
            direct_quote.quotation_items.select_related("item").all(), start=1
        ):
            item = getattr(quotation_item, "item", None)
            item_name = (
                getattr(item, "item_name", None) or getattr(item, "name", None) or ""
            )
            description = (
                getattr(item, "description", None)
                or item_name
                or getattr(quotation_item, "remarks", None)
                or ""
            )
            specification = getattr(item, "specifications", None) or ""
            unit = getattr(item, "unit", None) or ""
            quantity = float(quotation_item.quantity or 0)
            unit_price = float(quotation_item.unit_price or 0)
            total = float(quantity * unit_price)
            key = self._normalize_str(description)
            delivery = delivered_map.get(key, {})
            normalized.append(
                {
                    "id": quotation_item.item_id or index,
                    "name": item_name,
                    "description": description,
                    "specification": specification,
                    "unit": unit,
                    "quantity": quantity,
                    "unitPrice": unit_price,
                    "total": total,
                    "delivered": delivery.get("delivered", 0),
                    "deliveryStatus": delivery.get("deliveryStatus", "pending"),
                }
            )
        return normalized

    def get_items(self, obj):
        award = obj.award
        if not award:
            return []

        delivered_map = {}
        for line in obj.work_order_items.all():
            key = self._normalize_str(line.description)
            if key:
                delivered_map[key] = {
                    "delivered": line.delivered,
                    "deliveryStatus": line.item_delivery_status,
                }

        normalized_items = []
        raw_items = award.items or []
        for index, award_item in enumerate(raw_items, start=1):
            if not isinstance(award_item, dict):
                continue
            name = (
                award_item.get("name")
                or award_item.get("item_name")
                or award_item.get("itemName")
                or award_item.get("description")
            )
            description = award_item.get("description") or award_item.get("item_name")
            specification = award_item.get("specification")
            quantity = award_item.get("quantity")
            if quantity is None and award.rfq:
                for rfq_line in award.rfq.line_items.all():
                    if self._normalize_str(rfq_line.item_name) == self._normalize_str(
                        description
                    ):
                        quantity = getattr(rfq_line, "quantity", None)
                        break
            unit_price = award_item.get("unitPrice")
            if unit_price is None:
                unit_price = award_item.get("unit_price")
            total = award_item.get("total")
            try:
                if total is None and quantity is not None and unit_price is not None:
                    total = float(quantity) * float(unit_price)
            except (TypeError, ValueError):
                total = award_item.get("total")
            key = self._normalize_str(description)
            delivery = delivered_map.get(key, {})
            normalized_items.append(
                {
                    "id": award_item.get("id") or award_item.get("itemId") or index,
                    "name": name,
                    "description": description,
                    "specification": specification,
                    "unit": award_item.get("unit"),
                    "quantity": quantity or 0,
                    "unitPrice": unit_price,
                    "total": total,
                    "delivered": delivery.get("delivered", 0),
                    "deliveryStatus": delivery.get("deliveryStatus", "pending"),
                }
            )

        if normalized_items:
            return normalized_items
        return self._build_items_from_direct_evaluation(obj)

    def get_termsAndConditions(self, obj):
        if obj.terms_and_conditions:
            return [obj.terms_and_conditions]
        return [""]

    def get_deliveredItems(self, obj):
        from django.db.models import Sum as DSum

        result = obj.work_order_items.aggregate(total=DSum("delivered"))
        return result["total"] or 0


# ── Write serializer ─────────────────────────────────────────────────────────


class WorkOrderCreateSerializer(serializers.ModelSerializer):
    work_order_items = WorkOrderItemCreateSerializer(many=True, required=False)
    approval_history = WorkOrderApprovalHistorySerializer(many=True, required=False)
    notification_log = WorkOrderNotificationLogSerializer(many=True, required=False)

    workOrderNumber = serializers.CharField(source="wo_number", read_only=True)

    approver = serializers.PrimaryKeyRelatedField(
        read_only=True,
        help_text="Auto-assigned from the Approval Matrix (Work Order module).",
    )

    vendor = serializers.PrimaryKeyRelatedField(
        read_only=True,
    )

    class Meta:
        model = WorkOrder
        fields = [
            "id",
            "workOrderNumber",
            "award",
            "vendor",
            "title",
            "category",
            "order_date",
            "delivery_date",
            "acceptance_deadline",
            "delivery_address",
            "payment_terms",
            "warranty_period",
            "tc_template",
            "amount_paid",
            "terms_and_conditions",
            "special_instructions",
            "status",
            "approval_status",
            "vendor_status",
            "vendor_acceptance_date",
            "delivery_status",
            "payment_status",
            "auto_generated",
            "approval_level",
            "notification_sent",
            "notification_channel",
            "approver",
            "work_order_items",
            "approval_history",
            "notification_log",
        ]

    def _populate_award_item_values(self, work_order, item_data):
        award_item = _find_award_item(
            work_order.award if work_order else None, item_data=item_data
        )
        if not award_item:
            return item_data

        item_data["description"] = award_item.get("description") or award_item.get(
            "item_name"
        )
        item_data["specification"] = award_item.get("specification")
        return item_data

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("work_order_items", [])
        approval_data = validated_data.pop("approval_history", [])
        notif_data = validated_data.pop("notification_log", [])
        request = self.context.get("request")
        validated_data["created_by"] = request.user if request else None
        award = validated_data.get("award")
        if award and getattr(award, "vendor_profile", None):
            validated_data["vendor"] = award.vendor_profile
        wo = WorkOrder.objects.create(**validated_data)
        for item_data in items_data:
            item_data = self._populate_award_item_values(wo, item_data)
            WorkOrderItem.objects.create(work_order=wo, **item_data)
        for entry in approval_data:
            WorkOrderApprovalHistory.objects.create(work_order=wo, **entry)
        for entry in notif_data:
            WorkOrderNotificationLog.objects.create(work_order=wo, **entry)
        wo.calculate_total_amount()
        return wo

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop("work_order_items", None)
        approval_data = validated_data.pop("approval_history", None)
        notif_data = validated_data.pop("notification_log", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.work_order_items.all().delete()
            for item_data in items_data:
                item_data = self._populate_award_item_values(instance, item_data)
                WorkOrderItem.objects.create(work_order=instance, **item_data)
        if approval_data is not None:
            instance.approval_history.all().delete()
            for entry in approval_data:
                WorkOrderApprovalHistory.objects.create(work_order=instance, **entry)
        if notif_data is not None:
            # Append only – never wipe auto-created system logs
            for entry in notif_data:
                WorkOrderNotificationLog.objects.create(work_order=instance, **entry)
        instance.calculate_total_amount()
        return instance


class VendorAcceptanceSerializer(serializers.ModelSerializer):
    wo_number = serializers.CharField(source="work_order.wo_number", read_only=True)
    cs_number = serializers.SerializerMethodField()
    rfq_number = serializers.SerializerMethodField()

    class Meta:
        model = VendorAcceptance
        fields = [
            "id",
            "work_order",
            "wo_number",
            "cs_number",
            "rfq_number",
            "status",
            "response_date",
            "remarks",
            "attachment",
            "rejected_vendor",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_cs_number(self, obj):
        try:
            award = obj.work_order.award if obj.work_order else None
            cs = award.comparative_statement if award else None
            return cs.cs_number if cs else None
        except Exception:
            return None

    def get_rfq_number(self, obj):
        try:
            award = obj.work_order.award if obj.work_order else None
            rfq = award.rfq if award else None
            return rfq.rfq_number if rfq else None
        except Exception:
            return None
