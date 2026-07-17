from django.contrib import admin
from .models import ProvidentFundLoan


@admin.register(ProvidentFundLoan)
class ProvidentFundLoanAdmin(admin.ModelAdmin):
    list_display = [
        'applicant_name', 'designation', 'program_name',
        'expected_loan_amount', 'status', 'created_at',
    ]
    list_filter = ['status']
    search_fields = ['applicant_name', 'program_name']
    readonly_fields = [
        'created_by', 'created_at', 'updated_at',
        'supervisor_signature', 'upper_authority_signature',
        'accounts_officer_signature', 'trust_member_1_signature',
        'trust_member_2_signature', 'recommender_signature',
        'recorder_signature', 'approver_signature',
    ]
