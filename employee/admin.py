from django.contrib import admin
from .models import (
    Branch,
    Department,
    Designation,
    EmergencyContact,
    Employee,
    Grade,
    Nominee,
    ProbationCheckLog,
    Salary,
)
from leave.models import LeaveGroup
from import_export import resources, fields, widgets
from import_export.widgets import ForeignKeyWidget
from authentication.models import User
from shift.models import Shift
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import (
    ImportForm,
    SelectableFieldsExportForm,
)
from leave.models import SupervisorLevel
import logging
from decimal import Decimal

# Set up logging for debugging
logger = logging.getLogger(__name__)


class DesignationWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value and row:
            department_name = row.get("department")
            if not department_name:
                raise ValueError("Department is required to resolve Designation")
            try:
                department = Department.objects.get(name=department_name)
                return Designation.objects.get(name=value, department=department)
            except Department.DoesNotExist:
                raise ValueError(f"Department '{department_name}' not found.")
            except Designation.MultipleObjectsReturned:
                raise ValueError(
                    f"Multiple Designations found for name '{value}' and department '{department_name}'"
                )
            except Designation.DoesNotExist:
                raise ValueError(
                    f"Designation '{value}' not found for department '{department_name}'"
                )
        return None


class GrossSalaryWidget(widgets.Widget):
    def clean(self, value, row=None, *args, **kwargs):
        def to_decimal(v):
            try:
                if v is None or v == "":
                    return Decimal("0")
                return Decimal(str(v).replace(",", "").strip())
            except Exception:
                return Decimal("0")

        if not row:
            return to_decimal(value)

        basic = to_decimal(row.get("basic"))
        house = to_decimal(row.get("house_rent"))
        convey = to_decimal(row.get("conveyance"))
        medical = to_decimal(row.get("medical"))
        return basic + house + convey + medical


