from django.db import models


class Perdium(models.Model):
    """Perdium (Daily Allowance and Perdiem Claim Sheet) configuration."""
    
    GRADE_CHOICES = [
        ("H-1", "H-1"),
        ("C-G", "C-G"),
        ("A-B", "A-B"),
    ]
    
    AREA_CHOICES = [
        ("high", "High Expensive Area"),
        ("low", "Low Expensive Area"),
    ]
    
    description = models.TextField(
        help_text="Perdium Description (Human Resource management Manual 3.18 & 3.19)"
    )
    grade = models.CharField(max_length=10, choices=GRADE_CHOICES)
    area_type = models.CharField(max_length=10, choices=AREA_CHOICES)
    
    # Meal rates
    breakfast = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lunch = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    dinner = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    others_expenses = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, help_text="Other expenses"
    )
    
    # Accommodation rate
    accommodation = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        unique_together = ["grade", "area_type"]
    
    def __str__(self):
        return f"Perdium - {self.grade} ({self.get_area_type_display()})"
    
    @property
    def total(self):
        """Calculate total perdium amount."""
        return (
            self.breakfast + self.lunch + self.dinner + 
            self.others_expenses + self.accommodation
        )