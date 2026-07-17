from django.conf import settings
from django.db import models


class ProvidentFundLoan(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    # --- Page 1: Applicant Info ---
    application_date = models.DateField(null=True, blank=True)
    applicant_name = models.CharField(max_length=255, null=True, blank=True)
    designation = models.CharField(max_length=255, null=True, blank=True)
    joining_date = models.DateField(null=True, blank=True)
    permanent_date = models.DateField(null=True, blank=True)
    monthly_installment_count = models.IntegerField(null=True, blank=True)
    monthly_total_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    current_workplace = models.CharField(max_length=255, null=True, blank=True)
    program_name = models.CharField(max_length=255, null=True, blank=True)
    expected_loan_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    loan_purpose = models.TextField(null=True, blank=True)
    applicant_signature_date = models.DateField(null=True, blank=True)

    # --- Supervisor Recommendation ---
    supervisor_recommendation = models.TextField(null=True, blank=True)
    supervisor_name = models.CharField(max_length=255, null=True, blank=True)
    supervisor_designation = models.CharField(max_length=255, null=True, blank=True)
    supervisor_signature = models.JSONField(null=True, blank=True)

    # --- Upper Authority Recommendation ---
    upper_authority_recommendation = models.TextField(null=True, blank=True)
    upper_authority_name = models.CharField(max_length=255, null=True, blank=True)
    upper_authority_designation = models.CharField(max_length=255, null=True, blank=True)
    upper_authority_signature = models.JSONField(null=True, blank=True)

    # --- Page 2: Accounts Officer Section ---
    pf_total_balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    own_contribution = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    org_contribution = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_loan_eligible = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    monthly_interest_principal = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    interest_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    installment_count = models.IntegerField(null=True, blank=True)
    repayment_months = models.IntegerField(null=True, blank=True)
    accounts_officer_name = models.CharField(max_length=255, null=True, blank=True)
    accounts_officer_designation = models.CharField(max_length=255, null=True, blank=True)
    accounts_officer_signature = models.JSONField(null=True, blank=True)

    # --- PF Trust Board Members ---
    trust_member_1_name = models.CharField(max_length=255, null=True, blank=True)
    trust_member_1_signature = models.JSONField(null=True, blank=True)
    trust_member_2_name = models.CharField(max_length=255, null=True, blank=True)
    trust_member_2_signature = models.JSONField(null=True, blank=True)

    # --- Member Secretary ---
    secretary_approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # --- Final 3 Signatures ---
    recommender_signature = models.JSONField(null=True, blank=True)
    recorder_signature = models.JSONField(null=True, blank=True)
    approver_signature = models.JSONField(null=True, blank=True)

    # --- Status ---
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # --- Audit ---
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_pf_loans',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.applicant_name or 'Untitled'} - {self.program_name or ''}"