class EmployeeResource(resources.ModelResource):
    """
    Resource class for importing/exporting Employee model data.
    Ensures consistency between export and import formats.
    """

    employee_id = fields.Field(column_name="employee_id", attribute="employee_id")
    employee_name = fields.Field(column_name="employee_name", attribute="employee_name")
    user = fields.Field(
        column_name="user",
        attribute="user",
        widget=widgets.ForeignKeyWidget(User, field="username"),
    )
    department = fields.Field(
        column_name="department",
        attribute="department",
        widget=widgets.ForeignKeyWidget(Department, field="name"),
    )
    designation = fields.Field(
        column_name="designation",
        attribute="designation",
        widget=DesignationWidget(Designation, "name"),
    )
    location = fields.Field(
        column_name="location",
        attribute="location",
        widget=widgets.ForeignKeyWidget(Branch, field="name"),
    )
    joining_date = fields.Field(
        column_name="joining_date",
        attribute="joining_date",
        widget=widgets.DateWidget(format="%m/%d/%Y"),
    )
    probation_period = fields.Field(
        column_name="probation_period",
        attribute="probation_period",
        widget=widgets.BooleanWidget(),
    )
    probation_period_time = fields.Field(
        column_name="probation_period_time", attribute="probation_period_time"
    )
    confirmation_date = fields.Field(
        column_name="confirmation_date",
        attribute="confirmation_date",
        widget=widgets.DateWidget(format="%m/%d/%Y"),
    )
    supervisor = fields.Field(
        column_name="supervisor",
        attribute="supervisor",
        widget=widgets.ManyToManyWidget(User, field="username", separator=","),
    )
    office_days = fields.Field(column_name="office_days", attribute="office_days")
    office_time = fields.Field(
        column_name="office_time",
        attribute="office_time",
        widget=widgets.ForeignKeyWidget(Shift, field="name"),
    )
    official_mobile_number = fields.Field(
        column_name="official_mobile_number", attribute="official_mobile_number"
    )
    employment_type = fields.Field(
        column_name="employment_type",
        attribute="employment_type",
        widget=widgets.ForeignKeyWidget(LeaveGroup, field="name"),
    )

    salary = fields.Field(column_name="salary", attribute="salary", default=0)
    rfid_or_machine_code = fields.Field(
        column_name="rfid_or_machine_code", attribute="rfid_or_machine_code"
    )
    status = fields.Field(column_name="status", attribute="status")
    resign_terminated_date = fields.Field(
        column_name="resign_terminated_date",
        attribute="resign_terminated_date",
        widget=widgets.DateWidget(format="%m/%d/%Y"),
    )
    resign_terminated_reason = fields.Field(
        column_name="resign_terminated_reason", attribute="resign_terminated_reason"
    )
    present_address = fields.Field(
        column_name="present_address", attribute="present_address"
    )
    permanent_address = fields.Field(
        column_name="permanent_address", attribute="permanent_address"
    )
    marital_status = fields.Field(
        column_name="marital_status", attribute="marital_status"
    )
    religion = fields.Field(column_name="religion", attribute="religion")
    blood_group = fields.Field(column_name="blood_group", attribute="blood_group")
    gender = fields.Field(column_name="gender", attribute="gender")
    personal_mobile_number = fields.Field(
        column_name="personal_mobile_number", attribute="personal_mobile_number"
    )
    personal_email_id = fields.Field(
        column_name="personal_email_id", attribute="personal_email_id"
    )
    last_education = fields.Field(
        column_name="last_education", attribute="last_education"
    )
    educational_institute = fields.Field(
        column_name="educational_institute", attribute="educational_institute"
    )
    last_job_experience = fields.Field(
        column_name="last_job_experience",
        attribute="last_job_experience",
        default="N/A",
    )
    emergency_contact = fields.Field(
        column_name="emergency_contact",
        attribute="emergency_contact",
        widget=widgets.ManyToManyWidget(EmergencyContact, field="name", separator=","),
    )
    nominee = fields.Field(
        column_name="nominee",
        attribute="nominee",
        widget=widgets.ManyToManyWidget(Nominee, field="name", separator=","),
    )
    profile_picture = fields.Field(
        column_name="profile_picture", attribute="profile_picture"
    )
    date_of_birth = fields.Field(
        column_name="date_of_birth",
        attribute="date_of_birth",
        widget=widgets.DateWidget(format="%m/%d/%Y"),
    )
    bank_name = fields.Field(column_name="bank_name", attribute="bank_name")
    bank_account_number = fields.Field(
        column_name="bank_account_number", attribute="bank_account_number"
    )
    bank_branch = fields.Field(column_name="bank_branch", attribute="bank_branch")
    allow_web_login = fields.Field(
        column_name="allow_web_login",
        attribute="allow_web_login",
        widget=widgets.BooleanWidget(),
    )
    is_ip_restricted = fields.Field(
        column_name="is_ip_restricted",
        attribute="is_ip_restricted",
        widget=widgets.BooleanWidget(),
    )
    allow_any_ip_attendance = fields.Field(
        column_name="allow_any_ip_attendance",
        attribute="allow_any_ip_attendance",
        widget=widgets.BooleanWidget(),
    )

    def get_instance(self, instance_loader, row):
        """
        Override to skip lookup if employee_id is blank, and handle multiples by creating new.
        """
        import_id_fields = [self.fields[f] for f in self.get_import_id_fields()]
        lookups = {}
        for field in import_id_fields:
            field_value = field.get_value(row)
            if field_value:  # Ignore if empty or None
                lookups[field.attribute] = field_value
        if not lookups:
            return None  # Create new
        try:
            return instance_loader.get_instance(lookups)
        except (Employee.DoesNotExist, Employee.MultipleObjectsReturned) as e:
            logger.warning(f"Instance lookup failed for row {row}: {e}. Creating new.")
            return None  # Create new on error

    def before_import_row(self, row, **kwargs):
        """
        Generate employee_id if not provided and ensure related objects exist.
        """
        # Ensure department exists
        if row.get("department"):
            department, _ = Department.objects.get_or_create(name=row["department"])

        # Ensure designation exists (requires department)
        if row.get("designation") and row.get("department"):
            department, _ = Department.objects.get_or_create(name=row["department"])
            Designation.objects.get_or_create(
                name=row["designation"], department=department
            )

        # Ensure branch exists
        if row.get("location"):
            Branch.objects.get_or_create(name=row["location"])

        # Ensure employment_type exists
        if row.get("employment_type"):
            LeaveGroup.objects.get_or_create(name=row["employment_type"])

    def before_save_instance(self, instance, row, **kwargs):
        """
        Ensure user exists before saving employee.
        Updated to match django-import-export's expected signature.
        """
        # Get dry_run from kwargs if it exists
        dry_run = kwargs.get("dry_run", False)

        if not dry_run and instance.user_id is None:
            username = row.get("user")
            if username:
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": row.get("personal_email_id")
                        or f"{username}@example.com",
                        "is_active": True,
                    },
                )
                instance.user = user

    def import_obj(self, obj, data, dry_run, **kwargs):
        """
        Custom import handling to prevent duplicate employee_id errors.
        """
        employee_id = data.get("employee_id")
        if employee_id:
            # Check if employee with this ID already exists
            existing = Employee.objects.filter(employee_id=employee_id).first()
            if existing:
                # Update existing record instead of creating new one
                obj.pk = existing.pk
                obj.employee_id = existing.employee_id

        super().import_obj(obj, data, dry_run, **kwargs)

    def dehydrate_employee_id(self, employee):
        """
        Ensure employee_id is not None during export.
        """
        if not employee.employee_id:
            logger.warning(f"Employee {employee.employee_name} has no employee_id")
            return ""
        return employee.employee_id

    def dehydrate_supervisor(self, employee):
        """
        Custom export logic for supervisor to handle None usernames.
        """
        usernames = [
            user.username for user in employee.supervisor.all() if user.username
        ]
        if not usernames:
            logger.warning(
                f"No valid usernames found for supervisors of employee {employee.employee_name}"
            )
        return ",".join(usernames)

    def dehydrate_emergency_contact(self, employee):
        """
        Custom export logic for emergency_contact to handle None names.
        """
        names = [
            contact.name for contact in employee.emergency_contact.all() if contact.name
        ]
        if not names:
            logger.warning(
                f"No valid names found for emergency contacts of employee {employee.employee_name}"
            )
        return ",".join(names)

    def dehydrate_nominee(self, employee):
        """
        Custom export logic for nominee to handle None names.
        """
        names = [nominee.name for nominee in employee.nominee.all() if nominee.name]
        if not names:
            logger.warning(
                f"No valid names found for nominees of employee {employee.employee_name}"
            )
        return ",".join(names)

    def dehydrate_profile_picture(self, employee):
        """
        Export profile_picture as file path.
        """
        return str(employee.profile_picture) if employee.profile_picture else ""

    def import_row(self, row, instance_loader, **kwargs):
        """
        Override import_row to handle supervisor assignment with correct level ordering.
        """
        # Import the row normally first
        row_result = super().import_row(row, instance_loader, **kwargs)

        # Get dry_run from kwargs
        dry_run = kwargs.get("dry_run", False)

        if dry_run:
            return row_result

        # Get the imported/updated instance
        instance = row_result.instance
        if not instance:
            return row_result

        # Handle supervisor assignment with correct levels
        supervisor_value = row.get("supervisor")
        if supervisor_value:
            # Split the comma-separated supervisors and clean them
            supervisor_names = [
                name.strip() for name in supervisor_value.split(",") if name.strip()
            ]

        # Handle supervisor assignment with correct levels
        supervisor_value = row.get("supervisor")
        if supervisor_value:
            # Split the comma-separated supervisors and clean them
            supervisor_names = [
                name.strip() for name in supervisor_value.split(",") if name.strip()
            ]

            # Temporarily disconnect the signal to prevent conflicts
            from django.db.models.signals import m2m_changed
            from employee.signals import handle_employee_supervisor_levels

            m2m_changed.disconnect(
                handle_employee_supervisor_levels, sender=Employee.supervisor.through
            )

            try:
                # Get current supervisors
                current_supervisors = set(instance.supervisor.all())

                # Get new supervisors from Excel
                new_supervisors = set()
                for supervisor_name in supervisor_names:
                    try:
                        supervisor = User.objects.get(username=supervisor_name)
                        new_supervisors.add(supervisor)
                    except User.DoesNotExist:
                        print(
                            f"Warning: Supervisor '{supervisor_name}' not found for employee {instance.employee_name}"
                        )

                # Remove supervisors that are no longer in the list
                supervisors_to_remove = current_supervisors - new_supervisors
                for supervisor in supervisors_to_remove:
                    instance.supervisor.remove(supervisor)
                    # Also remove the SupervisorLevel entry
                    SupervisorLevel.objects.filter(
                        employee=instance, supervisor=supervisor
                    ).delete()

                # Add new supervisors
                supervisors_to_add = new_supervisors - current_supervisors
                for supervisor in supervisors_to_add:
                    instance.supervisor.add(supervisor)

                # Update/create SupervisorLevel entries with correct levels
                for level, supervisor_name in enumerate(supervisor_names, start=1):
                    try:
                        supervisor = User.objects.get(username=supervisor_name)
                        # Use get_or_create to update existing or create new
                        supervisor_level, created = (
                            SupervisorLevel.objects.get_or_create(
                                employee=instance,
                                supervisor=supervisor,
                                defaults={"level": level},
                            )
                        )
                        if not created and supervisor_level.level != level:
                            # Update level if it changed
                            supervisor_level.level = level
                            supervisor_level.save()
                    except User.DoesNotExist:
                        # Already warned above
                        pass
            finally:
                # Reconnect the signal
                m2m_changed.connect(
                    handle_employee_supervisor_levels,
                    sender=Employee.supervisor.through,
                )

        return row_result

    class Meta:
        model = Employee
        fields = (
            "employee_id",
            "employee_name",
            "user",
            "department",
            "designation",
            "location",
            "joining_date",
            "probation_period",
            "probation_period_time",
            "confirmation_date",
            "supervisor",
            "office_days",
            "office_time",
            "official_mobile_number",
            "employment_type",
            "salary",
            "rfid_or_machine_code",
            "status",
            "resign_terminated_date",
            "resign_terminated_reason",
            "present_address",
            "permanent_address",
            "marital_status",
            "religion",
            "blood_group",
            "gender",
            "personal_mobile_number",
            "personal_email_id",
            "last_education",
            "educational_institute",
            "last_job_experience",
            "emergency_contact",
            "nominee",
            "profile_picture",
            "date_of_birth",
            "bank_name",
            "bank_account_number",
            "bank_branch",
            "allow_web_login",
            "is_ip_restricted",
            "allow_any_ip_attendance",
        )
        export_order = fields
        import_id_fields = ("employee_id",)
        skip_unchanged = True
        report_skipped = True


