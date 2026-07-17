from django.db import models
from authentication.models import User


class ReturnSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Return Sequence'


class ReturnHeader(models.Model):
    RETURN_TYPE_CHOICES = [
        ('project_return', 'Project Item Return'),
        ('internal_transfer_return', 'Internal Transfer Return'),
        ('instant_it_return', 'Instant Internal Transfer Return'),
    ]
    SOURCE_DOC_CHOICES = [
        ('GIN', 'Goods Issue Note'),
        ('INTERNAL_TRANSFER', 'Internal Transfer'),
    ]
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Pending Approval', 'Pending Approval'),
        ('In Transit', 'In Transit'),
        ('Received', 'Received'),
        ('Cancelled', 'Cancelled'),
    ]

    return_number = models.CharField(max_length=30, unique=True, blank=True)
    return_type = models.CharField(max_length=30, choices=RETURN_TYPE_CHOICES)
    source_document_type = models.CharField(max_length=20, choices=SOURCE_DOC_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    return_date = models.DateField()
    source_location = models.CharField(max_length=200, blank=True)
    destination_location = models.CharField(max_length=200, blank=True)
    project = models.CharField(max_length=200, blank=True, null=True,
                               help_text='Project reference (for project_return type)')
    remarks = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_returns'
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_returns'
    )
    received_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_returns'
    )

    # Transport / dispatch details (filled when dispatching)
    transport_person = models.CharField(max_length=200, blank=True, null=True,
                                        help_text='Transport person or courier name')
    transport_phone = models.CharField(max_length=50, blank=True, null=True)
    transport_address = models.TextField(blank=True, null=True)
    vehicle_number = models.CharField(max_length=100, blank=True, null=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    dispatch_date = models.DateField(null=True, blank=True)
    dispatch_remarks = models.TextField(blank=True, null=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Return Header'
        verbose_name_plural = 'Return Headers'

    def __str__(self):
        return self.return_number or f'Return #{self.pk}'

    def save(self, *args, **kwargs):
        if not self.return_number:
            from django.utils import timezone
            year = timezone.now().year
            seq, _ = ReturnSequence.objects.get_or_create(year=year)
            seq.last_number += 1
            seq.save(update_fields=['last_number'])
            self.return_number = f'RET-{year}-{seq.last_number:04d}'
        super().save(*args, **kwargs)


class ReturnLine(models.Model):
    return_header = models.ForeignKey(
        ReturnHeader, on_delete=models.CASCADE, related_name='lines'
    )
    source_document_number = models.CharField(max_length=50, blank=True)
    source_line_id = models.IntegerField(null=True, blank=True,
                                         help_text='PK of the originating GIN or IT line')
    item_name = models.CharField(max_length=255, blank=True)
    item_code = models.CharField(max_length=50, blank=True)
    item = models.IntegerField(null=True, blank=True,
                               help_text='Product/Item ID from the inventory')
    unit = models.CharField(max_length=50, blank=True)
    issued_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    previously_returned_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    return_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    good_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    damaged_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Return Line'
        verbose_name_plural = 'Return Lines'

    def __str__(self):
        return f'{self.return_header} – {self.item_name}'


class ReturnDamageHistory(models.Model):
    return_header = models.ForeignKey(
        ReturnHeader, on_delete=models.CASCADE, related_name='damage_histories'
    )
    return_line = models.ForeignKey(
        ReturnLine, on_delete=models.CASCADE, related_name='damage_records', null=True, blank=True
    )
    item_name = models.CharField(max_length=255, blank=True)
    item_code = models.CharField(max_length=50, blank=True)
    item = models.IntegerField(null=True, blank=True)
    damaged_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    source_document_number = models.CharField(max_length=50, blank=True)
    remarks = models.TextField(blank=True, null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = 'Return Damage History'
        verbose_name_plural = 'Return Damage Histories'

    def __str__(self):
        return f'Damage – {self.return_header} – {self.item_name}'
