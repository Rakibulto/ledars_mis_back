from django.db import models


class OfficeManagement(models.Model):
    LOCATION_TYPE_CHOICES = [
        ("office", "Office"),
        ("warehouse", "Warehouse"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("closed", "Closed"),
    ]

    DIVISION_CHOICES = [
        ("Dhaka", "Dhaka"),
        ("Chattogram", "Chattogram"),
        ("Rajshahi", "Rajshahi"),
        ("Khulna", "Khulna"),
        ("Barishal", "Barishal"),
        ("Sylhet", "Sylhet"),
        ("Rangpur", "Rangpur"),
        ("Mymensingh", "Mymensingh"),
    ]

    office_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )  # OFF-003
    name = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=20, unique=True, null=True, blank=True)  # UKH
    district = models.CharField(max_length=100, null=True, blank=True)
    division = models.CharField(
        max_length=30, choices=DIVISION_CHOICES, null=True, blank=True
    )
    address = models.TextField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True, null=True, blank=True)

    type = models.CharField(
        max_length=50,
        choices=LOCATION_TYPE_CHOICES,
        default="office",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    head_of_office = models.CharField(max_length=255, null=True, blank=True)
    office_contact_person = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="office_contact_for",
    )
    staff_count = models.PositiveIntegerField(default=0, editable=False)

    budget_allocation = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, null=True, blank=True
    )
    budget_utilized = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, null=True, blank=True
    )

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.office_id:
            last_office = OfficeManagement.objects.order_by("-id").first()

            if last_office and last_office.office_id:
                last_number = int(last_office.office_id.split("-")[1])
                new_number = last_number + 1
            else:
                new_number = 1

            self.office_id = f"OFF-{new_number:03d}"  # OFF-001, OFF-002

        super().save(*args, **kwargs)

    def update_staff_count(self):
        if not self.pk:
            return
        staff_total = (
            OfficeStaff.objects.filter(office=self)
            .values_list("user", flat=True)
            .distinct()
            .count()
        )
        if self.staff_count != staff_total:
            self.__class__.objects.filter(pk=self.pk).update(staff_count=staff_total)
            self.staff_count = staff_total

    def __str__(self):
        return f"{self.name} - {self.address} - {self.district}"


class OfficeStaff(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    office = models.ForeignKey(
        OfficeManagement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff",
    )

    user = models.ManyToManyField("authentication.User", blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    def save(self, *args, **kwargs):
        previous_office = None
        if self.pk:
            try:
                previous_office = OfficeStaff.objects.get(pk=self.pk).office
            except OfficeStaff.DoesNotExist:
                previous_office = None

        super().save(*args, **kwargs)

        if previous_office and previous_office != self.office:
            previous_office.update_staff_count()
        if self.office:
            self.office.update_staff_count()

    def delete(self, *args, **kwargs):
        office = self.office
        super().delete(*args, **kwargs)
        if office:
            office.update_staff_count()

    def __str__(self):
        return self.office.name if self.office else str(self.pk)


class Warehouse(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("maintenance", "Maintenance"),
    ]

    office = models.ForeignKey(
        OfficeManagement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehouses",
    )

    warehouse_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
    )  # WH-003
    name = models.CharField(max_length=255, null=True, blank=True)
    capacity = models.CharField(max_length=255, null=True, blank=True)  # 5,000 sq ft
    address = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    def save(self, *args, **kwargs):
        if not self.warehouse_id:
            last = Warehouse.objects.order_by("-id").first()

            if last and last.warehouse_id:
                num = int(last.warehouse_id.split("-")[1]) + 1
            else:
                num = 1

            self.warehouse_id = f"WH-{num:03d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or str(self.pk)


# class OfficeActivity(models.Model):
#     ACTIVITY_TYPE_CHOICES = [
#         ('requisition', 'Requisition'),
#         ('grn', 'GRN'),
#         ('transfer', 'Transfer'),
#         ('payment', 'Payment'),
#     ]

#     office = models.ForeignKey(
#         OfficeManagement,
#         on_delete=models.SET_NULL, null=True, blank=True,
#         related_name='recent_activity'
#     )

#     type = models.CharField(max_length=50, choices=ACTIVITY_TYPE_CHOICES, null=True, blank=True)
#     description = models.TextField(null=True, blank=True)
#     date = models.DateField(null=True, blank=True)
#     user = models.CharField(max_length=255, null=True, blank=True)

#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.name or 'Unknown'} - {self.office.name if self.office else 'No Office'}"
