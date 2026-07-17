from django.db import models
from django.utils import timezone
from django.db.models import Max
from authentication.models import Role, User



class VendorProfile(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Active', 'Active'),
    ]

    VERIFICATION_CHOICES = [
        ("pending", "Pending"),
        ("under-review", "Under Review"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
    ]

    ACCOUNT_TYPE_CHOICES = [
        ('Savings Account', 'Savings Account'),
        ('Current Account', 'Current Account'),
    ]

    ORGANIZATION_TYPE_CHOICES = [
        ("sole_proprietorship", "Sole Proprietorship"),
        ("partnership", "Partnership"),
        ("limited_company", "Limited Company"),
        ('Cooperative Society', 'Cooperative Society'),
        ('Private_Company', 'Private Company'),
        ('NGO', 'NGO'),
        ("Other", "Other"),
    ]

    # 🔹 Basic Info
    code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    legal_name = models.CharField(max_length=255, blank=True, null=True)
    company_name_bn = models.CharField(max_length=255, blank=True, null=True)

    year_established = models.PositiveIntegerField(blank=True, null=True)
    organization_type = models.CharField(max_length=100, choices=ORGANIZATION_TYPE_CHOICES, blank=True, null=True)
    annual_turnover = models.CharField(max_length=100, blank=True, null=True)

    # 🔹 Contact Info
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    designation = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    office_phone = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)

    # 🔹 Identity
    nid_passport = models.CharField(max_length=100, blank=True, null=True)
    tax_id = models.CharField(max_length=100, blank=True, null=True)
    bin_number = models.CharField(max_length=100, blank=True, null=True)
    trade_license_number = models.CharField(max_length=100, blank=True, null=True)

    # 🔹 Address
    address = models.TextField(blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    division = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)

    # 🔹 Business Stats
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, blank=True, null=True)
    total_orders = models.PositiveIntegerField(default=0, blank=True, null=True)
    active_contracts = models.PositiveIntegerField(default=0, blank=True, null=True)

    # 🔹 Status
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending', blank=True, null=True)
    verification_state = models.CharField(max_length=50, choices=VERIFICATION_CHOICES, default='pending', blank=True, null=True)

    registration_date = models.DateField(auto_now_add=True, blank=True, null=True)
    enlistment_year = models.PositiveIntegerField(blank=True, null=True)
    trade_license_expiry = models.DateField(blank=True, null=True)

    # 🔹 Detailed Address (from PDF Section A field 3)
    village_road = models.CharField(max_length=255, blank=True, null=True)
    house_number = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)

    # 🔹 Proprietor Information (from PDF Section A field 2)
    proprietor_name = models.CharField(max_length=255, blank=True, null=True)
    proprietor_title = models.CharField(max_length=255, blank=True, null=True)
    proprietor_cell = models.CharField(max_length=20, blank=True, null=True)
    proprietor_email = models.EmailField(blank=True, null=True)

    # 🔹 Business Details (from PDF Section A fields 6-8)
    nature_of_business = models.CharField(max_length=255, blank=True, null=True)
    other_branch_name = models.CharField(max_length=255, blank=True, null=True)
    other_branch_address = models.TextField(blank=True, null=True)
    other_branch_cell = models.CharField(max_length=20, blank=True, null=True)
    other_branch_email = models.EmailField(blank=True, null=True)
    other_branch_website = models.URLField(blank=True, null=True)
    last_year_clients = models.JSONField(default=list, blank=True, null=True)

    # 🔹 Licensing & Tax (from PDF Section A fields 9-13)
    trade_license_valid_date = models.DateField(blank=True, null=True)
    tax_return_acknowledgement = models.BooleanField(default=False, blank=True, null=True)
    others_license_no = models.CharField(max_length=255, blank=True, null=True)

    # 🔹 Declaration (from PDF Section B signature block)
    declaration_name_title = models.CharField(max_length=255, blank=True, null=True)
    declaration_company_name = models.CharField(max_length=255, blank=True, null=True)
    declaration_date = models.DateField(blank=True, null=True)

    # 🔹 Banking
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    branch_name = models.CharField(max_length=255, blank=True, null=True)
    account_name = models.CharField(max_length=255, blank=True, null=True)
    account_number = models.CharField(max_length=100, blank=True, null=True)
    routing_number = models.CharField(max_length=50, blank=True, null=True)
    account_type = models.CharField(max_length=50, choices=ACCOUNT_TYPE_CHOICES, blank=True, null=True)
    swift_code = models.CharField(max_length=100, blank=True, null=True)

    # 🔹 Relations
    categories = models.ManyToManyField("inventory.Category", related_name='vendors')
    notes = models.TextField(null=True, blank=True)
    user = models.ForeignKey(   # user_info (vendor user)
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendor_profile'
    )

    created_by = models.ForeignKey(   # admin who created
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_vendors'
    )

    # 🔹 Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip()
            matched_user = User.objects.filter(email__iexact=self.email).first()
            self.user = matched_user
            if matched_user:
                vendor_role, _ = Role.objects.get_or_create(name='Vendor')
                if matched_user.role != vendor_role:
                    matched_user.role = vendor_role
                    matched_user.save(update_fields=['role'])
        else:
            self.user = None

        if not self.code:
            year = timezone.now().year

            last_vendor = VendorProfile.objects.filter(
                code__startswith=f"VEN-{year}"
            ).aggregate(Max("code"))

            last_code = last_vendor["code__max"]

            if last_code:
                last_number = int(last_code.split("-")[-1])
                new_number = last_number + 1
            else:
                new_number = 1

            self.code = f"VEN-{year}-{str(new_number).zfill(4)}"

        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.code or self.pk} - {self.company_name_bn or self.pk}"



