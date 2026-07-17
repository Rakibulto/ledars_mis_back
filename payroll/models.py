from django.db import models
from authentication.models import User
from employee.models import Employee

# Create your models here.


class Payroll(models.Model):
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="payroll_creator",
        blank=True,
        null=True,
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="payroll_employee",
        blank=True,
        null=True,
    )
    is_locked = models.BooleanField(default=False)
    payroll_month = models.CharField(
        max_length=20, blank=True, null=True
    )  # Format: "January"
    payroll_year = models.IntegerField(blank=True, null=True)  # Format: 2026
    days_of_month = models.IntegerField(blank=True, null=True)
    working_days = models.IntegerField(blank=True, null=True)
    present_days = models.IntegerField(blank=True, null=True)
    late_days = models.IntegerField(blank=True, null=True)
    absent_days = models.IntegerField(blank=True, null=True)
    weekend_days = models.IntegerField(blank=True, null=True)
    holidays = models.IntegerField(blank=True, null=True)
    leave_breakdown = models.JSONField(
        blank=True, null=True
    )  # Policy wise leave breakdown(It will come from LeaveRequest model)
    basic = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    house_rent = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    conveyance = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    medical = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    gross_salary = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    festival_bonus = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    performance_bonus = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    absence_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    late_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    holiday_compensation = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    weekday_compensation = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    net_salary = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    tax_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    total_transfer_amount = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
