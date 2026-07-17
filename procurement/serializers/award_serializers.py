from rest_framework import serializers
from django.utils import timezone
from ..models.award_models import Award, AwardNotification


def _get_award_submission(obj):
    comparative_statement = getattr(obj, "comparative_statement", None)
    rfq = getattr(comparative_statement, "rfq", None) or getattr(obj, "rfq", None)
    if comparative_statement is None or rfq is None:
        return None

    vendor_profile = getattr(obj, "vendor_profile", None) or getattr(
        comparative_statement, "recommended_vendor", None
    )
    submissions = rfq.vendor_submissions.select_related(
        "financial_proposal"
    ).prefetch_related("financial_proposal__items")

    vendor_ids = []
    for vendor_id in (
        getattr(vendor_profile, "id", None),
        getattr(comparative_statement, "recommended_vendor_id", None),
    ):
        if vendor_id and vendor_id not in vendor_ids:
            vendor_ids.append(vendor_id)

    for vendor_id in vendor_ids:
        submission = submissions.filter(vendor_id=vendor_id).first()
        if submission is not None:
            return submission

    vendor_names = []
    if vendor_profile is not None:
        vendor_user = getattr(vendor_profile, "user", None)
        if getattr(vendor_user, "username", None):
            vendor_names.append(vendor_user.username)
        if getattr(vendor_profile, "name", None):
            vendor_names.append(vendor_profile.name)

    for vendor_name in vendor_names:
        submission = submissions.filter(vendor_name=vendor_name).first()
        if submission is not None:
            return submission

    return None


def _build_items_from_financial_proposal(obj):
    submission = _get_award_submission(obj)
    financial_proposal = getattr(submission, "financial_proposal", None)
    if financial_proposal is None:
        return []

    comparative_statement = getattr(obj, "comparative_statement", None)
    rfq = getattr(comparative_statement, "rfq", None) or getattr(obj, "rfq", None)
    rfq_line_items = (
        {line_item.id: line_item for line_item in rfq.line_items.all()} if rfq else {}
    )

    items = []
    for financial_item in financial_proposal.items.all():
        rfq_line_item = rfq_line_items.get(financial_item.line_item_id)
        item_name = (
            financial_item.item_name
            or getattr(rfq_line_item, "item_name", None)
            or financial_item.description
            or ""
        )
        description = (
            financial_item.description
            or getattr(rfq_line_item, "item_name", None)
            or item_name
        )
        quantity = (
            financial_item.qty
            if getattr(financial_item, "qty", None) is not None
            else getattr(rfq_line_item, "quantity", None)
        )
        unit_price = float(financial_item.unit_price)
        total = float(financial_item.total)
        specification = getattr(rfq_line_item, "specification", "") or ""
        unit = financial_item.unit or getattr(rfq_line_item, "unit", None)

        items.append(
            {
                "line_item_id": financial_item.line_item_id,
                "item_id": financial_item.line_item_id,
                "name": item_name,
                "item_name": item_name,
                "description": description,
                "specification": specification,
                "quantity": float(quantity or 0),
                "qty": float(quantity or 0),
                "unit": unit,
                "unitPrice": unit_price,
                "unit_price": unit_price,
                "total": total,
                "total_price": total,
            }
        )

    return items


def _build_items_from_direct_evaluation(obj):
    cs = getattr(obj, "comparative_statement", None)
    if cs is None:
        return []

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

    items = []
    for quotation_item in direct_quote.quotation_items.select_related("item").all():
        item = getattr(quotation_item, "item", None)
        item_name = (
            getattr(item, "item_name", None) or getattr(item, "name", None) or ""
        )
        description = (
            getattr(item, "description", None)
            or item_name
            or quotation_item.remarks
            or ""
        )
        specification = getattr(item, "specifications", None) or ""
        unit = getattr(item, "unit", None) or ""
        quantity = float(quotation_item.quantity or 0)
        unit_price = float(quotation_item.unit_price or 0)
        total = float(quotation_item.quantity * quotation_item.unit_price)

        items.append(
            {
                "line_item_id": quotation_item.item_id,
                "item_id": quotation_item.item_id,
                "name": item_name,
                "item_name": item_name,
                "description": description,
                "specification": specification,
                "quantity": quantity,
                "qty": quantity,
                "unit": unit,
                "unitPrice": unit_price,
                "unit_price": unit_price,
                "total": total,
                "total_price": total,
            }
        )

    return items