class DepartmentResource(resources.ModelResource):
    """
    Resource class for importing/exporting Department model data.
    """

    name = fields.Field(column_name="name", attribute="name")

    class Meta:
        model = Department
        fields = ("name",)
        export_order = fields
        import_id_fields = ("name",)
        skip_unchanged = True
        report_skipped = True


# Designation Resource
class DesignationResource(resources.ModelResource):
    """
    Resource class for importing/exporting Designation model data.
    Handles ForeignKey to Department via department name.
    """

    name = fields.Field(column_name="name", attribute="name")
    department = fields.Field(
        column_name="department",
        attribute="department",
        widget=widgets.ForeignKeyWidget(Department, field="name"),
    )

    class Meta:
        model = Designation
        fields = ("name", "department")
        export_order = fields
        import_id_fields = ("name", "department")
        skip_unchanged = True
        report_skipped = True


# Branch Resource
class BranchResource(resources.ModelResource):
    """
    Resource class for importing/exporting Branch model data.
    """

    name = fields.Field(column_name="name", attribute="name")
    address = fields.Field(column_name="address", attribute="address")

    class Meta:
        model = Branch
        fields = ("name", "address")
        export_order = fields
        import_id_fields = ("name",)
        skip_unchanged = True
        report_skipped = True


# EmergencyContact Resource


