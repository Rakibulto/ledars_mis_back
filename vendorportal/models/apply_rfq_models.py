from django.db import models
from django.db.models import Sum
from django.core.validators import FileExtensionValidator
from django.conf import settings
from procurement.models.rfq_models import RFQ
from ..models.invitation_rfq_models import Invitation_rfq
# vendor submission models for RFQs


class PriceProposal(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Submitted', 'Submitted'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
        ('Negotiating', 'Under Negotiation'),
    ]

    apply_rfq       = models.ForeignKey('ApplyRFQ', on_delete=models.CASCADE, related_name='price_proposals')
    item            = models.ForeignKey('inventory.Item', on_delete=models.CASCADE, related_name='price_proposals')
    proposed_price  = models.DecimalField(max_digits=12, decimal_places=2, help_text='Proposed unit price')
    quantity        = models.DecimalField(max_digits=12, decimal_places=2, default=1, help_text='Proposed quantity')
    total_price     = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text='Total price (auto-calculated)')
    delivery_days   = models.PositiveIntegerField(help_text='Estimated delivery days after order confirmation')
    delivery_terms  = models.TextField(blank=True, null=True, help_text='Specific delivery terms and conditions')
    validity_days   = models.PositiveIntegerField(default=30, help_text='How many days this proposal is valid')
    payment_terms   = models.CharField(max_length=150, blank=True, null=True, help_text='Proposed payment terms')
    warranty_period = models.CharField(max_length=100, blank=True, null=True, help_text='Warranty period offered')
    technical_specs = models.TextField(blank=True, null=True, help_text='Technical specifications or compliance notes')
    comments        = models.TextField(blank=True, null=True, help_text='Additional comments or notes')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    created_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_price_proposals',
    )

    class Meta:
        ordering = ['-created_at']
        unique_together = [('apply_rfq', 'item')]

    def __str__(self):
        return f"PriceProposal: {self.apply_rfq} - {self.item}"




class ApplyRFQStatusLog(models.Model):
    rfq_number = models.ForeignKey(
        RFQ, on_delete=models.CASCADE, related_name="status_logs"
    )
    status = models.CharField(max_length=20, null=True, blank=True)
    action = models.CharField(max_length=100, null=True, blank=True)
    comments = models.TextField(null=True, blank=True)
    acted_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.rfq_number} {self.from_status or 'New'} -> {self.to_status}"
    


class ApplyRFQAttachment(models.Model):

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Under Review', 'Under Review'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    TYPE_CHOICES = [
        ('License', 'License'),
        ('Document', 'Document'),
        ('Certificate', 'Certificate'),
        ('Other', 'Other'),
    ]

    rfq_number = models.ForeignKey(
        RFQ, on_delete=models.CASCADE, related_name="attachments"
    )
    name = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    file = models.FileField(
        upload_to="material_requisitions/attachments/", null=True, blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "doc",
                    "docx",
                    "xls",
                    "xlsx",
                    "jpg",
                    "jpeg",
                    "png",
                    "svg",
                    "gif",
                    "webp",
                ])
        ],
    )

    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    reviewer_comment = models.TextField(blank=True, null=True)
    expires_at = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateField(auto_now_add=True) 
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def filename(self):
        return self.file.name.split("/")[-1] if self.file else None

    def __str__(self):
        return f"{self.rfq_number} - {self.filename or self.pk}"



class ApplyRFQ(models.Model):
    profile = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.CASCADE,
        related_name="apply_rfq",
        blank=True,
    )
    invitation_rfq = models.ForeignKey(Invitation_rfq, on_delete=models.CASCADE, related_name="apply_rfq")

    submission_note = models.TextField(blank=True, null=True, help_text="Additional notes from supplier during submission")

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_price_proposal(self):
        total = self.price_proposals.aggregate(total=Sum('total_price'))['total']
        return total or 0

    def __str__(self):
        return f"ApplyRFQ: {self.invitation_rfq.rfq_number.rfq_number} by {self.profile.name if self.profile else 'Unknown'}"




# ******************************submission models for vendor portal******************************


