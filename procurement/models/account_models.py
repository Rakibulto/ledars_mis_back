from django.db import models
from django.db import transaction
from django.utils import timezone



class AccountCategory(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name




class AccountSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"
    


class Account(models.Model):
    code = models.CharField(max_length=50, unique=True, blank=True)  # auto generated
    name = models.CharField(max_length=255, null=True, blank=True)
    category = models.ForeignKey(
        AccountCategory,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='accounts'
    )
    sub_category = models.ForeignKey(
        AccountCategory,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sub_category_accounts'
    )
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, blank=True)
    created_by = models.ForeignKey("authentication.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.code:
            current_year = timezone.now().year

            with transaction.atomic():
                sequence, _ = AccountSequence.objects.select_for_update().get_or_create(
                    year=current_year,
                    defaults={"last_number": 0}
                )
                sequence.last_number += 1
                sequence.save(update_fields=['last_number'])

                # Auto-generate code: ACCT-2026-0001
                self.code = f"ACCT-{current_year}-{sequence.last_number:04d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"