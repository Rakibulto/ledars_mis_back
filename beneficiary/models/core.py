from django.db import models
from django.utils import timezone


class Beneficiary(models.Model):
    DIVISION_CHOICES = [
        ("Dhaka", "Dhaka"),
        ("Chattogram", "Chattogram"),
        ("Khulna", "Khulna"),
        ("Rajshahi", "Rajshahi"),
        ("Barishal", "Barishal"),
        ("Sylhet", "Sylhet"),
        ("Rangpur", "Rangpur"),
        ("Mymensingh", "Mymensingh"),
    ]
    SEX_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
        ("Other", "Other"),
    ]
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Inactive", "Inactive"),
        ("Graduated", "Graduated"),
    ]
    MARITAL_STATUS_CHOICES = [
        ("Single", "Single"),
        ("Married", "Married"),
        ("Widowed", "Widowed"),
        ("Divorced", "Divorced"),
    ]
    ben_code = models.CharField(max_length=100, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    father_name = models.CharField(max_length=255, null=True, blank=True)
    mother_name = models.CharField(max_length=255, null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES, null=True, blank=True)
    nid = models.CharField(max_length=50, unique=True, null=True, blank=True)
    contact = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(null=True, blank=True)

    division = models.CharField(
        max_length=50, choices=DIVISION_CHOICES, null=True, blank=True
    )

    district = models.CharField(max_length=100, null=True, blank=True)
    upazila = models.CharField(max_length=100, null=True, blank=True)
    union = models.CharField(max_length=100, null=True, blank=True)
    village = models.CharField(max_length=100, null=True, blank=True)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    vulnerability_type = models.JSONField(blank=True, null=True)
    household_size = models.IntegerField(null=True, blank=True)
    monthly_income = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    education_level = models.CharField(max_length=100, null=True, blank=True)
    occupation = models.CharField(max_length=100, null=True, blank=True)
    marital_status = models.CharField(
        max_length=20, choices=MARITAL_STATUS_CHOICES, null=True, blank=True
    )
    registration_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Active", null=True, blank=True
    )

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):

        if not self.ben_code:
            year = timezone.now().year

            last_record = (
                Beneficiary.objects.filter(ben_code__startswith=f"BEN-{year}")
                .order_by("-id")
                .first()
            )

            if last_record:
                last_number = int(last_record.ben_code.split("-")[-1])
                new_number = str(last_number + 1).zfill(4)
            else:
                new_number = "0001"

            self.ben_code = f"BEN-{year}-{new_number}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ben_code or self.pk} - {self.name or self.pk} - {self.id}"


class ServiceRH(models.Model):

    STATUS_CHOICES = [
        ("Completed", "Completed"),
        ("Ongoing", "Ongoing"),
        ("Planned", "Planned"),
    ]
    beneficiary = models.ForeignKey(
        Beneficiary,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services_received",
    )

    name = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField(auto_now_add=True)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True
    )
    description = models.TextField(null=True, blank=True)
    value = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    staff = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, null=True, blank=True
    )

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name or self.pk}"


class ServiceCategory(models.Model):
    name = models.CharField(max_length=200, unique=True, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.name or self.pk


class VulnerabilityType(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(null=True, blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ServiceDelivery(models.Model):
    STATUS_CHOICES = [
        ("Planned", "Planned"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    ]
    beneficiary = models.ForeignKey(
        "beneficiary.Beneficiary",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services",
    )
    service_type = models.CharField(max_length=255, null=True, blank=True)
    category = models.ForeignKey(
        "beneficiary.ServiceCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services_delivery",
    )
    location = models.CharField(max_length=255, null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Planned")
    provider = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.IntegerField(null=True, blank=True)
    unit = models.CharField(max_length=50, null=True, blank=True)

    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.service_type or self.pk} - {self.beneficiary or self.pk}"
