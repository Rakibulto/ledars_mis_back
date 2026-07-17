import calendar
from datetime import date, datetime
from django.db import models, transaction
from django.utils import timezone
from authentication.models import User


class FiscalYear(models.Model):
    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("active", "Active"),
        ("closed", "Closed"),
    )

    code = models.CharField(max_length=20, unique=True, blank=True)
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    total_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    spent = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    description = models.TextField(null=True, blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_fiscal_years",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Fiscal Year"
        verbose_name_plural = "Fiscal Years"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.code:
            start_year = self.start_date.year
            end_year = self.end_date.year
            # Ensure uniqueness if same years exist
            base_code = f"FY-{start_year}-{end_year}"
            code = base_code
            counter = 1
            while FiscalYear.objects.filter(code=code).exclude(pk=self.pk).exists():
                code = f"{base_code}-{counter}"
                counter += 1
            self.code = code
        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new:
                self._generate_periods()

    def _generate_periods(self):
        """Auto-generate monthly accounting periods for this fiscal year."""
        current = self.start_date
        period_num = 1
        while current <= self.end_date and period_num <= 12:
            _, last_day = calendar.monthrange(current.year, current.month)
            period_end = date(current.year, current.month, last_day)
            if period_end > self.end_date:
                period_end = self.end_date
            AccountingPeriod.objects.create(
                fiscal_year=self,
                period_number=period_num,
                start_date=current,
                end_date=period_end,
                status="open",
            )
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)
            period_num += 1

    @property
    def periods(self):
        return self.accounting_periods.count()

    @property
    def closed_periods(self):
        return self.accounting_periods.filter(status="closed").count()

    def __str__(self):
        return self.name


class AccountingPeriod(models.Model):
    STATUS_CHOICES = (
        ("open", "Open"),
        ("closed", "Closed"),
    )

    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.CASCADE,
        related_name="accounting_periods",
    )
    period_number = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    closed_date = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_accounting_periods",
    )

    class Meta:
        ordering = ["period_number"]
        unique_together = [("fiscal_year", "period_number")]
        verbose_name = "Accounting Period"
        verbose_name_plural = "Accounting Periods"

    @property
    def month_name(self):
        return self.start_date.strftime("%B %Y") if self.start_date else ""

    @property
    def closed_by_name(self):
        return self.closed_by.username if self.closed_by else ""

    def close(self, user=None):
        with transaction.atomic():
            self.status = "closed"
            self.closed_date = timezone.now()
            self.closed_by = user
            self.save()

    def reopen(self):
        with transaction.atomic():
            self.status = "open"
            self.closed_date = None
            self.closed_by = None
            self.save()

    def __str__(self):
        return f"{self.fiscal_year.name} — Period {self.period_number} ({self.month_name})"
