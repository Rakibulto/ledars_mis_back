from django.contrib import admin
from unfold.admin import ModelAdmin
from payroll.models import Payroll


# Register your models here.
@admin.register(Payroll)
class PayrollAdmin(ModelAdmin):
    list_display = [
        "employee",
        "payroll_month",
        "payroll_year",
        "days_of_month",
        "working_days",
        "present_days",
        "absent_days",
        "weekend_days",
        "holidays",
        "holiday_compensation",
        "weekday_compensation",
        "gross_salary",
        "net_salary",
    ]
    search_fields = ["employee__user__username", "employee__employee_id"]
    readonly_fields = ["created_at", "updated_at"]
