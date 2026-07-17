from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.contrib.auth.models import Permission


# Dynamic Company Name Name and Logo
class CompanyInfo(models.Model):
    company_name = models.CharField(max_length=255, blank=True, null=True)
    logo = models.ImageField(upload_to="company_logo/", blank=True, null=True)
    favicon = models.ImageField(upload_to="company_favicon/", blank=True, null=True)

    def __str__(self):
        return self.company_name


# Custom User Model with Role-Based Permissions
STATUS_CHOICES = [
    ("active", "Active"),
    ("resign", "Resign"),
    ("terminate", "Terminate"),
]


class CustomUserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.is_active = extra_fields.get("is_active", True)
        user.save(using=self._db)
        # if the assigned role is Admin, make sure permissions are populated
        if user.role and user.role.name == "Admin":
            user.user_permissions.set(Permission.objects.all())
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        admin_role, _ = Role.objects.get_or_create(name="Admin")
        extra_fields.setdefault("role", admin_role)

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")
        if not extra_fields.get("is_active"):
            raise ValueError("Superuser must have is_active=True.")

        # create the user first
        user = self.create_user(email, username, password, **extra_fields)
        # ensure superusers have every permission
        perms = Permission.objects.all()
        user.user_permissions.set(perms)
        return user


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.name


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User Model extending Django's default.
    Username is the official email address. Includes roles for permissions.
    """

    username = models.CharField(
        max_length=150,
        unique=True,
        help_text="Username for the user, typically the official email address.",
    )
    email = models.EmailField(
        unique=True,
        help_text="Official Ledar's email address, used as username.",
        null=True,
        blank=True,
    )
    role = models.ForeignKey(
        Role, on_delete=models.SET_NULL, related_name="user_role", blank=True, null=True
    )
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        related_name="users",
        blank=True,
        null=True,
    )
    is_staff = models.BooleanField(
        default=False, help_text="Can access the admin site."
    )
    is_active = models.BooleanField(default=False, help_text="Is the account active?")
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
    objects = CustomUserManager()

    def save(self, *args, bulk_import=False, **kwargs):
        # Set default role to Employee if no role is assigned
        if not self.role:
            employee_role, _ = Role.objects.get_or_create(name="Employee")
            self.role = employee_role

        if (
            not bulk_import
            and self.password
            and not self.password.startswith(("pbkdf2_sha256$", "bcrypt$", "argon2$"))
        ):
            self.set_password(self.password)
        super().save(*args, **kwargs)

        if self.is_superuser:
            self.user_permissions.set(Permission.objects.all())

    def get_full_name(self):
        return self.username or self.email or ""

    def __str__(self):
        return self.email if self.email else self.username


class user_role_based_permissions(models.Model):
    """
    Model to store user role based permissions.
    """

    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name="role_permissions"
    )
    permission = models.ManyToManyField(Permission, related_name="role_permissions")

    def __str__(self):
        return f"{self.role.name} - {self.permission}"


class PreApprovedIP(models.Model):
    """Stores pre-approved IP addresses for web login."""

    ip_address = models.GenericIPAddressField(unique=True)
    description = models.CharField(
        max_length=255, help_text="e.g., Main Office, VPN", blank=True, null=True
    )

    def __str__(self):
        return self.ip_address


class Module(models.Model):
    """Defines frontend modules that can be assigned permissions."""

    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ModulePermission(models.Model):
    """Stores module-level CRUD/Add/View permissions for each user."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="module_permissions",
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="module_permissions",
    )
    can_create = models.BooleanField(default=False)
    can_update = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_add = models.BooleanField(default=False)
    can_view = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        unique_together = ("user", "module")
        ordering = ["module__name"]

    def __str__(self):
        return f"{self.user.email or self.user.username} - {self.module.name}"


class PermissionGroup(models.Model):
    """Reusable permission templates that can span multiple modules."""

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, default="")
    permissions = models.ManyToManyField(
        Permission, related_name="permission_groups", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AllowedAnyIPLogins(models.Model):
    """IPs logged in through Allow any Ip"""

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
