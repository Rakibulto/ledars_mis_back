from django.contrib import admin
from .models import (
    CompanyInfo,
    User,
    Role,
    PreApprovedIP,
    AllowedAnyIPLogins,
    user_role_based_permissions,
    Module,
    ModulePermission,
)
from django.contrib import admin
from .models import User, Role, PreApprovedIP, AllowedAnyIPLogins
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin
from django.contrib.auth.models import Permission
from employee.models import Employee
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import (
    ExportForm,
    ImportForm,
    SelectableFieldsExportForm,
)

# Importing the signal to ensure it is registered
from .signals import post_import_completed


# Dynamic Company Name Name and Logo Admin
@admin.register(CompanyInfo)
class CompanyInfoAdmin(ModelAdmin):
    list_display = ("company_name", "logo", "favicon")
    search_fields = ("company_name",)


# Custom User Resource for Import/Export with Optimized Permission Handling
class UserResource(resources.ModelResource):
    username = fields.Field(column_name="username", attribute="username")
    email = fields.Field(column_name="email", attribute="email")
    role = fields.Field(
        column_name="role",
        attribute="role",
        widget=widgets.ForeignKeyWidget(Role, "name"),
    )
    is_active = fields.Field(
        column_name="is_active",
        attribute="is_active",
        default=True,
        widget=widgets.BooleanWidget(),
    )
    password = fields.Field(column_name="password", attribute="password")

    class Meta:
        model = User
        # 'password' is NOT listed here. We handle it manually after creation.
        fields = ("username", "email", "role", "is_active", "password")
        export_order = ("id", "username", "email", "role", "is_active", "password")
        import_id_fields = ("email",)
        skip_unchanged = True
        report_skipped = True
        use_bulk = True
        # skip_diff = True
        batch_size = 1000

    def before_import(self, dataset, dry_run=False, **kwargs):
        """
        Caches data to avoid N+1 queries. No password logic here.
        """
        self.roles_cache = {role.name: role for role in Role.objects.all()}
        self.permissions_cache = {p.codename: p for p in Permission.objects.all()}
        self.role_permissions_map = {
            rp.role_id: list(rp.permission.values_list("id", flat=True))
            for rp in user_role_based_permissions.objects.prefetch_related("permission")
        }

    def after_import(
        self, dataset, result, using_transactions, dry_run=False, **kwargs
    ):
        """
        This method is now extremely fast. It performs quick bulk operations
        and then sends a signal to trigger the slow background work.
        """
        if dry_run:
            return

        # --- Collect all necessary data in a single, fast loop ---
        newly_created_users = []
        user_pks_and_passwords = []

        for i, row in enumerate(dataset.dict):
            row_result = result.rows[i]

            # Collect data for the background password hashing task
            if row_result.import_type in (
                row_result.IMPORT_TYPE_NEW,
                row_result.IMPORT_TYPE_UPDATE,
            ):
                password = row.get("password")
                if password:
                    # Store the user's primary key and their plain-text password
                    user_pks_and_passwords.append((row_result.instance.pk, password))

            # Collect newly created users for Employee creation
            if row_result.import_type == row_result.IMPORT_TYPE_NEW:
                newly_created_users.append(row_result.instance)

        # --- Perform Quick Bulk Operations ---
        if newly_created_users:
            Employee.objects.bulk_create(
                [
                    Employee(
                        user=user,
                        employee_name=user.username,
                        personal_email_id=user.email,
                    )
                    for user in newly_created_users
                ]
            )

        # --- Handle Permissions ---
        for row_result in result.rows:
            if row_result.import_type in (
                row_result.IMPORT_TYPE_NEW,
                row_result.IMPORT_TYPE_UPDATE,
            ):
                user_instance = row_result.instance
                if user_instance and user_instance.role:
                    role_id = user_instance.role.id
                    if role_id in self.role_permissions_map:
                        user_instance.user_permissions.set(
                            self.role_permissions_map[role_id]
                        )
                    else:
                        permissions_to_assign = self._get_permissions_for_role(
                            user_instance.role.name
                        )
                        if permissions_to_assign:
                            new_role_permission = (
                                user_role_based_permissions.objects.create(
                                    role=user_instance.role
                                )
                            )
                            new_role_permission.permission.set(permissions_to_assign)
                            permission_ids = [p.id for p in permissions_to_assign]
                            user_instance.user_permissions.set(permission_ids)
                            self.role_permissions_map[role_id] = permission_ids

        # --- Send Signal to Trigger Background Hashing ---
        # This is the final step. It returns immediately without blocking.
        # print(user_pks_and_passwords)
        if user_pks_and_passwords:
            post_import_completed.send(
                sender=self.__class__, user_pks_and_passwords=user_pks_and_passwords
            )

    def _get_permissions_for_role(self, role_name):
        permissions_code_names = []
        if role_name == "Supervisor":
            permissions_code_names = [
                "view_leaveapproval",
                "change_leaveapproval",
                "view_leaverequest",
                "add_leaverequest",
                "view_own_attendance",
                "view_subordinate_attendance",
                "add_attendancedata",
                "add_attendanceadjustmentrequest",
                "view_attendanceadjustmentrequest",
                "view_attendanceadjustmentapproval",
                "change_attendanceadjustmentapproval",
                "change_leaverequest",
                "change_attendanceadjustmentrequest",
            ]
        elif role_name == "Employee":
            permissions_code_names = [
                "view_leaverequest",
                "change_leaverequest",
                "add_leaverequest",
                "view_own_attendance",
                "add_attendancedata",
                "view_attendanceadjustmentrequest",
                "add_attendanceadjustmentrequest",
                "change_attendanceadjustmentrequest",
            ]
        elif role_name == "Admin":
            return list(self.permissions_cache.values())

        return [
            self.permissions_cache[codename]
            for codename in self.permissions_cache
            if codename in permissions_code_names
        ]


