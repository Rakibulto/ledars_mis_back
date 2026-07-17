from django.db import models
from authentication.models import User
from .product import Product
from .warehouse import Warehouse


class DonorFundedInventory(models.Model):
    project_name = models.CharField(max_length=200)
    donor = models.CharField(max_length=200)
    grant_reference = models.CharField(max_length=100, unique=True)
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    allocated_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    consumed_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default="active")

    def save(self, *args, **kwargs):
        self.remaining_qty = self.allocated_qty - self.consumed_qty
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.project_name} - {self.donor}"


class FieldDistribution(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    location = models.CharField(max_length=200)
    gps_coordinates = models.CharField(max_length=100, null=True, blank=True)
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    beneficiary_count = models.PositiveIntegerField(default=0)
    verification_method = models.CharField(max_length=100, null=True, blank=True)
    distributed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=20, default="completed")
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference


# ── Loss & Damage Claims ──
class LossDamageClaim(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    type = models.CharField(max_length=100)
    shipment_ref = models.CharField(max_length=100, null=True, blank=True)
    total_claim = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    insurance_ref = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=50, default="Under Review")
    filed_by = models.CharField(max_length=200, null=True, blank=True)
    carrier = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference


class LossDamageClaimItem(models.Model):
    claim = models.ForeignKey(
        LossDamageClaim, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(null=True, blank=True)


# ── Emergency Reserves ──
class EmergencyReserve(models.Model):
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="emergency_reserves"
    )
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    authorization_level = models.CharField(max_length=100)
    last_review = models.DateField(null=True, blank=True)
    next_review = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reserve - {self.warehouse}"


class EmergencyReserveItem(models.Model):
    reserve = models.ForeignKey(
        EmergencyReserve, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    reserved = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    min_reserve = models.DecimalField(max_digits=12, decimal_places=2, default=0)


# ── Commodity Tracking ──
class CommodityTracking(models.Model):
    commodity = models.CharField(max_length=200)
    donor = models.CharField(max_length=200)
    grant = models.CharField(max_length=100)
    received_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    distributed_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    in_transit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    in_warehouse = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    losses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loss_rate = models.CharField(max_length=20, default="0%")
    last_distribution = models.DateField(null=True, blank=True)
    compliance_status = models.CharField(max_length=50, default="Compliant")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.commodity} - {self.donor}"


# ── Pipeline Tracking ──
class PipelineTracking(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    shipment = models.CharField(max_length=200)
    origin = models.CharField(max_length=200)
    destination = models.CharField(max_length=200)
    current_leg = models.CharField(max_length=300, null=True, blank=True)
    legs = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=50, default="In Transit")
    eta = models.DateField(null=True, blank=True)
    departure_date = models.DateField(null=True, blank=True)
    items_desc = models.TextField(null=True, blank=True)
    insurance = models.CharField(max_length=100, null=True, blank=True)
    carrier = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference


# ── Customs & Import Tracking ──
class CustomsImportTracking(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    shipment = models.CharField(max_length=200)
    port = models.CharField(max_length=200)
    customs_status = models.CharField(max_length=50, default="In Progress")
    documents = models.JSONField(default=list, blank=True)
    duty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    exemption = models.CharField(max_length=200, null=True, blank=True)
    clearing_agent = models.CharField(max_length=200, null=True, blank=True)
    clearance_date = models.DateField(null=True, blank=True)
    days_in_customs = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference


# ── Humanitarian Kitting ──
class HumanitarianKit(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    bom = models.ForeignKey(
        "inventory.KittingBOM", on_delete=models.SET_NULL, null=True, blank=True
    )
    target_group = models.CharField(max_length=200, null=True, blank=True)
    approx_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_on_hand = models.PositiveIntegerField(default=0)
    pre_positioned = models.PositiveIntegerField(default=0)
    last_assembled = models.DateField(null=True, blank=True)
    shelf_life_days = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ── Disposal Management ──
class DisposalRecord(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lot = models.CharField(max_length=100, null=True, blank=True)
    reason = models.CharField(max_length=200)
    method = models.CharField(max_length=200)
    authorized_by = models.CharField(max_length=200, null=True, blank=True)
    witness = models.CharField(max_length=300, null=True, blank=True)
    certificate = models.CharField(max_length=100, null=True, blank=True)
    value_disposed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference


# ── Vehicle Dispatch ──
class VehicleDispatch(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    vehicle = models.CharField(max_length=200)
    driver = models.CharField(max_length=200)
    route = models.CharField(max_length=300)
    distance_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    departure = models.DateTimeField(null=True, blank=True)
    arrival = models.DateTimeField(null=True, blank=True)
    fuel_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=50, default="Scheduled")
    waybill = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference


class VehicleDispatchCargo(models.Model):
    dispatch = models.ForeignKey(
        VehicleDispatch, on_delete=models.CASCADE, related_name="cargo"
    )
    description = models.CharField(max_length=300)
    weight = models.CharField(max_length=50, null=True, blank=True)


# ── Beneficiary Distribution List ──
class BeneficiaryDistributionList(models.Model):
    name = models.CharField(max_length=200)
    project = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    total_beneficiaries = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=50, default="Active")
    created_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class BeneficiaryDistributionItem(models.Model):
    distribution_list = models.ForeignKey(
        BeneficiaryDistributionList,
        on_delete=models.CASCADE,
        related_name="items_per_beneficiary",
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(max_length=50, null=True, blank=True)


# ── Waybill Management ──
class Waybill(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    origin = models.CharField(max_length=200)
    destination = models.CharField(max_length=200)
    vehicle = models.CharField(max_length=200, null=True, blank=True)
    driver = models.CharField(max_length=200, null=True, blank=True)
    total_weight = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=50, default="Draft")
    departure_time = models.DateTimeField(null=True, blank=True)
    arrival_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference


class WaybillItem(models.Model):
    waybill = models.ForeignKey(
        Waybill, on_delete=models.CASCADE, related_name="items"
    )
    description = models.CharField(max_length=300)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    weight = models.CharField(max_length=50, null=True, blank=True)


# ── Field Warehouse ──
class FieldWarehouse(models.Model):
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=100)
    location = models.CharField(max_length=300)
    gps = models.CharField(max_length=100, null=True, blank=True)
    capacity_sqft = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    manager = models.CharField(max_length=200, null=True, blank=True)
    items_count = models.PositiveIntegerField(default=0)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    setup_date = models.DateField(null=True, blank=True)
    condition = models.CharField(max_length=50, default="Good")
    security = models.CharField(max_length=100, null=True, blank=True)
    climate_control = models.CharField(max_length=100, default="None")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
