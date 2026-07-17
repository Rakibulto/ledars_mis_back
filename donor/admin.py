from django.contrib import admin
from .models import Donor, DonorLedger

@admin.register(DonorLedger)
class DonorLedgerAdmin(admin.ModelAdmin):
    list_display = ("ledger_code", "donor", "transaction_type", "amount", "transaction_date")
    search_fields = ("ledger_code", "donor__name", "reference")
    list_filter = ("transaction_type", "is_reconciled")
    readonly_fields = ("ledger_code", "created_at", "updated_at")


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    list_display = ("donor_code", "name", "status", "created_at")
    search_fields = ("donor_code", "name")
    list_filter = ("status",)
    readonly_fields = ("created_at", "updated_at")