class EmergencyContactResource(resources.ModelResource):
    """
    Resource class for importing/exporting EmergencyContact model data.
    """

    name = fields.Field(column_name="name", attribute="name")
    relationship = fields.Field(column_name="relationship", attribute="relationship")
    phone = fields.Field(column_name="phone", attribute="phone")
    address = fields.Field(column_name="address", attribute="address")

    class Meta:
        model = EmergencyContact
        fields = ("name", "relationship", "phone", "address")
        export_order = fields
        import_id_fields = ("name", "phone")
        skip_unchanged = True
        report_skipped = True


# Nominee Resource


class NomineeResource(resources.ModelResource):
    """
    Resource class for importing/exporting Nominee model data.
    """

    name = fields.Field(column_name="name", attribute="name")
    relationship = fields.Field(column_name="relationship", attribute="relationship")
    phone = fields.Field(column_name="phone", attribute="phone")
    address = fields.Field(column_name="address", attribute="address")
    percentage = fields.Field(column_name="percentage", attribute="percentage")

    class Meta:
        model = Nominee
        fields = ("name", "relationship", "phone", "address", "percentage")
        export_order = fields
        import_id_fields = ("name", "phone")
        skip_unchanged = True
        report_skipped = True


class SalaryResource(resources.ModelResource):
    """Import/Export resource for Salary model.

    - `employee` column expects an Employee.employee_id value.
    - If a salary exists for the employee, it will be updated.
    - If not, a new salary will be created.
    - gross_salary is auto-calculated from basic, house_rent, conveyance, and medical
    """

    employee = fields.Field(
        column_name="employee",
        attribute="employee",
        widget=ForeignKeyWidget(Employee, field="employee_id"),
    )
    basic = fields.Field(
        column_name="basic",
        attribute="basic",
        widget=widgets.DecimalWidget(),
    )
    house_rent = fields.Field(
        column_name="house_rent",
        attribute="house_rent",
        widget=widgets.DecimalWidget(),
    )
    conveyance = fields.Field(
        column_name="conveyance",
        attribute="conveyance",
        widget=widgets.DecimalWidget(),
    )
    medical = fields.Field(
        column_name="medical",
        attribute="medical",
        widget=widgets.DecimalWidget(),
    )
    gross_salary = fields.Field(
        column_name="gross_salary",
        attribute="gross_salary",
        widget=GrossSalaryWidget(),
    )
    festival_bonus = fields.Field(
        column_name="festival_bonus",
        attribute="festival_bonus",
        widget=widgets.DecimalWidget(),
    )

    def get_instance(self, instance_loader, row):
        """
        Override to find existing Salary by employee.
        Returns the most recent salary for the employee if exists, None otherwise.
        """
        try:
            # Get employee_id from the row
            employee_id_value = row.get("employee")
            if not employee_id_value:
                return None

            # Find the employee
            employee = Employee.objects.filter(employee_id=employee_id_value).first()
            if not employee:
                logger.warning(f"Employee with ID '{employee_id_value}' not found")
                return None

            # Find the most recent salary for this employee
            salary = (
                Salary.objects.filter(employee=employee).order_by("-created_at").first()
            )
            if salary:
                logger.info(
                    f"Found existing salary for employee {employee_id_value}, will update"
                )
            else:
                logger.info(
                    f"No existing salary found for employee {employee_id_value}, will create new"
                )
            return salary
        except Exception as e:
            logger.warning(f"Error looking up Salary instance for row {row}: {e}")
            return None

    def before_save_instance(self, instance, row, **kwargs):
        """
        Calculate gross_salary from components during import (matches model.save()).
        This ensures correct numeric summation even if the incoming Excel contained
        concatenated/incorrect gross values.
        """

        def to_decimal(value):
            try:
                if value is None or value == "":
                    return Decimal("0")
                return Decimal(str(value))
            except Exception:
                return Decimal("0")

        instance.basic = to_decimal(getattr(instance, "basic", None))
        instance.house_rent = to_decimal(getattr(instance, "house_rent", None))
        instance.conveyance = to_decimal(getattr(instance, "conveyance", None))
        instance.medical = to_decimal(getattr(instance, "medical", None))
        instance.festival_bonus = to_decimal(getattr(instance, "festival_bonus", None))

        instance.gross_salary = (
            instance.basic
            + instance.house_rent
            + instance.conveyance
            + instance.medical
        )

    def dehydrate_employee(self, salary):
        return salary.employee.employee_id if salary.employee else ""

    class Meta:
        model = Salary
        fields = (
            "employee",
            "basic",
            "house_rent",
            "conveyance",
            "medical",
            "gross_salary",
            "festival_bonus",
        )
        export_order = fields
        import_id_fields = ()  # Empty tuple because we handle lookups in get_instance
        skip_unchanged = True
        report_skipped = True


