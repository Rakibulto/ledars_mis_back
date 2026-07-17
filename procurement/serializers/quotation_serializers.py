from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from django.db import transaction
from ..models.quotation_models import VendorQuotation, QuotationItem, QuotationOpening
from ..models.rfq_models import RFQ
from vendorportal.models.models import VendorProfile
from vendorportal.models.apply_rfq_models import VendorRFQSubmission
from ..models.comparative_models import ComparativeVendorEvaluation


class QuotationItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = QuotationItem
        fields = [
            "id",
            "quotation",
            "item",
            "item_code",
            "item_name",
            "unit",
            "quantity",
            "unit_price",
            "total_price",
            "remarks",
        ]
        read_only_fields = ["id"]

    def get_total_price(self, obj):
        return obj.quantity * obj.unit_price


class VendorQuotationSerializer(serializers.ModelSerializer):
    vendor_name = serializers.SerializerMethodField()
    rfq_number = serializers.CharField(source="rfq.rfq_number", read_only=True)
    quotation_items = QuotationItemSerializer(many=True, read_only=True)
    items_count = serializers.IntegerField(
        source="quotation_items.count", read_only=True
    )
    invited_vendors_count = serializers.IntegerField(
        source="rfq.vendors_count", read_only=True
    )
    total_price_proposal = serializers.SerializerMethodField()

    def get_vendor_name(self, obj):
        if obj.vendor:
            return obj.vendor.name
        return obj.direct_vendor_name

    def get_total_price_proposal(self, obj):
        if obj.price_proposal:
            total = sum(
                item.get("proposed_price", 0) * item.get("quantity", 0)
                for item in obj.price_proposal
            )
            return total
        return 0

    class Meta:
        model = VendorQuotation
        fields = [
            "id",
            "quotation_number",
            "rfq",
            "rfq_number",
            "invited_vendors_count",
            "vendor",
            "vendor_name",
            "is_direct_evaluation",
            "direct_vendor_name",
            "direct_vendor_email",
            "direct_vendor_phone",
            "direct_vendor_address",
            "direct_evaluation_justification",
            "submission_date",
            "validity_date",
            "total_amount",
            "discount_percentage",
            "tax_amount",
            "grand_total",
            "delivery_terms",
            "payment_terms",
            "warranty_terms",
            "remarks",
            "status",
            "price_proposal",
            "total_price_proposal",
            "attachment",
            "quotation_items",
            "items_count",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "quotation_number",
            "total_amount",
            "grand_total",
            "created_by",
            "created_at",
            "updated_at",
        ]