class VendorRFQSubmission(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("under_review", "Under Review"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    RECOMMENDED_STATUS_CHOICES = [
        ("withdraw", "Withdraw"),
        ("skip", "Skip"),
        ("decline", "Decline"),
        ("accept", "Accept"),
    ]

    rfq = models.ForeignKey(
        RFQ, on_delete=models.CASCADE, related_name="vendor_submissions"
    )
    # vendor info (denormalised from vendor profile at time of submission)
    vendor_id   = models.IntegerField()
    vendor_name = models.CharField(max_length=255)
    designation = models.CharField(max_length=255, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    recommended_status = models.CharField(
        max_length=20,
        choices=RECOMMENDED_STATUS_CHOICES,
        blank=True,
        null=True,
    )
    is_recommended = models.BooleanField(default=False)

    # additional_info block
    warranty_period    = models.CharField(max_length=100, blank=True, null=True)
    additional_remarks = models.TextField(blank=True, null=True)
    declaration        = models.BooleanField(default=False)

    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    created_by   = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_submissions",
    )

    class Meta:
        ordering = ["-created_at"]
        # one submission per vendor per RFQ — comment out during dev if needed
        # unique_together = [["rfq", "vendor_id"]]

    def __str__(self):
        return f"Submission: {self.rfq.rfq_number} by Vendor #{self.vendor_id}"


# ─────────────────────────────────────────────────────────────────────────────
# Technical Proposal
# ─────────────────────────────────────────────────────────────────────────────

class TechnicalProposal(models.Model):
    submission = models.OneToOneField(
        VendorRFQSubmission,
        on_delete=models.CASCADE,
        related_name="technical_proposal",
    )
    company_experience = models.TextField(blank=True, null=True)
    methodology        = models.TextField(blank=True, null=True)
    updated_at         = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"TechnicalProposal → {self.submission}"


class ComplianceItem(models.Model):
    COMPLIANT_CHOICES = [
        ("Yes",     "Yes"),
        ("Partial", "Partial"),
        ("No",      "No"),
    ]

    technical_proposal = models.ForeignKey(
        TechnicalProposal,
        on_delete=models.CASCADE,
        related_name="compliance_items",
    )
    line_item_id  = models.IntegerField(blank=True, null=True)
    item_name     = models.CharField(max_length=255, blank=True, null=True)
    required_spec = models.TextField(blank=True, null=True)
    offered_spec  = models.TextField(blank=True, null=True)
    compliant     = models.CharField(max_length=10, choices=COMPLIANT_CHOICES, default="Yes")

    def __str__(self):
        return f"{self.item_name} — {self.compliant}"


# ─────────────────────────────────────────────────────────────────────────────
# Financial Proposal
# ─────────────────────────────────────────────────────────────────────────────

class FinancialProposal(models.Model):
    submission = models.OneToOneField(
        VendorRFQSubmission,
        on_delete=models.CASCADE,
        related_name="financial_proposal",
    )
    sub_total              = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    vat                    = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ait                    = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    delivery_charge        = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    grand_total            = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_terms          = models.CharField(max_length=255, blank=True, null=True)
    quotation_validity_days = models.IntegerField(null=True, blank=True)
    delivery_lead_time_days = models.IntegerField(null=True, blank=True)
    updated_at             = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.grand_total = (
            (self.sub_total or 0)
            + (self.vat or 0)
            + (self.ait or 0)
            + (self.delivery_charge or 0)
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"FinancialProposal → {self.submission}"


class FinancialItem(models.Model):
    financial_proposal = models.ForeignKey(
        FinancialProposal,
        on_delete=models.CASCADE,
        related_name="items",
    )
    line_item_id = models.IntegerField()
    item_name    = models.CharField(max_length=255)
    description  = models.TextField(blank=True, null=True)
    qty          = models.IntegerField(default=1)
    unit         = models.CharField(max_length=50, blank=True, null=True)
    unit_price   = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total        = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.item_name} ×{self.qty}"


# ─────────────────────────────────────────────────────────────────────────────
# Submission Documents
# ─────────────────────────────────────────────────────────────────────────────

class SubmissionDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ("trade_license",        "Trade License"),
        ("tin_certificate",      "TIN Certificate"),
        ("vat_registration",     "VAT Registration (BIN)"),
        ("company_registration", "Company Registration Certificate"),
        ("bank_solvency",        "Bank Solvency Certificate"),
        ("other",                "Other"),
    ]

    submission = models.ForeignKey(
        VendorRFQSubmission,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    doc_name = models.CharField(max_length=255)          # label from RFQ required_documents
    doc_type = models.CharField(max_length=50, choices=DOC_TYPE_CHOICES, default="other")
    file = models.FileField(
        upload_to="vendor_submissions/documents/",
        validators=[FileExtensionValidator(
            allowed_extensions=["pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png"]
        )],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    @property
    def filename(self):
        return self.file.name.split("/")[-1] if self.file else None

    def __str__(self):
        return f"{self.doc_name} → {self.submission_id}"