class RoleResource(resources.ModelResource):
    """
    Resource class for importing/exporting Role model data.
    Handles TimeField widgets and ensures consistent formatting.
    Excludes created_at and updated_at to allow Django's auto_now_add/auto_now.
    """

    name = fields.Field(column_name="name", attribute="name")

    class Meta:
        model = Role
        fields = "name"
        export_order = fields
        import_id_fields = ("name",)
        skip_unchanged = True
        report_skipped = True


class PreApprovedIPResource(resources.ModelResource):
    """
    Resource class for importing/exporting PreApprovedIP model data.
    Handles IP address fields and ensures consistent formatting.
    """

    ip_address = fields.Field(column_name="ip_address", attribute="ip_address")
    description = fields.Field(column_name="description", attribute="description")

    class Meta:
        model = PreApprovedIP
        fields = ("ip_address", "description")
        export_order = fields
        import_id_fields = ("ip_address",)
        skip_unchanged = True
        report_skipped = True


@admin.register(User)
class UserAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing users.
    """

    list_display = ("id", "username", "email", "role")
    search_fields = ("username", "email")
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = UserResource
    filter_horizontal = ("user_permissions",)


@admin.register(user_role_based_permissions)
class UserRoleBasedPermissionsAdmin(ModelAdmin):
    """
    Admin interface for managing user role based permissions.
    """

    list_display = ("role", "role_based_permissions")
    search_fields = ("role__name",)
    filter_horizontal = ("permission",)

    def role_based_permissions(self, obj):
        return ", ".join([p.name for p in obj.permission.all()])

    role_based_permissions.short_description = "Permissions"


@admin.register(Module)
class ModuleAdmin(ModelAdmin):
    """Admin interface for listing available frontend modules."""

    list_display = ("id", "name", "code", "created_at", "updated_at")
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(ModulePermission)
class ModulePermissionAdmin(ModelAdmin):
    """Admin interface for user module permissions."""

    list_display = (
        "id",
        "user",
        "module",
        "can_create",
        "can_update",
        "can_delete",
        "can_add",
        "can_view",
        "created_at",
        "updated_at",
    )
    search_fields = ("user__email", "user__username", "module__name")
    list_filter = (
        "can_create",
        "can_update",
        "can_delete",
        "can_add",
        "can_view",
    )


@admin.register(Role)
class RoleAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing roles.
    """

    list_display = ("id", "name", "created_at", "updated_at")
    search_fields = ("name",)
    ordering = ("name",)
    import_form_class = ImportForm
    export_form_class = ExportForm
    resource_class = RoleResource


@admin.register(PreApprovedIP)
class PreApprovedIPAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing pre-approved IP addresses.
    """

    list_display = ("ip_address", "description")
    search_fields = ("ip_address", "description")
    import_form_class = ImportForm
    export_form_class = ExportForm
    resource_class = PreApprovedIPResource


@admin.register(AllowedAnyIPLogins)
class AllowedAnyIPLoginsPAdmin(ModelAdmin):
    """
    Admin interface for track login IP addresses.
    """

    list_display = ("ip_address", "created_at")
    search_fields = ("ip_address", "created_at")
    import_form_class = ImportForm
    export_form_class = ExportForm