class VendorQuotationCreateSerializer(serializers.ModelSerializer):
    quotation_items = QuotationItemSerializer(many=True)
    quotation_number = serializers.CharField(read_only=True)

    class Meta:
        model = VendorQuotation
        fields = [
            "id",
            "quotation_number",
            "rfq",
            "vendor",
            "validity_date",
            "discount_percentage",
            "tax_amount",
            "delivery_terms",
            "payment_terms",
            "warranty_terms",
            "remarks",
            "price_proposal",
            "attachment",
            "quotation_items",
        ]

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("quotation_items", [])
        request = self.context.get("request")
        validated_data["created_by"] = request.user if request else None
        quotation = VendorQuotation.objects.create(**validated_data)
        for item_data in items_data:
            item_data.pop("quotation", None)
            QuotationItem.objects.create(quotation=quotation, **item_data)
        quotation.calculate_totals()
        return quotation

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop("quotation_items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.quotation_items.all().delete()
            for item_data in items_data:
                item_data.pop("quotation", None)
                QuotationItem.objects.create(quotation=instance, **item_data)
        instance.calculate_totals()
        return instance


class QuotationOpeningSerializer(serializers.ModelSerializer):
    rfq_number = serializers.CharField(source="rfq.rfq_number", read_only=True)

    class Meta:
        model = QuotationOpening
        fields = [
            "id",
            "rfq",
            "rfq_number",
            "opening_date",
            "venue",
            "committee_members",
            "status",
            "minutes",
            "opened_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["opened_by", "created_at", "updated_at"]


# ─── RFQ-aggregate Quotation Read Serializer ─────────────────────────────────


class VendorQuotationRFQSerializer(serializers.Serializer):
    """Returns one entry per RFQ with all vendor submissions nested, matching mockQuotationData."""

    id = serializers.SerializerMethodField()
    quotationNumber = serializers.SerializerMethodField()
    rfqNumber = serializers.SerializerMethodField()
    invited_vendors_count = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    deadline = serializers.SerializerMethodField()
    publishedDate = serializers.SerializerMethodField()
    openedDate = serializers.SerializerMethodField()
    openedBy = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    estimatedValue = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    evaluationCriteria = serializers.SerializerMethodField()
    requiredDocuments = serializers.SerializerMethodField()
    vendors = serializers.SerializerMethodField()

    def get_id(self, obj):
        return obj.id

    def get_quotationNumber(self, obj):
        # Return the most recent VendorQuotation number linked to this RFQ.
        q = obj.vendor_quotations.order_by("-created_at").first()
        if q and q.quotation_number:
            return q.quotation_number

        # Fallback: if there are submitted vendor submissions but no quotation yet,
        # create a VendorQuotation so the RFQ can show a generated quotation number.
        submission = (
            obj.vendor_submissions.filter(status="submitted")
            .order_by("-submitted_at", "-created_at")
            .first()
        )
        if not submission:
            return None

        vendor_profile = VendorProfile.objects.filter(id=submission.vendor_id).first()
        quotation, created = VendorQuotation.objects.get_or_create(
            rfq=obj,
            vendor=vendor_profile,
            defaults={
                "submission_date": submission.submitted_at or timezone.now(),
                "status": "Submitted",
            },
        )
        return quotation.quotation_number

    def get_rfqNumber(self, obj):
        return obj.rfq_number

    def get_title(self, obj):
        return obj.rfq_title

    def get_deadline(self, obj):
        return obj.submission_deadline

    def get_publishedDate(self, obj):
        return obj.published_at or obj.created_at

    def _get_opening(self, obj):
        try:
            return obj.opening
        except Exception:
            return None

    def get_openedDate(self, obj):
        opening = self._get_opening(obj)
        return opening.opening_date if opening else None

    def get_openedBy(self, obj):
        opening = self._get_opening(obj)
        if not opening or not opening.opened_by:
            return None
        user = opening.opened_by
        full_name = (getattr(user, "get_full_name", lambda: None)() or "").strip()
        return full_name or user.username

    def get_status(self, obj):
        opening = self._get_opening(obj)
        if opening and opening.status:
            return opening.status
        if obj.status:
            return obj.get_status_display()
        return "Under Review"

    def get_category(self, obj):
        return obj.rfq_category.name if obj.rfq_category_id else None

    def get_estimatedValue(self, obj):
        return float(obj.total_estimated_value) if obj.total_estimated_value else None

    def get_invited_vendors_count(self, obj):
        return obj.vendors_count

    def get_currency(self, obj):
        return None  # No currency field on RFQ yet

    def get_evaluationCriteria(self, obj):
        return {"technical": 100, "financial": 100}

    def get_requiredDocuments(self, obj):
        return obj.required_documents or []

    def get_vendors(self, obj):
        # Required documents defined on the RFQ (list of strings)
        rfq_required_docs = [str(d).strip() for d in (obj.required_documents or [])]
        total_required = len(rfq_required_docs)

        submissions = list(
            obj.vendor_submissions.all()
            .select_related("financial_proposal")
            .prefetch_related("financial_proposal__items", "documents")
        )
        if not submissions:
            return []

        # Batch-load VendorProfiles (vendor_id is a denormalized int)
        vendor_ids = [s.vendor_id for s in submissions if s.vendor_id]
        vendor_names = [s.vendor_name for s in submissions if s.vendor_name]
        profiles_qs = (
            VendorProfile.objects.filter(
                Q(id__in=vendor_ids)
                | Q(rfq_invitations__rfq=obj, user__username__in=vendor_names)
                | Q(rfq_invitations__rfq=obj, name__in=vendor_names)
            )
            .distinct()
            .select_related("user")
        )

        profiles = {p.id: p for p in profiles_qs}
        profile_name_map = {}
        for p in profiles_qs:
            if p.user and p.user.username:
                profile_name_map[p.user.username.lower()] = p
            if p.name:
                profile_name_map[p.name.lower()] = p

        # Batch-load VendorQuotation numbers keyed by vendor_id (VendorProfile.id)
        quotation_map = {
            q.vendor_id: q.quotation_number
            for q in obj.vendor_quotations.only("vendor_id", "quotation_number")
        }

        # Build evaluation map from comparative statements (prefetched on queryset)
        eval_map = {}
        for cs in obj.comparative_statements.all():
            for ev in cs.vendor_evaluations.all():
                eval_map[ev.vendor_id] = ev

        # Compute min price for financial score normalisation
        totals = []
        for sub in submissions:
            fp = getattr(sub, "financial_proposal", None)
            totals.append(float(fp.grand_total) if fp else 0)
        min_price = min((t for t in totals if t > 0), default=0)

        vendor_list = []
        for sub in submissions:
            profile = profiles.get(sub.vendor_id)
            if not profile and sub.vendor_name:
                profile = profile_name_map.get(sub.vendor_name.lower())

            fp = getattr(sub, "financial_proposal", None)
            ev = eval_map.get(sub.vendor_id)

            grand_total = float(fp.grand_total) if fp else 0
            sub_total = float(fp.sub_total) if fp else 0
            vat = float(fp.vat) if fp else 0
            delivery = float(fp.delivery_charge) if fp else 0
            installation = max(round(grand_total - sub_total - vat - delivery, 2), 0)

            # ── Document-based Technical Score (0-100) ───────────────────────
            # Score = (required docs submitted by vendor / total required docs) × 100
            submitted_doc_names = {doc.doc_name.strip() for doc in sub.documents.all()}

            if total_required > 0:
                per_doc_score = round(100 / total_required, 2)
                matched = sum(
                    1 for req in rfq_required_docs if req in submitted_doc_names
                )
                technical_score = round((matched / total_required) * 100, 1)
                # Per-document criteria for the frontend checklist
                technical_criteria = {}
                for req in rfq_required_docs:
                    key = req.lower().replace(" ", "_").replace("/", "_")
                    uploaded = req in submitted_doc_names
                    technical_criteria[key] = {
                        "score": per_doc_score if uploaded else 0,
                        "maxScore": per_doc_score,
                        "comment": "Uploaded" if uploaded else "Missing",
                        "doc_name": req,
                        "uploaded": uploaded,
                    }
            else:
                # No required docs defined on RFQ — score by raw document count
                technical_score = 100.0 if submitted_doc_names else 0.0
                technical_criteria = {
                    doc.doc_name.lower().replace(" ", "_"): {
                        "score": 1,
                        "maxScore": 1,
                        "comment": "Uploaded",
                        "doc_name": doc.doc_name,
                        "uploaded": True,
                    }
                    for doc in sub.documents.all()
                }

            # ── Financial Score (0-100): lowest price → 100 pts ──────────────
            financial_score = (
                round(min_price / grand_total * 100, 1)
                if grand_total > 0 and min_price > 0
                else None
            )

            # ── Overall Score: 50% technical + 50% financial ─────────────────
            overall_score = None
            if financial_score is not None:
                overall_score = round(technical_score * 0.5 + financial_score * 0.5, 1)
            else:
                overall_score = round(technical_score * 0.5, 1)

            # Financial line items
            financial_items = []
            if fp:
                for fi in fp.items.all():
                    financial_items.append(
                        {
                            "name": fi.item_name,
                            "quantity": fi.qty,
                            "unitPrice": float(fi.unit_price),
                            "total": float(fi.total),
                        }
                    )

            # Submission documents / attachments
            docs = [
                {
                    "id": str(doc.id),
                    "name": doc.doc_name,
                    "file": doc.file.url if doc.file else None,
                    "type": doc.doc_type,
                }
                for doc in sub.documents.all()
            ]

            # VendorQuotation.vendor is now FK to VendorProfile, so key matches sub.vendor_id directly
            quotation_number = quotation_map.get(sub.vendor_id)
            if not quotation_number and profile:
                quotation_number = quotation_map.get(profile.id)
            if not quotation_number:
                quotation_number = self.get_quotationNumber(obj)

            vendor_list.append(
                {
                    "id": (
                        str(profile.id)
                        if profile
                        else (str(sub.vendor_id) if sub.vendor_id else str(sub.id))
                    ),
                    "quotationNumber": quotation_number,
                    "name": sub.vendor_name,
                    "registrationNumber": (
                        profile.trade_license_number if profile else None
                    ),
                    "contactPerson": profile.contact_person if profile else None,
                    "email": profile.email if profile else None,
                    "phone": profile.phone if profile else None,
                    "submissionDate": sub.submitted_at,
                    "totalPrice": grand_total,
                    "technicalScore": technical_score,
                    "financialScore": financial_score,
                    "overallScore": overall_score,
                    "status": sub.status,
                    "technical": technical_criteria,
                    "financial": {
                        "items": financial_items,
                        "subtotal": sub_total,
                        "tax": vat,
                        "delivery": delivery,
                        "installation": installation,
                        "total": grand_total,
                        "paymentTerms": fp.payment_terms if fp else None,
                        "deliveryTime": (
                            f"{fp.delivery_lead_time_days} days"
                            if fp and fp.delivery_lead_time_days
                            else None
                        ),
                        "warrantyPeriod": sub.warranty_period,
                    },
                    "attachments": docs,
                }
            )

        # Sort by overallScore descending (highest combined score = rank 1)
        vendor_list.sort(key=lambda v: (v["overallScore"] or 0), reverse=True)
        for i, v in enumerate(vendor_list, 1):
            v["rank"] = i

        return vendor_list


# ─── Direct Evaluation Serializers ───────────────────────────────────────────


class DirectEvaluationItemSerializer(serializers.Serializer):
    """One line-item in a direct-evaluation quote."""

    item_id = serializers.IntegerField(required=False, allow_null=True)
    item_name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    specification = serializers.CharField(required=False, allow_blank=True, default="")
    unit = serializers.CharField(required=False, allow_blank=True, default="")
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        attrs["total"] = attrs["quantity"] * attrs["unit_price"]
        return attrs


class DirectEvaluationSerializer(serializers.Serializer):
    """Payload for the direct-evaluation endpoint.

    VendorProfile FK is optional for existing vendors; manual vendor contact
    info is required only when no existing vendor is selected.
    """

    rfq = serializers.PrimaryKeyRelatedField(queryset=RFQ.objects.all())
    vendor_id = serializers.PrimaryKeyRelatedField(
        queryset=VendorProfile.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    vendor_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    vendor_email = serializers.EmailField(required=False, allow_blank=True, default="")
    vendor_phone = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )
    vendor_address = serializers.CharField(required=False, allow_blank=True, default="")
    justification = serializers.CharField(required=False, allow_blank=True, default="")
    delivery_terms = serializers.CharField(required=False, allow_blank=True, default="")
    payment_terms = serializers.CharField(required=False, allow_blank=True, default="")
    warranty_terms = serializers.CharField(required=False, allow_blank=True, default="")
    validity_date = serializers.DateField(required=False, allow_null=True, default=None)
    discount_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, default=0, min_value=0, max_value=100
    )
    tax_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, default=0, min_value=0
    )
    items = DirectEvaluationItemSerializer(many=True, min_length=1)

    def validate(self, attrs):
        vendor = attrs.get("vendor_id")
        vendor_name = attrs.get("vendor_name", "") or ""
        vendor_email = attrs.get("vendor_email", "") or ""

        if not vendor:
            errors = {}
            if not vendor_name.strip():
                errors["vendor_name"] = ["This field is required."]
            if not vendor_email.strip():
                errors["vendor_email"] = ["This field is required."]
            if errors:
                raise serializers.ValidationError(errors)
        else:
            attrs["vendor"] = attrs.pop("vendor_id")

        return attrs


