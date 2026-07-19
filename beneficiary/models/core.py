from django.db import models
from django.utils import timezone


class Beneficiary(models.Model):
    SEX_CHOICES = [
        ("Female", "Female"),
        ("Male", "Male"),
        ("Transgender", "Transgender"),
    ]
    HOUSEHOLD_TYPE_CHOICES = [
        ("Male-headed", "Male-headed"),
        ("Female-headed", "Female-headed"),
        ("Child-headed", "Child-headed"),
    ]
    EDUCATION_CHOICES = [
        ("No schooling", "No schooling"),
        ("Primary incomplete", "Primary incomplete"),
        ("Primary complete", "Primary complete"),
        ("Secondary", "Secondary"),
        ("Higher Secondary", "Higher Secondary"),
        ("Graduate & above", "Graduate & above"),
    ]
    LAND_OWNERSHIP_CHOICES = [
        ("Landless", "Landless"),
        ("Homestead only", "Homestead only"),
        ("Cultivable land", "Cultivable land"),
    ]
    HOUSING_CONDITION_CHOICES = [
        ("Muddy", "Muddy"),
        ("Semi-concrete", "Semi-concrete"),
        ("Concrete", "Concrete"),
    ]
    SANITATION_CHOICES = [
        ("Hygienic latrine", "Hygienic latrine"),
        ("Non-hygienic", "Non-hygienic"),
        ("Open defecation", "Open defecation"),
    ]

    # A. Identification & System Information
    ben_code = models.CharField(max_length=100, unique=True, null=True, blank=True)
    household_id = models.CharField(max_length=100, null=True, blank=True)
    projects = models.ManyToManyField(
        "projects.Project",
        blank=True,
        related_name="beneficiaries",
    )
    donors = models.ManyToManyField(
        "donor.Donor",
        blank=True,
        related_name="beneficiaries",
    )
    enrollment_date = models.DateField(null=True, blank=True)

    # B. Personal Information
    name = models.CharField(max_length=255, null=True, blank=True)
    mother_name = models.CharField(max_length=255, null=True, blank=True)
    father_name = models.CharField(max_length=255, null=True, blank=True)
    husband_name = models.CharField(max_length=255, null=True, blank=True)
    sex = models.CharField(max_length=20, choices=SEX_CHOICES, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    nid = models.CharField(max_length=50, unique=True, null=True, blank=True)
    contact = models.CharField(max_length=20, null=True, blank=True)

    # C. Household & Demographic Information
    household_type = models.CharField(
        max_length=30, choices=HOUSEHOLD_TYPE_CHOICES, null=True, blank=True
    )
    household_head_name = models.CharField(max_length=255, null=True, blank=True)
    relationship_with_hh_head = models.CharField(max_length=100, null=True, blank=True)
    household_size = models.IntegerField(null=True, blank=True)
    hh_members_total = models.IntegerField(null=True, blank=True)
    hh_members_male = models.IntegerField(null=True, blank=True)
    hh_members_female = models.IntegerField(null=True, blank=True)
    hh_members_transgender = models.IntegerField(null=True, blank=True)
    hh_members_children = models.IntegerField(null=True, blank=True)
    hh_members_elderly = models.IntegerField(null=True, blank=True)
    hh_members_pwd = models.IntegerField(null=True, blank=True)

    # D. Geographic & Location Details
    district = models.CharField(max_length=100, null=True, blank=True)
    upazila = models.CharField(max_length=100, null=True, blank=True)
    union = models.CharField(max_length=100, null=True, blank=True)
    village = models.CharField(max_length=100, null=True, blank=True)
    gps_latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    gps_longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    coastal_risk_zones = models.JSONField(blank=True, null=True, default=list)

    # E. Socio-Economic Status
    main_income_sources = models.JSONField(blank=True, null=True, default=list)
    secondary_occupation = models.CharField(max_length=255, null=True, blank=True)
    monthly_income = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    land_ownership_status = models.CharField(
        max_length=30, choices=LAND_OWNERSHIP_CHOICES, null=True, blank=True
    )
    housing_condition = models.CharField(
        max_length=30, choices=HOUSING_CONDITION_CHOICES, null=True, blank=True
    )

    # F. Education Profile
    education_level = models.CharField(
        max_length=50, choices=EDUCATION_CHOICES, null=True, blank=True
    )

    # G. Disability & Vulnerability Status
    person_with_disability = models.BooleanField(null=True, blank=True)
    disability_types = models.JSONField(blank=True, null=True, default=list)
    vulnerability_categories = models.JSONField(blank=True, null=True, default=list)

    # H. Health, WASH & Nutrition
    drinking_water_sources = models.JSONField(blank=True, null=True, default=list)
    drinking_water_distance_km = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    sanitation_facility = models.CharField(
        max_length=30, choices=SANITATION_CHOICES, null=True, blank=True
    )
    common_health_problems = models.JSONField(blank=True, null=True, default=list)
    common_health_problems_other = models.CharField(
        max_length=255, null=True, blank=True
    )
    access_to_health_services = models.JSONField(blank=True, null=True, default=list)

    # I. Climate Change & Disaster Exposure
    loss_and_damage = models.JSONField(blank=True, null=True, default=list)
    coping_strategies = models.JSONField(blank=True, null=True, default=list)

    # J. Program Participation & Group Membership
    group_memberships = models.JSONField(blank=True, null=True, default=list)
    group_joining_date = models.DateField(null=True, blank=True)

    # K. Agricultural Information
    agri_land_owned_decimal = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    currently_practiced_adaptive_agriculture = models.TextField(null=True, blank=True)
    total_cultivated_land_last_season = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    land_under_climate_adaptive_agriculture = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    irrigation_sources = models.JSONField(blank=True, null=True, default=list)
    total_agricultural_income_last_year = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    adaptive_agricultural_practices = models.TextField(null=True, blank=True)
    climate_resilient_crop_varieties = models.TextField(null=True, blank=True)

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.date_of_birth:
            today = timezone.now().date()
            dob = self.date_of_birth
            self.age = (
                today.year
                - dob.year
                - ((today.month, today.day) < (dob.month, dob.day))
            )
        if not self.ben_code:
            year = timezone.now().year
            last_record = (
                Beneficiary.objects.filter(ben_code__startswith=f"BEN-{year}")
                .order_by("-id")
                .first()
            )
            if last_record and last_record.ben_code:
                try:
                    last_number = int(last_record.ben_code.split("-")[-1])
                    new_number = str(last_number + 1).zfill(4)
                except (ValueError, IndexError):
                    new_number = "0001"
            else:
                new_number = "0001"
            self.ben_code = f"BEN-{year}-{new_number}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ben_code or self.pk} - {self.name or self.pk}"


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
        return self.name or str(self.pk)


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
        return f"{self.service_type or self.pk}"
