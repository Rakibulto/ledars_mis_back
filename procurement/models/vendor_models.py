from django.db import models


class VendorCategory(models.Model):
    """Vendor categorization for procurement classification."""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Vendor Categories"

    def __str__(self):
        return self.name


class VendorCategoryMapping(models.Model):
    """Map vendors to multiple vendor categories."""

    supplier = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.CASCADE,
        related_name="category_mappings",
    )
    category = models.ForeignKey(
        VendorCategory, on_delete=models.CASCADE, related_name="vendor_mappings"
    )

    class Meta:
        unique_together = ["supplier", "category"]

    def __str__(self):
        return f"{self.supplier} - {self.category}"


class VendorEvaluation(models.Model):
    """Periodic performance evaluation of vendors."""

    RATING_CHOICES = [
        (1, "Poor"),
        (2, "Below Average"),
        (3, "Average"),
        (4, "Good"),
        (5, "Excellent"),
    ]

    supplier = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.CASCADE,
        related_name="evaluations",
    )
    evaluation_date = models.DateField()
    quality_rating = models.IntegerField(choices=RATING_CHOICES, default=3)
    delivery_rating = models.IntegerField(choices=RATING_CHOICES, default=3)
    price_rating = models.IntegerField(choices=RATING_CHOICES, default=3)
    compliance_rating = models.IntegerField(choices=RATING_CHOICES, default=3)
    communication_rating = models.IntegerField(choices=RATING_CHOICES, default=3)
    overall_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    comments = models.TextField(null=True, blank=True)
    recommendation = models.TextField(null=True, blank=True)

    evaluated_by = models.ForeignKey(
        "employee.Employee", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-evaluation_date"]

    def save(self, *args, **kwargs):
        ratings = [
            self.quality_rating,
            self.delivery_rating,
            self.price_rating,
            self.compliance_rating,
            self.communication_rating,
        ]
        self.overall_rating = sum(ratings) / len(ratings)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Eval - {self.supplier} - {self.evaluation_date}"


class VendorOnboarding(models.Model):
    """Vendor onboarding checklist and status tracking."""

    STATUS_CHOICES = [
        ("Initiated", "Initiated"),
        ("Documents Pending", "Documents Pending"),
        ("Under Verification", "Under Verification"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
    ]

    supplier = models.OneToOneField(
        "vendorportal.VendorProfile",
        on_delete=models.CASCADE,
        related_name="onboarding",
    )
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="Initiated"
    )
    trade_license = models.BooleanField(default=False)
    tax_certificate = models.BooleanField(default=False)
    bank_details = models.BooleanField(default=False)
    nda_signed = models.BooleanField(default=False)
    reference_verified = models.BooleanField(default=False)
    compliance_checked = models.BooleanField(default=False)
    remarks = models.TextField(null=True, blank=True)

    initiated_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    completed_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Onboarding - {self.supplier} - {self.status}"


class VendorVerification(models.Model):
    """Vendor verification status for compliance."""

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Verified", "Verified"),
        ("Suspended", "Suspended"),
        ("Blacklisted", "Blacklisted"),
    ]

    supplier = models.OneToOneField(
        "vendorportal.VendorProfile",
        on_delete=models.CASCADE,
        related_name="verification",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    verification_date = models.DateField(null=True, blank=True)
    documents_verified = models.BooleanField(default=False)
    financial_check = models.BooleanField(default=False)
    compliance_check = models.BooleanField(default=False)
    remarks = models.TextField(null=True, blank=True)

    verified_by = models.ForeignKey(
        "employee.Employee", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Verification - {self.supplier} - {self.status}"


class VendorPerformance(models.Model):
    """Monthly vendor performance metrics for reporting."""

    supplier = models.ForeignKey(
        "vendorportal.VendorProfile",
        on_delete=models.CASCADE,
        related_name="performance_records",
    )
    period_month = models.IntegerField()
    period_year = models.IntegerField()
    total_orders = models.PositiveIntegerField(default=0)
    on_time_deliveries = models.PositiveIntegerField(default=0)
    late_deliveries = models.PositiveIntegerField(default=0)
    rejected_items = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    avg_delivery_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    compliance_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_year", "-period_month"]
        unique_together = ["supplier", "period_month", "period_year"]

    def __str__(self):
        return f"{self.supplier} - {self.period_month}/{self.period_year}"