class VendorDocument(models.Model):
    REVIEW_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Verified', 'Verified'),
        ('Rejected', 'Rejected'),
    ]


    vendor = models.ForeignKey(
        VendorProfile,
        on_delete=models.CASCADE,
        related_name='documents'
    )

    doc_type = models.CharField(max_length=255, null=True, blank=True)

    file = models.FileField(upload_to='vendors/documents/%Y/%m/')

    expiry_date = models.DateField(blank=True, null=True)

    # 🔹 Review System
    review_status = models.CharField(
        max_length=20,
        choices=REVIEW_STATUS_CHOICES,
        default='pending'
    )

    reviewer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_documents'
    )

    rejection_reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    review_date = models.DateTimeField(blank=True, null=True)

    # 🔹 Timestamps
    created_by = models.ForeignKey(   # admin who created
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_document'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vendor.company_name_bn or self.pk} - {self.doc_type or self.pk}"


class VendorBlacklist(models.Model):
    """Record of blacklisted vendors."""

    CATEGORY_CHOICES = [
        ("Fraud", "Fraud"),
        ("Performance", "Performance"),
        ("Conflict of Interest", "Conflict of Interest"),
        ("Quality", "Quality"),
        ("Ethics", "Ethics"),
        ("Other", "Other"),
    ]

    DURATION_CHOICES = [
        ("Permanent", "Permanent"),
        ("Under Review", "Under Review"),
        ("6 months", "6 months"),
        ("12 months", "12 months"),
        ("24 months", "24 months"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("pending", "Pending"),
    ]

    blacklist_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    supplier = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blacklist_records",
    )
    vendor_name_snapshot = models.CharField(max_length=500, null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, null=True, blank=True)
    blacklisted_date = models.DateField(null=True, blank=True, default=timezone.now)
    blacklisted_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blacklist_actions",
    )
    blacklisted_by_name = models.CharField(max_length=255, null=True, blank=True)
    duration = models.CharField(
        max_length=20, choices=DURATION_CHOICES, default="Under Review"
    )
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    notes = models.TextField(null=True, blank=True)
    previous_contracts = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-blacklisted_date", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.blacklist_number:
            year = timezone.now().year
            count = VendorBlacklist.objects.filter(
                blacklisted_date__year=year
            ).count() + 1
            self.blacklist_number = f"BL-{year}-{count:03d}"
        if self.supplier and not self.vendor_name_snapshot:
            self.vendor_name_snapshot = self.supplier.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.blacklist_number} - {self.vendor_name_snapshot}"


class VendorEnlistment(models.Model):
    """Vendor enlistment application (pre-registration request)."""

    STATUS_CHOICES = [
        ("pending-review", "Pending Review"),
        ("under-evaluation", "Under Evaluation"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    enlistment_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    company_name = models.CharField(max_length=500, null=True, blank=True)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    category = models.CharField(max_length=255, null=True, blank=True)
    submitted_date = models.DateField(null=True, blank=True, default=timezone.now)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending-review"
    )
    tin = models.CharField(max_length=100, null=True, blank=True)
    years_in_business = models.PositiveIntegerField(null=True, blank=True)
    annual_turnover = models.CharField(max_length=220,  null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enlistment_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    supplier = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enlistment_records",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_date", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.enlistment_number:
            year = timezone.now().year
            count = VendorEnlistment.objects.filter(
                submitted_date__year=year
            ).count() + 1
            self.enlistment_number = f"ENL-{year}-{count:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.enlistment_number} - {self.company_name}"