def _normalize_raw_award_item(item):
    name = (
        item.get("name")
        or item.get("item_name")
        or item.get("itemName")
        or item.get("description")
        or ""
    )
    description = (
        item.get("description") or item.get("item_name") or item.get("itemName") or name
    )
    quantity = item.get("quantity")
    if quantity is None:
        quantity = item.get("qty")
    unit_price = item.get("unitPrice")
    if unit_price is None:
        unit_price = item.get("unit_price")
    total = item.get("total")
    if total is None:
        total = item.get("total_price")
    if total is None and quantity is not None and unit_price is not None:
        try:
            total = float(quantity) * float(unit_price)
        except (TypeError, ValueError):
            total = None

    return {
        "line_item_id": item.get("line_item_id") or item.get("item_id"),
        "item_id": item.get("item_id") or item.get("line_item_id"),
        "name": name,
        "item_name": item.get("item_name") or item.get("itemName") or name,
        "description": description,
        "specification": item.get("specification") or "",
        "quantity": quantity,
        "qty": quantity,
        "unit": item.get("unit"),
        "unitPrice": unit_price,
        "unit_price": unit_price,
        "total": total,
        "total_price": total,
    }


class AwardSerializer(serializers.ModelSerializer):
    """
    Full award serializer — output matches the frontend's expected structure.
    Computed / relational fields are exposed with camelCase aliases.
    """

    # ── identity ──────────────────────────────────────────────────
    award_number = serializers.CharField(read_only=True)
    rfqNumber = serializers.CharField(source="rfq.rfq_number", read_only=True)
    csNumber = serializers.CharField(
        source="comparative_statement.cs_number", read_only=True
    )
    requisitionNumber = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()

    # ── financial ─────────────────────────────────────────────────
    awardedAmount = serializers.DecimalField(
        source="total_amount", max_digits=15, decimal_places=2, read_only=True
    )
    approvedAmount = serializers.DecimalField(
        source="approved_amount",
        max_digits=15,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    savings = serializers.SerializerMethodField()
    savingsPercentage = serializers.SerializerMethodField()
    amountPaid = serializers.DecimalField(
        source="amount_paid", max_digits=15, decimal_places=2, read_only=True
    )

    # ── dates ─────────────────────────────────────────────────────
    awardDate = serializers.DateField(source="award_date", read_only=True)
    notificationDate = serializers.DateField(source="notification_date", read_only=True)
    responseDeadline = serializers.DateField(source="response_deadline", read_only=True)
    validFrom = serializers.DateField(source="valid_from", read_only=True)
    validUntil = serializers.DateField(source="valid_until", read_only=True)
    acceptanceDate = serializers.DateField(source="acceptance_date", read_only=True)
    completionDate = serializers.DateField(source="completion_date", read_only=True)

    # ── contract detail aliases ───────────────────────────────────
    validityPeriod = serializers.CharField(source="validity_period", read_only=True)
    deliveryTimeline = serializers.CharField(source="delivery_timeline", read_only=True)
    deliveryAddress = serializers.CharField(source="delivery_address", read_only=True)
    paymentTerms = serializers.CharField(source="payment_terms", read_only=True)
    warrantyPeriod = serializers.CharField(source="warranty_period", read_only=True)

    # ── status aliases ────────────────────────────────────────────
    notificationStatus = serializers.CharField(
        source="notification_status", read_only=True
    )
    acceptanceStatus = serializers.CharField(source="acceptance_status", read_only=True)
    deliveryStatus = serializers.CharField(source="delivery_status", read_only=True)
    deliveryProgress = serializers.IntegerField(
        source="delivery_progress", read_only=True
    )
    paymentStatus = serializers.CharField(source="payment_status", read_only=True)

    # ── item counts ───────────────────────────────────────────────
    totalItems = serializers.IntegerField(source="total_items", read_only=True)
    deliveredItems = serializers.IntegerField(source="delivered_items", read_only=True)

    # ── rich objects ──────────────────────────────────────────────
    organization = serializers.SerializerMethodField()
    vendor = serializers.SerializerMethodField()
    contactInfo = serializers.JSONField(source="contact_info", read_only=True)
    deliverySchedule = serializers.JSONField(source="delivery_schedule", read_only=True)
    items = serializers.SerializerMethodField()
    approvers = serializers.SerializerMethodField()

    class Meta:
        model = Award
        fields = [
            # identity
            "id",
            "award_number",
            "rfqNumber",
            "csNumber",
            "requisitionNumber",
            "title",
            "description",
            "category",
            # org / vendor
            "organization",
            "vendor",
            # financial
            "awardedAmount",
            "approvedAmount",
            "savings",
            "savingsPercentage",
            # dates
            "awardDate",
            "notificationDate",
            "responseDeadline",
            "validFrom",
            "validUntil",
            # contract detail
            "validityPeriod",
            "deliveryTimeline",
            "deliveryAddress",
            "paymentTerms",
            "warrantyPeriod",
            # status
            "status",
            "notificationStatus",
            "acceptanceStatus",
            "acceptanceDate",
            "deliveryStatus",
            "deliveryProgress",
            "completionDate",
            "paymentStatus",
            "amountPaid",
            # items
            "items",
            "totalItems",
            "deliveredItems",
            # structured
            "terms",
            "deliverySchedule",
            "approvers",
            "contactInfo",
            # internal / audit (kept for admin use)
            "comparative_statement",
            "rfq",
            "vendor_profile",
            "justification",
            "terms_and_conditions",
            "awarded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id" "award_number",
            "rfqNumber",
            "csNumber",
            "savings",
            "savingsPercentage",
            "vendor",
            "approvers",
            "awarded_by",
            "created_at",
            "updated_at",
        ]

    def get_savings(self, obj):
        if obj.approved_amount and obj.total_amount is not None:
            return float(obj.approved_amount) - float(obj.total_amount)
        return None

    def get_savingsPercentage(self, obj):
        savings = self.get_savings(obj)
        if savings is not None and obj.approved_amount:
            try:
                return round((savings / float(obj.approved_amount)) * 100, 2)
            except ZeroDivisionError:
                return None
        return None

    def get_description(self, obj):
        cs_description = getattr(obj.comparative_statement, "description", None)
        if cs_description:
            return cs_description
        return getattr(obj.rfq, "description", None)

    def get_category(self, obj):
        rfq = getattr(obj, "rfq", None)
        if rfq is None:
            rfq = getattr(getattr(obj, "comparative_statement", None), "rfq", None)
        if rfq is None:
            return None
        return getattr(getattr(rfq, "rfq_category", None), "name", None)

    def get_requisitionNumber(self, obj):
        try:
            rfq = obj.rfq
            if rfq:
                req = rfq.requisitions.first()
                return req.requisition_no if req else None
        except Exception:
            return None
        return None

    def get_items(self, obj):
        financial_proposal_items = _build_items_from_financial_proposal(obj)
        if financial_proposal_items:
            return financial_proposal_items

        raw_items = obj.items or []
        normalized = []
        for item in raw_items:
            if isinstance(item, dict):
                normalized.append(_normalize_raw_award_item(item))
        if normalized:
            return normalized

        return _build_items_from_direct_evaluation(obj)

    def get_organization(self, obj):
        organization = obj.organization_info or {}
        office = None

        if obj.rfq:
            req = obj.rfq.requisitions.select_related(
                "requesting_office", "requesting_office__office_contact_person"
            ).first()
            if req and req.requesting_office:
                office = req.requesting_office
            else:
                li = obj.rfq.line_items.select_related(
                    "requisition__requesting_office",
                    "requisition__requesting_office__office_contact_person",
                ).first()
                if li and li.requisition and li.requisition.requesting_office:
                    office = li.requisition.requesting_office

        if office:
            contact_user = getattr(office, "office_contact_person", None)
            return {
                "id": office.id,
                "name": office.name,
                "contactPerson": contact_user.username if contact_user else None,
                "email": office.email,
                "phone": office.phone,
                "address": office.address,
            }

        if isinstance(organization, dict):
            return organization
        return None

    def _get_direct_vendor_info(self, obj):
        cs = getattr(obj, "comparative_statement", None)
        if cs is None:
            return None

        direct_quote = (
            cs.quotations.filter(is_direct_evaluation=True).order_by("-id").first()
        )
        if direct_quote is None:
            direct_quote = (
                cs.quotations.filter(vendor__isnull=True).order_by("-id").first()
            )
        if direct_quote is None:
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
        vp = obj.vendor_profile
        if vp:
            return {
                "id": vp.id,
                "name": vp.name,
                "contactPerson": getattr(vp, "contact_person", None),
                "email": getattr(vp, "email", None),
                "phone": getattr(vp, "phone", None),
                "address": getattr(vp, "address", None),
                "is_direct_evaluation": False,
            }

        return self._get_direct_vendor_info(obj)

    def get_approvers(self, obj):
        cs = obj.comparative_statement
        if not cs:
            return []
        result = []
        for wf in cs.approval_workflow.all():
            result.append(
                {
                    "name": wf.approver_name or "",
                    "role": wf.role or "",
                    "date": wf.date.strftime("%Y-%m-%d") if wf.date else None,
                    "status": wf.status or "",
                }
            )
        return result

    def get_category(self, obj):
        rfq = getattr(obj, "rfq", None)
        if rfq is None:
            rfq = getattr(getattr(obj, "comparative_statement", None), "rfq", None)
        if rfq is None:
            return None
        return getattr(getattr(rfq, "rfq_category", None), "name", None)


class AwardWriteSerializer(serializers.ModelSerializer):
    """Writable serializer for manual create/update of awards via the API."""

    acceptanceStatus = serializers.CharField(source="acceptance_status", required=False)

    class Meta:
        model = Award
        fields = [
            "comparative_statement",
            "rfq",
            "vendor_profile",
            "title",
            "description",
            "total_amount",
            "approved_amount",
            "amount_paid",
            "award_date",
            "notification_date",
            "response_deadline",
            "valid_from",
            "valid_until",
            "validity_period",
            "delivery_timeline",
            "delivery_address",
            "payment_terms",
            "warranty_period",
            "justification",
            "terms_and_conditions",
            "status",
            "notification_status",
            "acceptanceStatus",
            "acceptance_date",
            "delivery_status",
            "delivery_progress",
            "completion_date",
            "payment_status",
            "total_items",
            "delivered_items",
            "items",
            "terms",
            "delivery_schedule",
            "organization_info",
            "contact_info",
        ]


class SimpleAwardSerializer(serializers.ModelSerializer):
    """Minimal award serializer for the simple_award extra action."""

    rfqNumber = serializers.CharField(source="rfq.rfq_number", read_only=True)
    csNumber = serializers.CharField(
        source="comparative_statement.cs_number", read_only=True
    )
    status = serializers.CharField(read_only=True)
    acceptanceStatus = serializers.CharField(source="acceptance_status", read_only=True)
    vendor = serializers.SerializerMethodField()

    class Meta:
        model = Award
        fields = [
            "id",
            "award_number",
            "rfqNumber",
            "csNumber",
            "title",
            "status",
            "acceptanceStatus",
            "vendor",
        ]

    def get_vendor(self, obj):
        vp = obj.vendor_profile
        if vp:
            return {
                "id": vp.id,
                "name": vp.name,
                "contactPerson": getattr(vp, "contact_person", None),
                "email": getattr(vp, "email", None),
                "phone": getattr(vp, "phone", None),
                "address": getattr(vp, "address", None),
                "is_direct_evaluation": False,
            }
        cs = getattr(obj, "comparative_statement", None)
        if not cs:
            return None
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


class AwardNotificationSerializer(serializers.ModelSerializer):
    award_number = serializers.CharField(source="award.award_number", read_only=True)
    vendor_profile_name = serializers.CharField(
        source="vendor_profile.name", read_only=True
    )

    class Meta:
        model = AwardNotification
        fields = [
            "id",
            "award",
            "award_number",
            "vendor_profile",
            "vendor_profile_name",
            "notification_type",
            "sent_date",
            "message",
            "is_sent",
            "is_acknowledged",
            "acknowledged_date",
            "created_at",
        ]
        read_only_fields = ["created_at"]
