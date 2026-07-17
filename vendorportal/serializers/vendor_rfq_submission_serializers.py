import json
from rest_framework import serializers
from django.utils import timezone

from authentication.models import User
from procurement.models.rfq_models import RFQ, RFQVendorInvitation
from vendorportal.models.models import VendorProfile
from ..models.apply_rfq_models import (
    VendorRFQSubmission,
    TechnicalProposal,
    ComplianceItem,
    FinancialProposal,
    FinancialItem,
    SubmissionDocument,
)

# ─── helper ──────────────────────────────────────────────────────────────────

DOC_NAME_TO_TYPE = {
    "Company Registration Certificate": "company_registration",
    "VAT Registration (BIN)":           "vat_registration",
    "TIN Certificate":                  "tin_certificate",
    "Bank Solvency Certificate":        "bank_solvency",
    "Up to date Trade License":         "trade_license",
}

def _parse_int_or_none(value):
    """Convert empty string / None to None, otherwise int."""
    if value in (None, "", "null"):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


# ─────────────────────────────────────────────────────────────────────────────
# READ serializers  (used for GET list / retrieve)
# ─────────────────────────────────────────────────────────────────────────────

class ComplianceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ComplianceItem
        fields = ["id", "line_item_id", "item_name", "required_spec", "offered_spec", "compliant"]


class TechnicalProposalSerializer(serializers.ModelSerializer):
    compliance = ComplianceItemSerializer(many=True, source="compliance_items", read_only=True)

    class Meta:
        model  = TechnicalProposal
        fields = ["id", "company_experience", "methodology", "compliance", "updated_at"]


class FinancialItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FinancialItem
        fields = ["id", "line_item_id", "item_name", "description", "qty", "unit", "unit_price", "total"]


class FinancialProposalSerializer(serializers.ModelSerializer):
    items = FinancialItemSerializer(many=True, read_only=True)

    class Meta:
        model  = FinancialProposal
        fields = [
            "id", "sub_total", "vat", "ait", "delivery_charge", "grand_total",
            "payment_terms", "quotation_validity_days", "delivery_lead_time_days",
            "items", "updated_at",
        ]


class SubmissionDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model  = SubmissionDocument
        fields = ["id", "doc_name", "doc_type", "file", "file_url", "filename", "uploaded_at"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


class VendorRFQSubmissionSerializer(serializers.ModelSerializer):
    technical_proposal = TechnicalProposalSerializer(read_only=True)
    financial_proposal = FinancialProposalSerializer(read_only=True)
    documents          = SubmissionDocumentSerializer(many=True, read_only=True)
    rfq                = serializers.PrimaryKeyRelatedField(read_only=True)
    rfq_number         = serializers.CharField(source="rfq.rfq_number", read_only=True)
    vendor             = serializers.SerializerMethodField()

    class Meta:
        model  = VendorRFQSubmission
        fields = [
            "id", "rfq", "rfq_number", "vendor", "status",
            "recommended_status", "is_recommended",
            "warranty_period", "additional_remarks", "declaration",
            "technical_proposal", "financial_proposal", "documents",
            "submitted_at", "created_at", "updated_at",
        ]

    def _find_vendor_profile(self, obj):
        if obj.rfq and obj.vendor_name:
            profile = VendorProfile.objects.filter(
                rfq_invitations__rfq=obj.rfq,
                user__username__iexact=obj.vendor_name,
            ).first()
            if profile:
                return profile

            profile = VendorProfile.objects.filter(
                rfq_invitations__rfq=obj.rfq,
                name__iexact=obj.vendor_name,
            ).first()
            if profile:
                return profile

        return VendorProfile.objects.filter(pk=obj.vendor_id).first()

    def _find_vendor_user_id(self, vendor):
        if not vendor:
            return None
        if getattr(vendor, "user", None):
            return vendor.user.id
        if vendor.email:
            matched_user = User.objects.filter(email__iexact=vendor.email).first()
            return matched_user.id if matched_user else None
        return None

    def get_vendor(self, obj):
        vendor = self._find_vendor_profile(obj)
        return {
            "vendor_id":   vendor.id if vendor else obj.vendor_id,
            "user_id":      self._find_vendor_user_id(vendor),
            "vendor_name": obj.vendor_name,
            "designation": obj.designation,
            "contactPerson": vendor.contact_person if vendor else None,
            "email":         vendor.email if vendor else None,
            "phone":         vendor.phone if vendor else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# WRITE serializer  (POST / PUT / PATCH)
# Accepts multipart/form-data — compliance & items arrive as JSON strings
# ─────────────────────────────────────────────────────────────────────────────

class VendorRFQSubmissionWriteSerializer(serializers.Serializer):
    # ── RFQ reference
    rfq        = serializers.PrimaryKeyRelatedField(queryset=RFQ.objects.all())
    rfq_number = serializers.CharField(required=False, allow_blank=True)
    status     = serializers.ChoiceField(choices=["draft", "submitted"], default="draft")

    # ── Technical proposal
    company_experience = serializers.CharField(required=False, allow_blank=True, default="")
    methodology        = serializers.CharField(required=False, allow_blank=True, default="")
    compliance         = serializers.CharField(required=False, allow_blank=True, default="[]")  # JSON string

    # ── Financial proposal
    items                   = serializers.CharField(required=False, allow_blank=True, default="[]")  # JSON string
    sub_total               = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    vat                     = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    ait                     = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    delivery_charge         = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    grand_total             = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_terms           = serializers.CharField(required=False, allow_blank=True, default="")
    quotation_validity_days  = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)
    delivery_lead_time_days  = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)

    # ── Additional info
    warranty_period    = serializers.CharField(required=False, allow_blank=True, allow_null=True, default="")
    additional_remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True, default="")
    declaration        = serializers.CharField(required=False, default="false")
    recommended_status = serializers.ChoiceField(
        choices=["withdraw", "skip", "decline", "accept"],
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
    )
    is_recommended     = serializers.BooleanField(default=False)

    # ── Vendor info
    vendor_id   = serializers.IntegerField()
    vendor_name = serializers.CharField()
    designation = serializers.CharField(required=False, allow_blank=True, allow_null=True, default="")

    # ── Validation helpers

    def _resolve_vendor_profile(self, rfq, vendor_name):
        if not rfq or not vendor_name:
            return None

        profile = VendorProfile.objects.filter(
            rfq_invitations__rfq=rfq,
            user__username__iexact=vendor_name,
        ).first()
        if profile:
            return profile

        profile = VendorProfile.objects.filter(
            rfq_invitations__rfq=rfq,
            name__iexact=vendor_name,
        ).first()
        return profile

    def validate(self, attrs):
        resolved_vendor = self._resolve_vendor_profile(attrs.get("rfq"), attrs.get("vendor_name"))
        if resolved_vendor:
            attrs["vendor_id"] = resolved_vendor.id
        return attrs

    def validate_compliance(self, value):
        if not value or value == "[]":
            return []
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            raise serializers.ValidationError("compliance must be a valid JSON array string.")

    def validate_items(self, value):
        if not value or value == "[]":
            return []
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            raise serializers.ValidationError("items must be a valid JSON array string.")

    def validate_declaration(self, value):
        return _parse_bool(value)

    def validate_quotation_validity_days(self, value):
        return _parse_int_or_none(value)

    def validate_delivery_lead_time_days(self, value):
        return _parse_int_or_none(value)

    def _sync_submission_invitation(self, submission):
        if submission.status != "submitted":
            return

        vendor = self._resolve_vendor_profile(submission.rfq, submission.vendor_name)
        if not vendor:
            vendor = VendorProfile.objects.filter(pk=submission.vendor_id).first()
        if not vendor:
            return

        invitation, created = RFQVendorInvitation.objects.get_or_create(
            rfq=submission.rfq,
            vendor=vendor,
            defaults={
                "invite_status": "submitted",
                "submitted_status": True,
            },
        )
        if not created:
            changed = False
            if not invitation.submitted_status:
                invitation.submitted_status = True
                changed = True
            if invitation.invite_status != "submitted":
                invitation.invite_status = "submitted"
                changed = True
            if changed:
                invitation.save(update_fields=["submitted_status", "invite_status"])

    # ── Create

    def create(self, validated_data):
        rfq = validated_data["rfq"]  # already an RFQ instance via PrimaryKeyRelatedField
        request = self.context.get("request")
        status_val = validated_data.get("status", "draft")

        # ── Main submission
        submission = VendorRFQSubmission.objects.create(
            rfq=rfq,
            vendor_id=validated_data["vendor_id"],
            vendor_name=validated_data["vendor_name"],
            designation=validated_data.get("designation", ""),
            status=status_val,
            recommended_status=validated_data.get("recommended_status"),
            is_recommended=validated_data.get("is_recommended", False),
            warranty_period=validated_data.get("warranty_period", ""),
            additional_remarks=validated_data.get("additional_remarks", ""),
            declaration=validated_data.get("declaration", False),
            submitted_at=timezone.now() if status_val == "submitted" else None,
            created_by=request.user if request and request.user.is_authenticated else None,
        )

        # ── Technical proposal
        tech = TechnicalProposal.objects.create(
            submission=submission,
            company_experience=validated_data.get("company_experience", ""),
            methodology=validated_data.get("methodology", ""),
        )
        for c in validated_data.get("compliance", []):
            ComplianceItem.objects.create(
                technical_proposal=tech,
                line_item_id=c.get("line_item_id"),
                item_name=c.get("item_name", ""),
                required_spec=c.get("required_spec", ""),
                offered_spec=c.get("offered_spec", ""),
                compliant=c.get("compliant", "Yes"),
            )

        # ── Financial proposal
        financial = FinancialProposal.objects.create(
            submission=submission,
            sub_total=validated_data.get("sub_total", 0),
            vat=validated_data.get("vat", 0),
            ait=validated_data.get("ait", 0),
            delivery_charge=validated_data.get("delivery_charge", 0),
            payment_terms=validated_data.get("payment_terms", ""),
            quotation_validity_days=validated_data.get("quotation_validity_days"),
            delivery_lead_time_days=validated_data.get("delivery_lead_time_days"),
        )
        for item in validated_data.get("items", []):
            FinancialItem.objects.create(
                financial_proposal=financial,
                line_item_id=item.get("line_item_id"),
                item_name=item.get("item_name", ""),
                description=item.get("description", ""),
                qty=item.get("qty", 1),
                unit=item.get("unit", ""),
                unit_price=item.get("unit_price", 0),
                total=item.get("total", 0),
            )

        # ── Documents  (keys: documents[Company Registration Certificate])
        if request:
            for key, file_obj in request.FILES.items():
                if key.startswith("documents[") and key.endswith("]"):
                    doc_name = key[10:-1]
                    doc_type = DOC_NAME_TO_TYPE.get(doc_name, "other")
                    SubmissionDocument.objects.create(
                        submission=submission,
                        doc_name=doc_name,
                        doc_type=doc_type,
                        file=file_obj,
                    )

        self._sync_submission_invitation(submission)
        return submission

    # ── Update (PUT / PATCH)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        status_val = validated_data.get("status", instance.status)

        # ── Update submission fields
        instance.vendor_id   = validated_data.get("vendor_id",   instance.vendor_id)
        instance.vendor_name = validated_data.get("vendor_name", instance.vendor_name)
        instance.designation = validated_data.get("designation", instance.designation)
        instance.status      = status_val
        instance.recommended_status = validated_data.get("recommended_status", instance.recommended_status)
        instance.is_recommended = validated_data.get("is_recommended", instance.is_recommended)
        instance.warranty_period    = validated_data.get("warranty_period",    instance.warranty_period)
        instance.additional_remarks = validated_data.get("additional_remarks", instance.additional_remarks)
        instance.declaration        = validated_data.get("declaration",        instance.declaration)
        if status_val == "submitted" and not instance.submitted_at:
            instance.submitted_at = timezone.now()
        instance.save()

        # ── Update technical proposal
        tech, _ = TechnicalProposal.objects.get_or_create(submission=instance)
        tech.company_experience = validated_data.get("company_experience", tech.company_experience)
        tech.methodology        = validated_data.get("methodology",        tech.methodology)
        tech.save()

        compliance_data = validated_data.get("compliance")
        if compliance_data is not None:
            tech.compliance_items.all().delete()
            for c in compliance_data:
                ComplianceItem.objects.create(
                    technical_proposal=tech,
                    line_item_id=c.get("line_item_id"),
                    item_name=c.get("item_name", ""),
                    required_spec=c.get("required_spec", ""),
                    offered_spec=c.get("offered_spec", ""),
                    compliant=c.get("compliant", "Yes"),
                )

        # ── Update financial proposal
        fin, _ = FinancialProposal.objects.get_or_create(submission=instance)
        for field in ("sub_total", "vat", "ait", "delivery_charge",
                      "payment_terms", "quotation_validity_days", "delivery_lead_time_days"):
            if field in validated_data:
                setattr(fin, field, validated_data[field])
        fin.save()

        items_data = validated_data.get("items")
        if items_data is not None:
            fin.items.all().delete()
            for item in items_data:
                FinancialItem.objects.create(
                    financial_proposal=fin,
                    line_item_id=item.get("line_item_id"),
                    item_name=item.get("item_name", ""),
                    description=item.get("description", ""),
                    qty=item.get("qty", 1),
                    unit=item.get("unit", ""),
                    unit_price=item.get("unit_price", 0),
                    total=item.get("total", 0),
                )

        # ── Update / append documents (replace same doc_type if re-uploaded)
        if request:
            for key, file_obj in request.FILES.items():
                if key.startswith("documents[") and key.endswith("]"):
                    doc_name = key[10:-1]
                    doc_type = DOC_NAME_TO_TYPE.get(doc_name, "other")
                    old = instance.documents.filter(doc_type=doc_type).first()
                    if old:
                        old.file.delete(save=False)
                        old.delete()
                    SubmissionDocument.objects.create(
                        submission=instance,
                        doc_name=doc_name,
                        doc_type=doc_type,
                        file=file_obj,
                    )

        self._sync_submission_invitation(instance)
        return instance