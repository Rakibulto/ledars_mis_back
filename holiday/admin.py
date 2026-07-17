from django.contrib import admin
from .models import Holiday
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin
from employee.models import Branch, Designation, Department, Employee
from leave.models import LeaveGroup
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.contrib.filters.admin import (
    MultipleRelatedDropdownFilter,
)
import logging

# Set up logging for debugging
logger = logging.getLogger(__name__)

class HolidayResource(resources.ModelResource):
    """
    Resource class for importing/exporting Holiday model data.
    Ensures consistency between export and import formats.
    """
    name = fields.Field(column_name='name', attribute='name')
    from_date = fields.Field(
        column_name='from_date',
        attribute='from_date',
        widget=widgets.DateWidget(format='%Y-%m-%d')
    )
    to_date = fields.Field(
        column_name='to_date',
        attribute='to_date',
        widget=widgets.DateWidget(format='%Y-%m-%d')
    )
    description = fields.Field(column_name='description', attribute='description')
    is_global = fields.Field(
        column_name='is_global',
        attribute='is_global',
        widget=widgets.BooleanWidget()
    )
    employment_types = fields.Field(
        column_name='employment_types',
        attribute='employment_types',
        widget=widgets.ForeignKeyWidget(LeaveGroup, field='name')
    )
    branches = fields.Field(
        column_name='branches',
        attribute='branches',
        widget=widgets.ManyToManyWidget(Branch, field='name', separator=',')
    )
    designations = fields.Field(
        column_name='designations',
        attribute='designations',
        widget=widgets.ManyToManyWidget(Designation, field='name', separator=',')
    )
    departments = fields.Field(
        column_name='departments',
        attribute='departments',
        widget=widgets.ManyToManyWidget(Department, field='name', separator=',')
    )
    assigned_employees = fields.Field(
        column_name='assigned_employees',
        attribute='assigned_employees',
        widget=widgets.ManyToManyWidget(Employee, field='employee_id', separator=',')
    )
    excluded_employees = fields.Field(
        column_name='excluded_employees',
        attribute='excluded_employees',
        widget=widgets.ManyToManyWidget(Employee, field='employee_id', separator=',')
    )
    created_at = fields.Field(
        column_name='created_at',
        attribute='created_at',
        widget=widgets.DateTimeWidget(format='%Y-%m-%d %H:%M:%S')
    )
    updated_at = fields.Field(
        column_name='updated_at',
        attribute='updated_at',
        widget=widgets.DateTimeWidget(format='%Y-%m-%d %H:%M:%S')
    )

    def dehydrate_assigned_employees(self, holiday):
        """
        Custom export logic for assigned_employees to handle None employee_id values.
        """
        employee_ids = [emp.employee_id for emp in holiday.assigned_employees.all() if emp.employee_id]
        if not employee_ids:
            logger.warning(f"No valid employee_id found for assigned_employees in holiday {holiday.name}")
        return ','.join(employee_ids)

    def dehydrate_excluded_employees(self, holiday):
        """
        Custom export logic for excluded_employees to handle None employee_id values.
        """
        employee_ids = [emp.employee_id for emp in holiday.excluded_employees.all() if emp.employee_id]
        if not employee_ids:
            logger.warning(f"No valid employee_id found for excluded_employees in holiday {holiday.name}")
        return ','.join(employee_ids)

    class Meta:
        model = Holiday
        fields = (
            'name', 'from_date', 'to_date', 'description', 'is_global', 'employment_types',
            'branches', 'designations', 'departments', 'assigned_employees', 'excluded_employees',
            'created_at', 'updated_at'
        )
        export_order = fields  
        import_id_fields = ('name', 'from_date', 'to_date') 
        skip_unchanged = True 
        report_skipped = True 

    def before_import_row(self, row, **kwargs):
        """
        Validate dates and employee_id values before importing a row.
        """
        from_date = row.get('from_date')
        to_date = row.get('to_date')
        if from_date and to_date:
            try:
                from datetime import datetime
                from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
                to_date = datetime.strptime(to_date, '%Y-%m-%d').date()
                if to_date < from_date:
                    raise ValueError("to_date cannot be earlier than from_date")
            except ValueError as e:
                raise ValueError(f"Invalid date format or {str(e)}")

        # Validate employee_id values
        for field in ['assigned_employees', 'excluded_employees']:
            if row.get(field):
                employee_ids = row[field].split(',')
                for emp_id in employee_ids:
                    if emp_id and not Employee.objects.filter(employee_id=emp_id).exists():
                        raise ValueError(f"Invalid employee_id '{emp_id}' in {field}")

        # Ensure employment_types exists
        if row.get('employment_types'):
            LeaveGroup.objects.get_or_create(name=row['employment_types'])

    def after_save_instance(self, instance, row, dry_run, **kwargs):
        """
        Ensure dates are validated during import.
        Accepts row instead of using_transactions for compatibility with django-import-export.
        """
        instance.validate_dates()

@admin.register(Holiday)
class HolidayAdmin(ModelAdmin, ImportExportModelAdmin):
    list_display = ('name', 'from_date', 'to_date', 'is_global', 'created_at', 'updated_at')
    search_fields = ('name', 'assigned_employees__employee_name' , 'branches__name', 'designations__name', 'departments__name')
    list_filter = [
                ('is_global'), 
                ('branches', MultipleRelatedDropdownFilter), 
                ('designations', MultipleRelatedDropdownFilter), 
                ('departments', MultipleRelatedDropdownFilter)
    ]
    list_filter_submit = True
    ordering = ('-created_at',)
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = HolidayResource