class DirectEvaluationResponseSerializer(serializers.ModelSerializer):
    """Read-only response returned after a successful direct evaluation submission."""

    rfq_number = serializers.CharField(source="rfq.rfq_number", read_only=True)
    award_number = serializers.SerializerMethodField()
    award_id = serializers.SerializerMethodField()
    vendor = serializers.SerializerMethodField()

    class Meta:
        model = VendorQuotation
        fields = [
            "id",
            "quotation_number",
            "rfq",
            "rfq_number",
            "is_direct_evaluation",
            "direct_vendor_name",
            "direct_vendor_email",
            "direct_vendor_phone",
            "direct_vendor_address",
            "direct_evaluation_justification",
            "total_amount",
            "grand_total",
            "status",
            "created_at",
            "award_number",
            "award_id",
            "vendor",
        ]

    def get_award_number(self, obj):
        award = getattr(obj, "_created_award", None)
        return award.award_number if award else None

    def get_award_id(self, obj):
        award = getattr(obj, "_created_award", None)
        return award.id if award else None

    def get_vendor(self, obj):
        """Return normalized vendor dict matching AwardSerializer.get_vendor() format."""
        return {
            "id": None,
            "name": obj.direct_vendor_name,
            "contactPerson": obj.direct_vendor_name,
            "email": obj.direct_vendor_email,
            "phone": obj.direct_vendor_phone,
            "address": obj.direct_vendor_address,
            "is_direct_evaluation": True,
        }
