from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from collections import defaultdict

from ..models.comparative_models import (
    ComparativeStatement,
    ComparativeApprovalWorkflow,
    ComparativeNote,
    ComparativeLineItem,
    ComparativeVendorEvaluation,
    ComparativeVendorScoreCriteria,
    ComparativeVendorFinancial,
    ComparativeNotificationLog,
)


# ─── Score Criteria ───────────────────────────────────────────────────────────

class ComparativeVendorScoreCriteriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComparativeVendorScoreCriteria
        fields = ["id", "name", "score", "max_score", "weight"]


# ─── Vendor Evaluation ────────────────────────────────────────────────────────

class ComparativeVendorEvaluationSerializer(serializers.ModelSerializer):
    vendor_id = serializers.IntegerField(source="vendor.id", read_only=True)
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    criteria = ComparativeVendorScoreCriteriaSerializer(many=True, read_only=True)

    class Meta:
        model = ComparativeVendorEvaluation
        fields = [
            "id", "comparative", "vendor", "vendor_id", "vendor_name",
            "total_score", "is_recommended", "criteria",
        ]
        read_only_fields = ["id"]


class ComparativeVendorEvaluationCreateSerializer(serializers.ModelSerializer):
    criteria = ComparativeVendorScoreCriteriaSerializer(many=True, required=False)

    class Meta:
        model = ComparativeVendorEvaluation
        fields = ["comparative", "vendor", "total_score", "is_recommended", "criteria"]

    def create(self, validated_data):
        criteria_data = validated_data.pop("criteria", [])
        evaluation = ComparativeVendorEvaluation.objects.create(**validated_data)
        for c in criteria_data:
            ComparativeVendorScoreCriteria.objects.create(evaluation=evaluation, **c)
        return evaluation

    def update(self, instance, validated_data):
        criteria_data = validated_data.pop("criteria", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if criteria_data is not None:
            instance.criteria.all().delete()
            for c in criteria_data:
                ComparativeVendorScoreCriteria.objects.create(evaluation=instance, **c)
        return instance


# ─── Line Items ───────────────────────────────────────────────────────────────

class ComparativeLineItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    quotation_number = serializers.CharField(
        source="quotation.quotation_number", read_only=True
    )

    class Meta:
        model = ComparativeLineItem
        fields = [
            "id", "comparative", "item", "item_name",
            "vendor", "vendor_name",
            "quotation", "quotation_number",
            "quoted_price", "quantity", "total_price",
            "is_lowest", "is_recommended", "remarks",
        ]
        read_only_fields = ["total_price"]


class ComparativeLineItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComparativeLineItem
        fields = [
            "item", "vendor", "quotation",
            "quoted_price", "quantity",
            "is_lowest", "is_recommended", "remarks",
        ]
        read_only_fields = ["total_price"]


# ─── Vendor Financial ─────────────────────────────────────────────────────────

class ComparativeVendorFinancialSerializer(serializers.ModelSerializer):
    vendor_id = serializers.IntegerField(source="vendor.id", read_only=True)
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    quotation_number = serializers.CharField(
        source="quotation.quotation_number", read_only=True
    )
    items = serializers.SerializerMethodField()

    class Meta:
        model = ComparativeVendorFinancial
        fields = [
            "id", "comparative", "vendor", "vendor_id", "vendor_name",
            "quotation", "quotation_number",
            "subtotal", "vat", "ait", "delivery", "grand_total",
            "items",
        ]
        read_only_fields = ["id"]

    def get_items(self, obj):
        line_items = ComparativeLineItem.objects.filter(
            comparative=obj.comparative, vendor=obj.vendor
        ).select_related("item")
        return ComparativeLineItemSerializer(line_items, many=True).data


# ─── Approval Workflow ────────────────────────────────────────────────────────


class BlankAcceptingJSONField(serializers.JSONField):
    def to_internal_value(self, data):
        if data is None:
            return None
        if isinstance(data, str) and data.strip() == "":
            return []
        return super().to_internal_value(data)


def _populate_approver_fields(validated_data):
    """Fill role, approver_name, designation from the selected approver User."""
    approver = validated_data.get("approver")
    if not approver:
        return

    # approver_name: prefer Employee full name, fall back to username
    try:
        employee = approver.employee
        validated_data["approver_name"] = employee.employee_name or approver.username
        validated_data["designation"] = (
            employee.designation.name if employee.designation_id else ""
        )
    except Exception:
        validated_data["approver_name"] = approver.username
        validated_data["designation"] = ""

    # role: from User.role FK
    validated_data["role"] = approver.role.name if approver.role_id else ""


class ComparativeApprovalWorkflowSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="approver_name", read_only=True)
    members = BlankAcceptingJSONField(required=False, allow_null=True)

    class Meta:
        model = ComparativeApprovalWorkflow
        fields = [
            "id",
            # write-only (required for create/link)
            "comparative",
            "approver",
            # read / write
            "level",
            "status",
            "date",
            "remarks",
            "notification_sent",
            "notification_date",
            "members",
            # read-only (auto-populated from approver)
            "role",
            "name",
            "designation",
        ]
        read_only_fields = ["id", "role", "name", "designation"]
        extra_kwargs = {
            "comparative": {"write_only": True},
            "approver": {"write_only": True},
        }

    def create(self, validated_data):
        _populate_approver_fields(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        _populate_approver_fields(validated_data)
        return super().update(instance, validated_data)


# ─── Notes ────────────────────────────────────────────────────────────────────

class ComparativeNoteSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    role = serializers.CharField(read_only=True)
    designations = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()

    class Meta:
        model = ComparativeNote
        fields = ["id", "comparative", "author", "role", "designations", "date", "text"]
        read_only_fields = ["id", "date", "author", "role", "designations"]
        extra_kwargs = {
            "comparative": {"write_only": True},
        }

    def get_author(self, obj):
        if not obj.author_id:
            return None
        user = obj.author
        full_name = (getattr(user, "get_full_name", lambda: None)() or "").strip()
        return full_name or user.username

    def get_designations(self, obj):
        if not obj.author_id:
            return None
        user = obj.author
        employee = getattr(user, "employee", None)
        return (
            employee.designation.name if employee and getattr(employee, "designation", None) else None
        )

    def get_date(self, obj):
        if not obj.date:
            return None
        return obj.date.strftime("%Y-%m-%d")

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user:
            user = request.user
            validated_data["author"] = user
            validated_data["role"] = (
                user.role.name if getattr(user, "role", None) else ""
            )
        return super().create(validated_data)


# ─── Full CS Read Serializer ──────────────────────────────────────────────────

class ComparativeStatementSerializer(serializers.ModelSerializer):
    # ── kept fields ───────────────────────────────────────────────
    rfq_number = serializers.CharField(source="rfq.rfq_number", read_only=True)
    rfq_title = serializers.CharField(source="rfq.rfq_title", read_only=True)
    category = serializers.CharField(source="rfq.rfq_category.name", read_only=True)
    requisitions = serializers.SerializerMethodField()
    requisition_no = serializers.SerializerMethodField()
    budget_code = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    office_info = serializers.SerializerMethodField()
    description = serializers.CharField(source="rfq.description", read_only=True)

    # ── identity / audit ─────────────────────────────────────────
    created_by_name = serializers.SerializerMethodField()

    # ── computed financial summary ────────────────────────────────
    vendors_evaluated = serializers.SerializerMethodField()
    total_estimated_value = serializers.SerializerMethodField()
    lowest_bid = serializers.SerializerMethodField()
    recommended_bid = serializers.SerializerMethodField()
    potential_savings = serializers.SerializerMethodField()

    # ── structured composite fields ───────────────────────────────
    items = serializers.SerializerMethodField()
    vendors = serializers.SerializerMethodField()
    required_documents = serializers.SerializerMethodField()
    recommended_vendor = serializers.SerializerMethodField()
    vendor_ranking = serializers.SerializerMethodField()
    approval_matrix = serializers.SerializerMethodField()
    can_approve = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()
    notification_log = serializers.SerializerMethodField()

    class Meta:
        model = ComparativeStatement
        fields = [
            # ── KEPT (as instructed) ──────────────────────────────
            "id",
            "cs_number",
            "rfq",
            "rfq_number",
            "rfq_title",
            "title",
            "requisitions",
            "requisition_no",
            "category",
            "project",
            "office_info",
            "budget_code",
            # ── UPDATED / NEW ────────────────────────────────────
            "created_by",
            "created_by_name",
            "created_at",
            "auto_extracted",
            "description",
            "status",
            "extraction_date",
            "extraction_source",
            "vendors_evaluated",
            "total_estimated_value",
            "lowest_bid",
            "recommended_bid",
            "potential_savings",
            "items",
            "vendors",
            "required_documents",
            "recommended_vendor",
            "vendor_ranking",
            "justification",
            "approval_matrix",
            "can_approve",
            "notes",
            "notification_log",
        ]
        read_only_fields = ["cs_number", "created_by", "created_at"]

    # ── kept field helpers ────────────────────────────────────────

    def get_requisitions(self, obj):
        return obj.rfq.requisitions.count()

    def get_requisition_no(self, obj):
        req = obj.rfq.requisitions.first()
        return req.requisition_no if req else None

    def get_budget_code(self, obj):
        if obj.budget_code:
            return obj.budget_code
        req = obj.rfq.requisitions.select_related("budget_code").first()
        if req and req.budget_code:
            return getattr(req.budget_code, "code", None)
        li = obj.rfq.line_items.select_related("requisition__budget_code").filter(
            requisition__isnull=False
        ).first()
        if li and li.requisition and li.requisition.budget_code:
            return getattr(li.requisition.budget_code, "code", None)
        return None

    def get_project(self, obj):
        if obj.project:
            return obj.project
        req = obj.rfq.requisitions.select_related("project").first()
        if req and req.project:
            return getattr(req.project, "code", None) or getattr(req.project, "name", None)
        li = obj.rfq.line_items.select_related("requisition__project").filter(
            requisition__isnull=False
        ).first()
        if li and li.requisition and li.requisition.project:
            p = li.requisition.project
            return getattr(p, "code", None) or getattr(p, "name", None)
        return None

    def get_office_info(self, obj):
        req = obj.rfq.requisitions.select_related("requesting_office").first()
        if req and req.requesting_office:
            return {
                "id": req.requesting_office.id,
                "name": req.requesting_office.name,
                "address": req.requesting_office.address,
            }
        li = obj.rfq.line_items.select_related("requisition__requesting_office").filter(
            requisition__isnull=False
        ).first()
        if li and li.requisition and li.requisition.requesting_office:
            office = li.requisition.requesting_office
            return {"id": office.id, "name": office.name, "address": office.address}
        if obj.office:
            return {"id": None, "name": obj.office, "address": None}
        return None

    # ── identity / audit ─────────────────────────────────────────

    def get_created_by_name(self, obj):
        if not obj.created_by_id:
            return None
        user = obj.created_by
        full_name = (getattr(user, "get_full_name", lambda: None)() or "").strip()
        return full_name or user.username

    # ── computed financial summary ────────────────────────────────

    def get_vendors_evaluated(self, obj):
        return obj.rfq.vendor_submissions.filter(status="submitted").values(
            "vendor_id"
        ).distinct().count()

    def get_total_estimated_value(self, obj):
        val = obj.rfq.total_estimated_value
        return float(val) if val is not None else None

    def get_lowest_bid(self, obj):
        financial = obj.vendor_financials.order_by("grand_total").first()
        if financial:
            return float(financial.grand_total)
        sub = (
            obj.rfq.vendor_submissions.filter(status="submitted")
            .select_related("financial_proposal")
            .order_by("financial_proposal__grand_total")
            .first()
        )
        if sub:
            fp = getattr(sub, "financial_proposal", None)
            if fp:
                return float(fp.grand_total)
        return None

    def get_recommended_bid(self, obj):
        if not obj.recommended_vendor_id:
            return None
        financial = obj.vendor_financials.filter(
            vendor_id=obj.recommended_vendor_id
        ).first()
        return float(financial.grand_total) if financial else None

    def get_potential_savings(self, obj):
        total = obj.rfq.total_estimated_value
        rec_bid = self.get_recommended_bid(obj)
        if total and rec_bid is not None:
            return float(total) - rec_bid
        return None

    # ── items (RFQ line items — product list) ─────────────────────

    def get_required_documents(self, obj):
        return obj.rfq.required_documents or []

    def get_items(self, obj):
        return [
            {
                "id": li.id,
                "name": li.item_name,
                "unit": li.unit,
                "qty": li.quantity,
            }
            for li in obj.rfq.line_items.all()
        ]
    def _get_financial_proposal_items(self, submission, vendor_line_items=None):
        financial_proposal = getattr(submission, "financial_proposal", None)
        price_map = {}
        if financial_proposal is not None:
            for fi in financial_proposal.items.all():
                price_map[fi.line_item_id] = {
                    "unit_price": float(fi.unit_price),
                    "total_price": float(fi.total),
                }

        technical_proposal = None
        try:
            technical_proposal = submission.technical_proposal
        except Exception:
            technical_proposal = None

        if technical_proposal is not None:
            return [
                {
                    "item_id": compliance_item.line_item_id,
                    "item_name": compliance_item.item_name,
                    "unit_price": price_map.get(compliance_item.line_item_id, {}).get(
                        "unit_price", 0.0
                    ),
                    "total_price": price_map.get(compliance_item.line_item_id, {}).get(
                        "total_price", 0.0
                    ),
                }
                for compliance_item in technical_proposal.compliance_items.all()
            ]

        if vendor_line_items:
            return [
                {
                    "item_id": li.item_id,
                    "item_name": li.item.item_name if li.item else None,
                    "unit_price": float(li.quoted_price),
                    "total_price": float(li.total_price),
                }
                for li in vendor_line_items
            ]

        if financial_proposal is not None:
            return [
                {
                    "item_id": fi.line_item_id,
                    "item_name": fi.item_name,
                    "unit_price": float(fi.unit_price),
                    "total_price": float(fi.total),
                }
                for fi in financial_proposal.items.all()
            ]

        return []
    # ── vendors (rich detail per vendor) ─────────────────────────

    def get_vendors(self, obj):
        submissions = list(
            obj.rfq.vendor_submissions.filter(status="submitted")
            .select_related("financial_proposal")
            .prefetch_related(
                "financial_proposal__items",
                "technical_proposal__compliance_items",
                "documents",
            )
        )
        if not submissions:
            return []

        vendor_ids = [s.vendor_id for s in submissions]

        # Required documents defined on the RFQ
        rfq_required_docs = [str(d).strip() for d in (obj.rfq.required_documents or [])]
        total_required = len(rfq_required_docs)

        # Pre-fetch vendor profiles
        try:
            from vendorportal.models.models import VendorProfile
            profiles = {
                vp.id: vp
                for vp in VendorProfile.objects.filter(id__in=vendor_ids)
            }
            vendor_usernames = [s.vendor_name for s in submissions if s.vendor_name]
            username_profiles = {
                vp.user.username: vp
                for vp in VendorProfile.objects.filter(user__username__in=vendor_usernames).select_related('user')
                if vp.user
            }
        except Exception:
            profiles = {}
            username_profiles = {}

        # Pre-fetch evaluations and financials (keyed by vendor_id)
        evaluations = {
            e.vendor_id: e
            for e in obj.vendor_evaluations.prefetch_related("criteria").filter(
                vendor_id__in=vendor_ids
            )
        }
        financials = {
            f.vendor_id: f
            for f in obj.vendor_financials.filter(vendor_id__in=vendor_ids)
        }

        # Pre-fetch comparative line items grouped by vendor
        line_items_by_vendor = defaultdict(list)
        for li in obj.line_items.filter(vendor_id__in=vendor_ids).select_related("item"):
            line_items_by_vendor[li.vendor_id].append(li)

        # Compute min grand total for financial score normalisation
        grand_totals = []
        for sub in submissions:
            fin = financials.get(sub.vendor_id)
            if fin:
                grand_totals.append(float(fin.grand_total))
            else:
                fp_sub = getattr(sub, "financial_proposal", None)
                if fp_sub:
                    grand_totals.append(float(fp_sub.grand_total))
        min_grand_total = min((t for t in grand_totals if t > 0), default=0)

        result = []
        for submission in submissions:
            vid = submission.vendor_id
            vp = profiles.get(vid) or username_profiles.get(submission.vendor_name)
            evaluation = evaluations.get(vid)
            financial = financials.get(vid)

            # Technical score (legacy ComparativeVendorEvaluation)
            technical_score = None
            if evaluation:
                criteria = [
                    {
                        "name": c.name,
                        "max_score": float(c.max_score),
                        "score": float(c.score),
                        "weight": float(c.weight),
                    }
                    for c in evaluation.criteria.all()
                ]
                technical_score = {
                    "total": float(evaluation.total_score),
                    "criteria": criteria,
                }

            # ── Document-based score (0-100) ─────────────────────────────────
            _request = self.context.get("request")
            submitted_doc_names = set()
            doc_file_map = {}
            for _doc in submission.documents.all():
                _name = _doc.doc_name.strip()
                submitted_doc_names.add(_name)
                if _doc.file:
                    doc_file_map[_name] = (
                        _request.build_absolute_uri(_doc.file.url)
                        if _request
                        else _doc.file.url
                    )
            if total_required > 0:
                matched = sum(1 for req in rfq_required_docs if req in submitted_doc_names)
                doc_score = round((matched / total_required) * 100, 1)
            else:
                doc_score = 100.0 if submitted_doc_names else 0.0

            # ── Financial score (0-100): lowest price → 100 ──────────────────
            fin = financials.get(vid)
            if fin:
                grand_total = float(fin.grand_total)
            else:
                fp_sub = getattr(submission, "financial_proposal", None)
                grand_total = float(fp_sub.grand_total) if fp_sub else 0
            financial_score = (
                round(min_grand_total / grand_total * 100, 1)
                if grand_total > 0 and min_grand_total > 0
                else None
            )

            # ── Overall score: 50% doc + 50% financial ───────────────────────
            if financial_score is not None:
                overall_score = round(doc_score * 0.5 + financial_score * 0.5, 1)
            else:
                overall_score = round(doc_score * 0.5, 1)

            # ── Per-document checklist for Technical Scorecard tab ──────────────
            if total_required > 0:
                per_doc_score = round(100 / total_required, 2)
                technical_docs = {
                    req.lower().replace(" ", "_").replace("/", "_"): {
                        "score": per_doc_score if req in submitted_doc_names else 0,
                        "maxScore": per_doc_score,
                        "comment": "Uploaded" if req in submitted_doc_names else "Missing",
                        "doc_name": req,
                        "uploaded": req in submitted_doc_names,
                        "file_url": doc_file_map.get(req),
                    }
                    for req in rfq_required_docs
                }
            else:
                technical_docs = {
                    doc.doc_name.lower().replace(" ", "_"): {
                        "score": 1,
                        "maxScore": 1,
                        "comment": "Uploaded",
                        "doc_name": doc.doc_name,
                        "uploaded": True,
                        "file_url": doc_file_map.get(doc.doc_name.strip()),
                    }
                    for doc in submission.documents.all()
                }

            # Financial proposal items — prefer technical proposal compliance when available
            vendor_line_items = line_items_by_vendor.get(vid, [])
            items_data = self._get_financial_proposal_items(
                submission, vendor_line_items=vendor_line_items
            )

            # Financial proposal totals
            if financial:
                financial_proposal = {
                    "items": items_data,
                    "subtotal": float(financial.subtotal),
                    "vat": float(financial.vat),
                    "ait": float(financial.ait),
                    "delivery": float(financial.delivery),
                    "grand_total": float(financial.grand_total),
                }
            else:
                fp_sub = getattr(submission, "financial_proposal", None)
                financial_proposal = (
                    {
                        "items": items_data,
                        "subtotal": float(fp_sub.sub_total),
                        "vat": float(fp_sub.vat),
                        "ait": 0,
                        "delivery": float(fp_sub.delivery_charge),
                        "grand_total": float(fp_sub.grand_total),
                    }
                    if fp_sub
                    else None
                )

            if vp and obj.recommended_vendor_id == vp.id:
                is_recommended = True
            elif evaluation:
                is_recommended = evaluation.is_recommended
            else:
                is_recommended = False

            tin_url = None
            submission_documents = getattr(submission, "documents", None)
            if submission_documents is not None:
                tin_doc = next(
                    (
                        doc
                        for doc in submission_documents.all()
                        if doc.doc_type == "tin_certificate" and getattr(doc, "file", None)
                    ),
                    None,
                )
                if tin_doc and getattr(tin_doc, "file", None):
                    request = self.context.get("request")
                    if request:
                        tin_url = request.build_absolute_uri(tin_doc.file.url)
                    else:
                        tin_url = tin_doc.file.url

            result.append(
                {
                    "id": vid,
                    "vendor_id": vp.id if vp else vid,
                    "name": (vp.name if vp else submission.vendor_name),
                    "company_name_bn": vp.company_name_bn if vp else None,
                    "user_name": vp.user.username if vp and vp.user else None,
                    "tin": tin_url or (vp.tax_id if vp else None),
                    "location": vp.address if vp else None,
                    "is_recommended": is_recommended,
                    "enlisted_since": (
                        str(vp.registration_date)
                        if vp and vp.registration_date
                        else None
                    ),
                    "past_orders": (vp.total_orders or 0) if vp else 0,
                    "delivery_rating": float(vp.rating) if vp and vp.rating else 0.0,
                    "technical_score": technical_score,
                    "doc_score": doc_score,
                    "financial_score": financial_score,
                    "overall_score": overall_score,
                    "financial_proposal": financial_proposal,
                    "technical_docs": technical_docs,
                }
            )

        return result

    # ── recommended vendor summary ────────────────────────────────

    def get_recommended_vendor(self, obj):
        if not obj.recommended_vendor_id:
            return None
        vp = obj.recommended_vendor
        evaluation = obj.vendor_evaluations.filter(
            vendor_id=obj.recommended_vendor_id
        ).first()
        financial = obj.vendor_financials.filter(
            vendor_id=obj.recommended_vendor_id
        ).first()

        submission = obj.rfq.vendor_submissions.prefetch_related(
            "documents",
            "financial_proposal__items",
            "technical_proposal__compliance_items",
        )
        submission = submission.filter(vendor_id=obj.recommended_vendor_id).first()
        if submission is None and vp is not None:
            submission = obj.rfq.vendor_submissions.filter(
                vendor_name=vp.user.username if vp.user else vp.name
            ).prefetch_related(
                "documents",
                "financial_proposal__items",
                "technical_proposal__compliance_items",
            ).first()

        tin_url = None
        financial_proposal = None
        if submission is not None:
            tin_doc = next(
                (
                    doc
                    for doc in submission.documents.all()
                    if doc.doc_type == "tin_certificate" and getattr(doc, "file", None)
                ),
                None,
            )
            if tin_doc and getattr(tin_doc, "file", None):
                request = self.context.get("request")
                tin_url = request.build_absolute_uri(tin_doc.file.url) if request else tin_doc.file.url

            items_data = self._get_financial_proposal_items(submission)
            fp_sub = getattr(submission, "financial_proposal", None)
            if fp_sub:
                financial_proposal = {
                    "items": items_data,
                    "subtotal": float(fp_sub.sub_total),
                    "vat": float(fp_sub.vat),
                    "ait": float(fp_sub.ait),
                    "delivery": float(fp_sub.delivery_charge),
                    "grand_total": float(fp_sub.grand_total),
                }

        evals_ordered = list(
            obj.vendor_evaluations.order_by("-total_score").values_list(
                "vendor_id", flat=True
            )
        )
        rank = None
        if obj.recommended_vendor_id in evals_ordered:
            rank = evals_ordered.index(obj.recommended_vendor_id) + 1

        return {
            "id": submission.vendor_id if submission is not None else (vp.id if vp else None),
            "vendor_id": vp.id if vp else None,
            "name": vp.name if vp else None,
            "company_name_bn": vp.company_name_bn if vp else None,
            "user_name": vp.user.username if vp and vp.user else None,
            "tin": tin_url or (vp.tax_id if vp else None),
            "location": vp.address if vp else None,
            "is_recommended": True,
            "enlisted_since": str(vp.registration_date) if vp and vp.registration_date else None,
            "past_orders": (vp.total_orders or 0) if vp else 0,
            "delivery_rating": float(vp.rating) if vp and vp.rating else 0.0,
            "technical_score": float(evaluation.total_score) if evaluation else None,
            "financial_proposal": financial_proposal,
            "rank": rank,
        }

    # ── vendor ranking ────────────────────────────────────────────

    def get_vendor_ranking(self, obj):
        evaluations = list(
            obj.vendor_evaluations.select_related("vendor").order_by("-total_score")
        )
        financials = {f.vendor_id: f for f in obj.vendor_financials.all()}
        result = []
        for rank, evaluation in enumerate(evaluations, 1):
            financial = financials.get(evaluation.vendor_id)
            result.append(
                {
                    "rank": rank,
                    "name": evaluation.vendor.name if evaluation.vendor else None,
                    "technical": float(evaluation.total_score),
                    "financial": float(financial.grand_total) if financial else None,
                    "recommended": evaluation.is_recommended,
                }
            )
        return result

    # ── approval matrix ───────────────────────────────────────────

    def get_can_approve(self, obj):
        """
        Returns True if the requesting user is a pending approver for this CS.
        Falls back to checking the global ApprovalMatrix settings when no per-CS
        workflow records exist yet.
        """
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False
        if obj.status != "pending_approval":
            return False

        user = request.user

        # ── Case 1: per-CS workflow records exist ─────────────────
        workflow_entries = list(obj.approval_workflow.all())
        if workflow_entries:
            # Find the first pending step
            pending_step = next(
                (wf for wf in workflow_entries if wf.status == "pending"), None
            )
            if pending_step is None:
                return False

            # Check single approver FK
            if pending_step.approver_id and pending_step.approver_id == user.id:
                return True

            # Check members JSON list (may store {id, name, ...} dicts or raw IDs)
            members = pending_step.members or []
            for member in members:
                if isinstance(member, dict):
                    if member.get("id") == user.id or member.get("user_id") == user.id:
                        return True
                elif member == user.id:
                    return True

            return False

        # ── Case 2: no per-CS workflow yet — use global ApprovalMatrix ──
        try:
            from procurement.models.settings_models import ApprovalMatrix

            # Find the lowest active level for "Comparative Statement" module
            matrix_entries = (
                ApprovalMatrix.objects.filter(
                    module="Comparative Statement",
                    is_active=True,
                )
                .prefetch_related("approvers__user")
                .order_by("approval_level")
            )
            # Get the lowest level entry
            first_level = None
            for entry in matrix_entries:
                first_level = entry
                break

            if first_level is None:
                return False

            # Check if the user is in the approvers M2M for this level
            employee = getattr(user, "employee", None)
            if employee and first_level.approvers.filter(pk=employee.pk).exists():
                return True
        except Exception:
            pass

        return False

    def get_approval_matrix(self, obj):
        result = []
        for wf in obj.approval_workflow.all():
            result.append(
                {
                    "level": wf.level,
                    "role": wf.role,
                    "name": wf.approver_name,
                    "designation": wf.designation,
                    "status": wf.status,
                    "approver_id": wf.approver_id,
                    "date": wf.date.strftime("%Y-%m-%d") if wf.date else None,
                    "remarks": wf.remarks,
                    "notification_sent": wf.notification_sent,
                    "notification_date": (
                        wf.notification_date.strftime("%Y-%m-%d %H:%M")
                        if wf.notification_date
                        else None
                    ),
                    "members": wf.members or [],
                }
            )
        return result

    # ── notes ─────────────────────────────────────────────────────

    def get_notes(self, obj):
        result = []
        for note in obj.notes.all():
            author_name = None
            role_name = note.role
            designation_name = None
            if note.author_id:
                user = note.author
                full_name = (
                    getattr(user, "get_full_name", lambda: None)() or ""
                ).strip()
                author_name = full_name or user.username
                if not role_name:
                    role_name = (
                        user.role.name if getattr(user, "role", None) else None
                    )
                employee = getattr(user, "employee", None)
                designation_name = (
                    employee.designation.name
                    if employee and getattr(employee, "designation", None)
                    else None
                )
            result.append(
                {
                    "id": note.id,
                    "author": author_name,
                    "role": role_name,
                    "designations": designation_name,
                    "date": note.date.strftime("%Y-%m-%d") if note.date else None,
                    "text": note.text,
                }
            )
        return result

    # ── notification log ──────────────────────────────────────────

    def get_notification_log(self, obj):
        result = []
        for log in obj.notification_logs.all():
            result.append(
                {
                    "date": (
                        log.date.strftime("%Y-%m-%d %H:%M") if log.date else None
                    ),
                    "event": log.event,
                    "recipients": log.recipients,
                    "channel": log.channel,
                }
            )
        return result


# ─── Create / Update Serializer ───────────────────────────────────────────────

def _build_award_data(cs):
    """
    Collect all data needed to create/update an Award from a ComparativeStatement.
    Returns a dict suitable for Award.objects.create(**data) / update(**data).
    """
    rfq = cs.rfq
    vp = cs.recommended_vendor  # VendorProfile instance

    # ── financial totals from vendor's submission / financials ────
    total_amount = 0
    items_data = []
    financial = cs.vendor_financials.filter(vendor_id=vp.id).first() if vp else None
    submission = None
    financial_proposal = None
    if vp:
        submissions = rfq.vendor_submissions.select_related(
            "financial_proposal"
        ).prefetch_related("financial_proposal__items")
        submission = submissions.filter(vendor_id=vp.id).first()
        if submission is None:
            uname = vp.user.username if vp.user else None
            if uname:
                submission = submissions.filter(vendor_name=uname).first()
        financial_proposal = getattr(submission, "financial_proposal", None) if submission else None

    rfq_line_items = {line_item.id: line_item for line_item in rfq.line_items.all()} if rfq else {}

    if financial_proposal:
        total_amount = float(financial.grand_total) if financial else float(financial_proposal.grand_total)
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
            unit = financial_item.unit or getattr(rfq_line_item, "unit", None)
            unit_price = float(financial_item.unit_price)
            total = float(financial_item.total)

            items_data.append(
                {
                    "line_item_id": financial_item.line_item_id,
                    "item_id": financial_item.line_item_id,
                    "name": item_name,
                    "item_name": item_name,
                    "description": description,
                    "specification": getattr(rfq_line_item, "specification", "") or "",
                    "quantity": float(quantity or 0),
                    "qty": float(quantity or 0),
                    "unit": unit,
                    "unitPrice": unit_price,
                    "unit_price": unit_price,
                    "total": total,
                    "total_price": total,
                }
            )
    elif financial:
        total_amount = float(financial.grand_total)
        for li in cs.line_items.filter(vendor_id=vp.id).select_related("item"):
            item_name = li.item.item_name if li.item else ""
            items_data.append(
                {
                    "item_id": getattr(li.item, "id", None) if li.item else None,
                    "name": item_name,
                    "item_name": item_name,
                    "description": item_name,
                    "specification": getattr(li.item, "specifications", "") if li.item else "",
                    "quantity": float(li.quantity),
                    "qty": float(li.quantity),
                    "unit": getattr(li.item, "unit", None) if li.item else None,
                    "unitPrice": float(li.quoted_price),
                    "unit_price": float(li.quoted_price),
                    "total": float(li.total_price),
                    "total_price": float(li.total_price),
                }
            )

    approved_amount = float(rfq.total_estimated_value) if rfq.total_estimated_value else None
    total_items = len(items_data)

    # ── organization info from requesting office ──────────────────
    organization_info = None
    req = rfq.requisitions.select_related(
        "requesting_office", "requesting_office__office_contact_person"
    ).first()
    if req and req.requesting_office:
        office = req.requesting_office
        contact_user = getattr(office, "office_contact_person", None)
        organization_info = {
            "name": office.name,
            "contactPerson": contact_user.username if contact_user else None,
            "email": getattr(office, "email", None),
            "phone": getattr(office, "phone", None),
            "address": getattr(office, "address", None),
        }
    elif cs.office:
        organization_info = {"name": cs.office, "contactPerson": None, "email": None, "phone": None, "address": None}

    # ── contact info from CS creator ─────────────────────────────
    contact_info = None
    if cs.created_by:
        user = cs.created_by
        full_name = (getattr(user, "get_full_name", lambda: None)() or "").strip() or user.username
        contact_info = {
            "procurementOfficer": full_name,
            "email": user.email or None,
            "phone": None,
            "officeHours": None,
        }

    # ── terms from CS justification (if it's a list) ─────────────
    terms = []
    if cs.justification:
        if isinstance(cs.justification, list):
            terms = cs.justification
        elif isinstance(cs.justification, dict):
            terms_val = cs.justification.get("terms") or cs.justification.get("conditions")
            if isinstance(terms_val, list):
                terms = terms_val

    return {
        "rfq": rfq,
        "vendor_profile": vp,
        "title": cs.title or (rfq.rfq_title if rfq else None),
        "description": cs.description,
        "total_amount": total_amount,
        "approved_amount": approved_amount,
        "award_date": timezone.now().date(),
        "status": "active",
        "items": items_data,
        "total_items": total_items,
        "organization_info": organization_info,
        "contact_info": contact_info,
        "terms": terms,
        "delivery_schedule": [],
    }


def _sync_award_for_cs(cs):
    """
    Create or update the Award linked to `cs` based on the recommended_vendor.
    Called whenever recommended_vendor is set/changed.
    """
    from ..models.award_models import Award

    if not cs.recommended_vendor_id:
        return  # nothing to do if no vendor recommended

    existing = Award.objects.filter(comparative_statement=cs).first()
    data = _build_award_data(cs)

    if existing:
        for field, value in data.items():
            setattr(existing, field, value)
        existing.save()
    else:
        Award.objects.create(comparative_statement=cs, **data)


class ComparativeStatementCreateSerializer(serializers.ModelSerializer):
    line_items = ComparativeLineItemCreateSerializer(many=True, required=False)
    action = serializers.ChoiceField(
        choices=["approve", "reject", "return"], required=False, write_only=True
    )
    remarks = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = ComparativeStatement
        fields = [
            "rfq",
            "title",
            "description",
            "recommended_vendor",
            "justification",
            "status",
            "auto_extracted",
            "extraction_date",
            "extraction_source",
            "budget_code",
            "project",
            "office",
            "line_items",
            "action",
            "remarks",
        ]

    def _get_pending_workflow_step(self, instance):
        return instance.approval_workflow.filter(status="pending").order_by("level").first()

    def _create_note(self, instance, remarks):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not remarks or not user or not getattr(user, "is_authenticated", False):
            return

        ComparativeNote.objects.create(
            comparative=instance,
            author=user,
            role=user.role.name if getattr(user, "role", None) else "",
            text=remarks,
        )

    def _apply_action(self, instance, action, remarks):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        now = timezone.now()
        pending_step = self._get_pending_workflow_step(instance)

        if pending_step and pending_step.approver_id and (
            not user or pending_step.approver_id != user.id
        ):
            raise serializers.ValidationError(
                {"detail": "Only the current approver can take action on this comparative statement."}
            )

        if action == "approve":
            if not instance.recommended_vendor_id:
                raise serializers.ValidationError(
                    {"recommended_vendor": "A recommended vendor is required before approval."}
                )

            if pending_step:
                pending_step.status = "approved"
                pending_step.date = now
                pending_step.remarks = remarks
                pending_step.save(update_fields=["status", "date", "remarks"])

                next_step = (
                    instance.approval_workflow.filter(level__gt=pending_step.level)
                    .order_by("level")
                    .first()
                )
                if next_step:
                    if next_step.status == "not_started":
                        next_step.status = "pending"
                        next_step.notification_sent = True
                        next_step.notification_date = now
                        next_step.save(
                            update_fields=[
                                "status",
                                "notification_sent",
                                "notification_date",
                            ]
                        )
                    instance.status = "pending_approval"
                    instance.approved_by = None
                    instance.approved_date = None
                else:
                    instance.status = "approved"
                    instance.approved_by = user if getattr(user, "is_authenticated", False) else None
                    instance.approved_date = now
            else:
                instance.status = "approved"
                instance.approved_by = user if getattr(user, "is_authenticated", False) else None
                instance.approved_date = now
        elif action == "reject":
            if pending_step:
                pending_step.status = "rejected"
                pending_step.date = now
                pending_step.remarks = remarks
                pending_step.save(update_fields=["status", "date", "remarks"])
            instance.status = "rejected"
            instance.approved_by = None
            instance.approved_date = None
        elif action == "return":
            if pending_step and remarks is not None:
                pending_step.remarks = remarks
                pending_step.save(update_fields=["remarks"])
            instance.status = "under_review"
            instance.approved_by = None
            instance.approved_date = None

        self._create_note(instance, remarks)

    @transaction.atomic
    def create(self, validated_data):
        line_items_data = validated_data.pop("line_items", [])
        validated_data.pop("action", None)
        validated_data.pop("remarks", None)
        request = self.context.get("request")
        validated_data["created_by"] = request.user if request else None
        cs = ComparativeStatement.objects.create(**validated_data)
        for item_data in line_items_data:
            item_data.pop("comparative", None)
            ComparativeLineItem.objects.create(comparative=cs, **item_data)

        if validated_data.get("recommended_vendor") is not None:
            ComparativeVendorEvaluation.objects.filter(comparative=cs).update(is_recommended=False)
            if cs.recommended_vendor:
                ComparativeVendorEvaluation.objects.filter(
                    comparative=cs,
                    vendor=cs.recommended_vendor,
                ).update(is_recommended=True)
            _sync_award_for_cs(cs)

        return cs

    @transaction.atomic
    def update(self, instance, validated_data):
        line_items_data = validated_data.pop("line_items", None)
        action = validated_data.pop("action", None)
        remarks = validated_data.pop("remarks", None)
        recommended_vendor_changed = "recommended_vendor" in validated_data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if action:
            self._apply_action(instance, action, remarks)

        instance.save()

        if recommended_vendor_changed:
            ComparativeVendorEvaluation.objects.filter(comparative=instance).update(is_recommended=False)
            if instance.recommended_vendor:
                ComparativeVendorEvaluation.objects.filter(
                    comparative=instance,
                    vendor=instance.recommended_vendor,
                ).update(is_recommended=True)
            _sync_award_for_cs(instance)

        if line_items_data is not None:
            instance.line_items.all().delete()
            for item_data in line_items_data:
                item_data.pop("comparative", None)
                ComparativeLineItem.objects.create(comparative=instance, **item_data)
        return instance
