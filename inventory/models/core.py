from django.db import models
from django.core.exceptions import ValidationError
from authentication.models import User


class Category(models.Model):
    LEVEL_CHOICES = (
        ("Main", "Main"),
        ("Sub", "Sub"),
    )

    STATUS_CHOICES = (
        ("Active", "Active"),
        ("Inactive", "Inactive"),
    )

    COSTING_CHOICES = (
        ("standard", "Standard Price"),
        ("fifo", "First In First Out"),
        ("average", "Average Cost"),
    )

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_categories",
    )

    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    item_count = models.PositiveIntegerField(default=0)
    costing_method = models.CharField(
        max_length=20, choices=COSTING_CHOICES, default="average"
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="Active")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"

    def clean(self):
        if self.level == "Main" and self.parent is not None:
            raise ValidationError(
                {"parent": "Main category cannot have a parent category."}
            )
        if self.level == "Sub":
            if self.parent is None:
                raise ValidationError(
                    {"parent": "Sub category must have a parent category."}
                )
            elif self.parent.level != "Main":
                raise ValidationError(
                    {"parent": "Sub category parent must be a Main category."}
                )

    def save(self, *args, **kwargs):
        if not self.code:
            if self.level == "Main":
                last = Category.objects.filter(level="Main").order_by("-id").first()
                num = 1
                if last and last.code:
                    try:
                        num = int(last.code.split("-")[1]) + 1
                    except (IndexError, ValueError):
                        pass
                self.code = f"CAT-{num:03d}"
            elif self.level == "Sub":
                last = Category.objects.filter(level="Sub").order_by("-id").first()
                num = 1
                if last and last.code:
                    try:
                        num = int(last.code.split("-")[2]) + 1
                    except (IndexError, ValueError):
                        pass
                self.code = f"CAT-SUB-{num:03d}"
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name or self.pk} ({self.code or self.pk})"


class UnitOfMeasure(models.Model):
    name = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Unit of Measure"
        verbose_name_plural = "Units of Measure"

    def __str__(self):
        return self.name
