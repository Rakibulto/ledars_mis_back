from django.db import models


class Currency(models.Model):
    """Multi-currency support."""

    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=5)
    decimal_places = models.IntegerField(default=2)
    is_base = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Currencies"

    def __str__(self):
        return f"{self.code} - {self.name}"


class ExchangeRate(models.Model):
    """Currency exchange rates for multi-currency transactions."""

    currency = models.ForeignKey(
        Currency, on_delete=models.CASCADE, related_name="exchange_rates"
    )
    date = models.DateField()
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    inverse_rate = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    source = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["currency", "date"]

    def __str__(self):
        return f"{self.currency.code} @ {self.date}: {self.rate}"

    def save(self, *args, **kwargs):
        if self.rate and self.rate != 0:
            self.inverse_rate = 1 / self.rate
        super().save(*args, **kwargs)