@admin.register(Employee)
class EmployeeAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing employees.
    """

    list_display = (
        "user_id",
        "user",
        "employee_id",
        "department",
        "designation",
        "employment_type",
        "joining_date",
        "status",
    )
    search_fields = (
        "user__username",
        "user__email",
        "employee_id",
        "department__name",
        "designation__name",
    )
    filter_horizontal = ("supervisor",)
    list_filter = ("department", "designation", "location", "status")
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = EmployeeResource


@admin.register(Department)
class DepartmentAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing departments.
    """

    list_display = ("id", "name", "created_at", "updated_at")
    search_fields = ("name",)
    ordering = ("name",)
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = DepartmentResource


@admin.register(Designation)
class DesignationAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing designations.
    """

    list_display = ("id", "name", "department", "created_at", "updated_at")
    search_fields = ("name", "department__name")
    ordering = ("name",)
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = DesignationResource


@admin.register(Branch)
class BranchAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing branches.
    """

    list_display = ("id", "name", "address", "created_at", "updated_at")
    search_fields = ("name", "address")
    ordering = ("name",)
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = BranchResource


# Grade Resource
class GradeResource(resources.ModelResource):
    """
    Resource class for importing/exporting Grade model data.
    """

    name = fields.Field(column_name="name", attribute="name")

    class Meta:
        model = Grade
        fields = ("name",)
        export_order = fields
        import_id_fields = ("name",)
        skip_unchanged = True
        report_skipped = True


