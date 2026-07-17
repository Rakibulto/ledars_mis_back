from django.http import Http404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from paginations import Pagination
from inventory.views import CreatedByMixin
from ..models.quotation_models import VendorQuotation, QuotationItem, QuotationOpening
from ..models.rfq_models import RFQ
from ..models.comparative_models import ComparativeStatement
from ..models.award_models import Award
from ..models.notification_models import ProcurementNotification
from vendorportal.models.apply_rfq_models import VendorRFQSubmission
from ..serializers.quotation_serializers import (
    VendorQuotationSerializer,
    VendorQuotationCreateSerializer,
    VendorQuotationRFQSerializer,
    QuotationItemSerializer,
    QuotationOpeningSerializer,
    DirectEvaluationSerializer,
    DirectEvaluationResponseSerializer,
)


class VendorQuotationViewSet(CreatedByMixin, viewsets.ModelViewSet):
    queryset = (
        VendorQuotation.objects.select_related("rfq", "vendor", "created_by")
        .prefetch_related("quotation_items__item")
        .all()
    )
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["quotation_number", "vendor__name", "rfq__rfq_number", "status"]
    ordering_fields = ["created_at", "total_amount", "grand_total"]
    ordering = ["-created_at"]
    filterset_fields = ["status", "rfq", "vendor"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return VendorQuotationCreateSerializer
        return VendorQuotationSerializer

    # ── helpers ────────────────────────────────────────────────────────────

    def _rfq_queryset(self):
        return RFQ.objects.select_related(
            "rfq_category", "opening", "opening__opened_by"
        ).prefetch_related(
            "vendor_submissions",
            "vendor_submissions__financial_proposal",
            "vendor_submissions__financial_proposal__items",
            "vendor_submissions__documents",
            "vendor_quotations",
            "comparative_statements__vendor_evaluations__criteria",
            "comparative_statements__vendor_evaluations__vendor",
        )

    # ── object lookup ──────────────────────────────────────────────────────

    def get_object(self):
        """Return a VendorQuotation, supporting fallback from RFQ id.

        1. Try pk as a VendorQuotation.pk → return that VQ.
        2. Try pk as an RFQ.pk → return the latest VQ for that RFQ.
        3. Neither found → Http404.
        """
        pk = self.kwargs.get(self.lookup_field)
        obj = VendorQuotation.objects.filter(pk=pk).first()
        if obj:
            self.check_object_permissions(self.request, obj)
            return obj
        obj = VendorQuotation.objects.filter(rfq_id=pk).order_by("-id").first()
        if obj:
            self.check_object_permissions(self.request, obj)
            return obj
        raise Http404

    # ── override GET endpoints ─────────────────────────────────────────────

    def list(self, request, *args, **kwargs):
        """Return one entry per RFQ with all vendor submissions aggregated."""
        rfq_ids = VendorRFQSubmission.objects.values_list(
            "rfq_id", flat=True
        ).distinct()
        qs = self._rfq_queryset().filter(id__in=rfq_ids)

        # Optional query-param filters
        rfq = request.query_params.get("rfq")
        rfq_status = request.query_params.get("status")
        if rfq:
            qs = qs.filter(id=rfq)
        if rfq_status:
            qs = qs.filter(status=rfq_status)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = VendorQuotationRFQSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(VendorQuotationRFQSerializer(qs, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        """Return the RFQ-aggregate view for the quotation's RFQ.

        The list serializer uses rfq.id as the entry id, so we first try the pk
        as an RFQ pk directly.  Only if no RFQ matches do we fall back to
        interpreting pk as a VendorQuotation pk.
        """
        pk = self.kwargs.get(self.lookup_field)
        rfq = self._rfq_queryset().filter(pk=pk).first()
        if not rfq:
            # Fallback: pk is a VendorQuotation pk
            vq = VendorQuotation.objects.filter(pk=pk).first()
            if not vq:
                vq = VendorQuotation.objects.filter(rfq_id=pk).order_by("-id").first()
            if not vq:
                raise NotFound("Quotation not found.")
            rfq = self._rfq_queryset().filter(pk=vq.rfq_id).first()
        if not rfq:
            raise NotFound("RFQ not found.")
        return Response(dict(VendorQuotationRFQSerializer(rfq).data))

    # ── extra action ───────────────────────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = VendorQuotation.objects.all()
        data = {
            "total": qs.count(),
            "draft": qs.filter(status="Draft").count(),
            "submitted": qs.filter(status="Submitted").count(),
            "under_review": qs.filter(status="Under Review").count(),
            "accepted": qs.filter(status="Accepted").count(),
        }
        return Response(data)

    @action(detail=False, methods=["get"], url_path="simple-quotation-validation")
    def simple_quotation_validation(self, request):
        """Lightweight endpoint for duplicate quotation validation.

        Returns only RFQ numbers and vendor emails to check if a vendor
        has already submitted a quotation for a given RFQ.

        Optional query param: ?rfq_no=<rfq_number> to filter by specific RFQ.
        """
        from django.db.models import Q

        rfq_no = (request.query_params.get("rfq_no") or "").strip()

        quotations = VendorQuotation.objects.filter(
            Q(vendor__isnull=False) | Q(direct_vendor_email__isnull=False)
        )

        if rfq_no:
            quotations = quotations.filter(rfq__rfq_number__iexact=rfq_no)

        quotations = quotations.values(
            "rfq__rfq_number",
            "rfq_id",
            "vendor__email",
            "direct_vendor_email",
        )

        result = {}
        for q in quotations:
            rfq_number = q["rfq__rfq_number"]
            rfq_id = q["rfq_id"]
            email = q["vendor__email"] or q["direct_vendor_email"]
            if not email:
                continue

            key = rfq_number or str(rfq_id)
            if key not in result:
                result[key] = {"rfqNumber": rfq_number, "rfqId": rfq_id, "vendors": []}

            email_lower = email.lower()
            if not any(v["email"] == email_lower for v in result[key]["vendors"]):
                result[key]["vendors"].append({"email": email_lower})

        return Response(list(result.values()))

    # ── Direct Evaluation ──────────────────────────────────────────────────

    @action(detail=False, methods=["post"], url_path="direct-evaluation")
    @transaction.atomic
    def direct_evaluation(self, request):
        """Create a vendor quotation + award for a one-off vendor without a VendorProfile.

        Pipeline:
        1. Validate payload.
        2. Create VendorQuotation (vendor=None, is_direct_evaluation=True).
        3. Auto-create a minimal approved ComparativeStatement linked to the RFQ.
        4. Create an Award immediately (status=active).
        5. Create a ProcurementNotification for the submitting user.
        6. Return quotation + award identifiers.
        """
        serializer = DirectEvaluationSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        rfq = data["rfq"]
        items = data["items"]

        # Build price_proposal JSON from submitted items
        price_proposal = [
            {
                "item_name": item["item_name"],
                "description": item.get("description", ""),
                "specification": item.get("specification", ""),
                "unit": item.get("unit", ""),
                "quantity": item["quantity"],
                "proposed_price": float(item["unit_price"]),
                "total": float(
                    item.get("total", item["quantity"] * item["unit_price"])
                ),
                "remarks": item.get("remarks", ""),
            }
            for item in items
        ]

        # Compute totals
        subtotal = sum(Decimal(str(i["total"])) for i in price_proposal)
        discount_pct = Decimal(str(data.get("discount_percentage", 0)))
        tax_amount = Decimal(str(data.get("tax_amount", 0)))
        discount_value = subtotal * (discount_pct / Decimal("100"))
        grand_total = subtotal - discount_value + tax_amount

        # 1 ─ Create VendorQuotation
        selected_vendor = data.get("vendor")
        direct_vendor_name = data.get("vendor_name") if data.get("vendor_name") else None
        direct_vendor_email = data.get("vendor_email") if data.get("vendor_email") else None
        direct_vendor_phone = data.get("vendor_phone") if data.get("vendor_phone") else None
        direct_vendor_address = data.get("vendor_address") if data.get("vendor_address") else None

        if selected_vendor:
            direct_vendor_name = direct_vendor_name or selected_vendor.name or selected_vendor.company_name
            direct_vendor_email = direct_vendor_email or selected_vendor.email
            direct_vendor_phone = (
                direct_vendor_phone
                or selected_vendor.phone
                or selected_vendor.office_phone
                or ""
            )
            direct_vendor_address = direct_vendor_address or selected_vendor.address or ""

        quotation = VendorQuotation.objects.create(
            rfq=rfq,
            vendor=selected_vendor,
            is_direct_evaluation=True,
            direct_vendor_name=direct_vendor_name,
            direct_vendor_email=direct_vendor_email,
            direct_vendor_phone=direct_vendor_phone,
            direct_vendor_address=direct_vendor_address,
            direct_evaluation_justification=data.get("justification", ""),
            delivery_terms=data.get("delivery_terms", ""),
            payment_terms=data.get("payment_terms", ""),
            warranty_terms=data.get("warranty_terms", ""),
            validity_date=data.get("validity_date"),
            discount_percentage=discount_pct,
            tax_amount=tax_amount,
            total_amount=subtotal,
            grand_total=grand_total,
            submission_date=timezone.now(),
            status="accepted",
            price_proposal=price_proposal,
            created_by=request.user,
        )

        # Persist direct evaluation lines as quotation items so the CS/quotation item list stays consistent.
        for item in items:
            QuotationItem.objects.create(
                quotation=quotation,
                item_id=item.get("item_id"),
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                remarks=item.get("remarks", ""),
            )

        # 2 ─ Auto-create a minimal approved ComparativeStatement
        cs = ComparativeStatement.objects.create(
            rfq=rfq,
            title=f"Direct Evaluation – {rfq.rfq_number}",
            status="approved",
            auto_extracted=False,
            created_by=request.user,
            approved_by=request.user,
            approved_date=timezone.now(),
        )
        cs.quotations.add(quotation)

        # 3 ─ Create Award immediately
        award = Award.objects.create(
            comparative_statement=cs,
            rfq=rfq,
            vendor_profile=None,
            title=f"Direct Evaluation Award – {rfq.rfq_number} / {data['vendor_name']}",
            description=data.get("justification", ""),
            total_amount=grand_total,
            award_date=timezone.now().date(),
            notification_date=timezone.now().date(),
            acceptance_date=timezone.now().date(),
            payment_terms=data.get("payment_terms", ""),
            delivery_timeline=data.get("delivery_terms", ""),
            justification=data.get("justification", ""),
            status="active",
            notification_status="sent",  # no portal vendor; skip portal notification
            acceptance_status="accepted",
            awarded_by=request.user,
        )

        # 4 ─ Internal notification for submitting user
        ProcurementNotification.objects.create(
            recipient=request.user,
            title=f"Direct Evaluation submitted for {rfq.rfq_number}",
            message=(
                f"A direct evaluation quotation from {data['vendor_name']} "
                f"was recorded for RFQ {rfq.rfq_number}. "
                f"Award {award.award_number} has been created."
            ),
            notification_type="Quotation",
            priority="Medium",
            reference_type="Award",
            reference_id=award.id,
        )

        # Attach award to quotation instance for the response serializer
        quotation._created_award = award

        response_serializer = DirectEvaluationResponseSerializer(quotation)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class QuotationItemViewSet(viewsets.ModelViewSet):
    queryset = QuotationItem.objects.select_related("quotation", "item").all()
    serializer_class = QuotationItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["quotation"]


class QuotationOpeningViewSet(CreatedByMixin, viewsets.ModelViewSet):
    queryset = (
        QuotationOpening.objects.select_related("rfq", "opened_by")
        .prefetch_related("committee_members")
        .all()
    )
    serializer_class = QuotationOpeningSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status"]
    ordering = ["-opening_date"]

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(opened_by=self.request.user)
