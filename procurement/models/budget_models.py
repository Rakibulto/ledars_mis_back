from django.db import models
from django.db import transaction
from django.utils import timezone



class BudgetSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"
    


class Budget(models.Model):
    code = models.CharField(max_length=50, unique=True, blank=True)  # auto generated
    name = models.CharField(max_length=255, null=True, blank=True)
    department = models.ForeignKey("employee.Department", on_delete=models.SET_NULL, null=True, blank=True)

    allocated_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, blank=True)
    spent = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    fiscal_year = models.CharField(max_length=50, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey("authentication.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Always auto-calculate balance
        self.balance = self.allocated_amount - self.spent

        if not self.code:
            current_year = timezone.now().year

            with transaction.atomic():
                sequence, _ = BudgetSequence.objects.select_for_update().get_or_create(
                    year=current_year,
                    defaults={"last_number": 0}
                )
                sequence.last_number += 1
                sequence.save(update_fields=['last_number'])

                # BDG-2026-0001 format
                self.code = f"BDG-{current_year}-{sequence.last_number:04d}"

        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Budget"
        verbose_name_plural = "Budgets"

    def __str__(self):
        return f"{self.code} - {self.name}"


    