@admin.register(Grade)
class GradeAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing grades.
    """

    list_display = ("id", "name", "created_at", "updated_at")
    search_fields = ("name",)
    ordering = ("name",)
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = GradeResource


@admin.register(EmergencyContact)
class EmergencyContactAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing emergency contacts.
    """

    list_display = ("id", "name", "relationship", "phone")
    search_fields = ("employee__employee_name", "name", "phone")
    ordering = ("employee",)
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = EmergencyContactResource


@admin.register(Nominee)
class NomineeAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing nominees.
    """

    list_display = ("id", "name", "phone")
    search_fields = ("employee__user__username", "name", "email", "phone")
    ordering = ("name",)
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = NomineeResource


@admin.register(ProbationCheckLog)
class ProbationCheckLogAdmin(ModelAdmin):
    """
    Admin interface for managing probation check logs.
    """

    list_display = ("id", "date")
    search_fields = ("date",)
    ordering = ("-date",)


@admin.register(Salary)
class SalaryAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing salary records.
    """

    list_display = (
        "employee",
        "basic",
        "house_rent",
        "conveyance",
        "medical",
        "gross_salary",
        "festival_bonus",
        "created_at",
    )
    # Enable import/export in admin
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = SalaryResource

    search_fields = (
        "employee__employee_name",
        "employee__user__username",
        "employee__employee_id",
    )
    ordering = ("-created_at",)
