from django.db import models
from django.conf import settings


class FinalSettlement(models.Model):

    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Submitted', 'Submitted'),
        ('Under_Review', 'Under Review'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Payment_Pending', 'Payment Pending'),
        ('Completed', 'Completed'),
    ]

    # Header fields
    project_name = models.CharField(max_length=255)
    date = models.DateField()
    name_of_staff = models.CharField(max_length=255)
    designation = models.CharField(max_length=255)
    joining_date = models.DateField()
    resignation_date = models.DateField()
    supervisor_opinion = models.TextField(blank=True)

    # Financial settlement rows (stored as JSON array)
    # Each item: { sn, particulars, yes_no, amount, due_staff, due_ledars, remarks }
    financial_rows = models.JSONField(default=list)

    # Totals
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_due_staff = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_due_ledars = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    final_payment = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    final_payment_words = models.CharField(max_length=500, blank=True)

    # Loan information rows (JSON array)
    # Each item: { sn, date, amount, last_date_of_payment, remarks }
    loan_rows = models.JSONField(default=list)

    # Declarations
    canteen_declaration = models.TextField(blank=True)
    srizon_declaration = models.TextField(blank=True)

    # Final declaration
    declaration_name = models.CharField(max_length=255, blank=True)
    declaration_amount = models.CharField(max_length=255, blank=True)

    # Status
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default='Draft'
    )

    # Signatures (store user id + name + email + signed_at)
    supervisor_signature = models.JSONField(null=True, blank=True)
    finance_signature = models.JSONField(null=True, blank=True)
    management_signature = models.JSONField(null=True, blank=True)

    # Payment
    payment_completed_at = models.DateTimeField(null=True, blank=True)
    payment_completed_by = models.JSONField(null=True, blank=True)

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='settlements_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name_of_staff} — {self.project_name} ({self.status})"