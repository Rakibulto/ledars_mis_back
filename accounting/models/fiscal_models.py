from django.db import models


class FiscalYear(models.Model):
    """Accounting fiscal year definition."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("open", "Open"),
        ("closed", "Closed"),
    ]
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def save(self, *args, **kwargs):
        if not self.pk and not self.code:
            start_year = self.start_date.year if self.start_date else 'XXXX'
            end_year = self.end_date.year if self.end_date else 'XXXX'
            prefix = f"FY-{start_year}-{end_year}-"
            existing_nums = list(
                FiscalYear.objects.filter(code__startswith=prefix)
                .values_list('code', flat=True)
            )
            nums = []
            for c in existing_nums:
                try:
                    nums.append(int(c.replace(prefix, '')))
                except ValueError:
                    pass
            next_num = max(nums) + 1 if nums else 1
            self.code = f"{prefix}{next_num:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class FiscalPeriod(models.Model):
    """Monthly or custom accounting periods within a fiscal year."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("open", "Open"),
        ("closed", "Closed"),
    ]
    fiscal_year = models.ForeignKey(
        FiscalYear, on_delete=models.CASCADE, related_name="periods"
    )
    name = models.CharField(max_length=100)
    number = models.IntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")

    class Meta:
        ordering = ["fiscal_year", "number"]
        unique_together = ["fiscal_year", "number"]

    def __str__(self):
        return f"{self.fiscal_year.code} - {self.name}"
