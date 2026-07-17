from django.db import models
from accounting.models.perdium_models import Perdium

class PerdiumClaim(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    # Employee info
    employee_name = models.CharField(max_length=255)
    designation = models.CharField(max_length=255, blank=True)
    grade = models.CharField(max_length=10, blank=True)
    area_type = models.CharField(max_length=10, choices=Perdium.AREA_CHOICES, blank=True, null=True)
    purpose_of_travel = models.TextField(blank=True)
    name_of_project = models.CharField(max_length=255, blank=True)

    # Submitted perdiem dates
    from_date = models.DateField(null=True, blank=True)
    to_date = models.DateField(null=True, blank=True)
    total_days = models.PositiveIntegerField(default=0)

    # Claimed quantities
    breakfast_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    breakfast_unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lunch_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lunch_unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    dinner_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    dinner_unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    accommodation_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    accommodation_unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    others_qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    others_unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    amount_in_words = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    # Signature section
    prepared_by = models.CharField(max_length=255, blank=True)
    reviewed_by = models.CharField(max_length=255, blank=True)
    finance_by = models.CharField(max_length=255, blank=True)
    approved_by = models.CharField(max_length=255, blank=True)

    # Signature JSON fields (stores signature image, name, email, signed_at)
    prepared_by_signature = models.JSONField(null=True, blank=True)
    reviewed_by_signature = models.JSONField(null=True, blank=True)
    finance_by_signature = models.JSONField(null=True, blank=True)
    approved_by_signature = models.JSONField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    # Metadata
    date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Perdium Claim - {self.employee_name} ({self.date})"

    @property
    def breakfast_total(self):
        return self.breakfast_qty * self.breakfast_unit_cost

    @property
    def lunch_total(self):
        return self.lunch_qty * self.lunch_unit_cost

    @property
    def dinner_total(self):
        return self.dinner_qty * self.dinner_unit_cost

    @property
    def accommodation_total(self):
        return self.accommodation_qty * self.accommodation_unit_cost

    @property
    def others_total(self):
        return self.others_qty * self.others_unit_cost

    @property
    def grand_total(self):
        return (
            self.breakfast_total + self.lunch_total + self.dinner_total +
            self.accommodation_total + self.others_total
        )
