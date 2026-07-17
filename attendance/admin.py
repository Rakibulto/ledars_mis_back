from django.contrib import admin
from .models import AttendanceData, AttendanceAdjustmentRequest, AttendanceAdjustmentApproval, AttendanceHistory, CutOff
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from import_export import fields
from import_export.widgets import ForeignKeyWidget
from employee.models import Employee
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.contrib.filters.admin import (
    RelatedDropdownFilter,
)

class AttendanceDataResource(resources.ModelResource):
    employee = fields.Field(
        column_name='employee',
        attribute='employee',
        widget=ForeignKeyWidget(Employee, 'user_id')
    )
    
    class Meta:
        model = AttendanceData
        fields = ('id', 'employee', 'rfid_or_machine_code', 'device_serial_number', 'login_type', 'timestamp', 'attendance_status', 'remarks')

class AttendanceHistoryResource(resources.ModelResource):
    employee = fields.Field(
        column_name='employee',
        attribute='employee',
        widget=ForeignKeyWidget(Employee, 'user_id')
    )
    
    class Meta:
        model = AttendanceHistory
        fields = ('employee', 'date', 'check_in_time', 'check_out_time', 'is_late', 'rfid_or_machine_code', 'late_by', 'early_out_by', 'status', 'remarks')
        import_id_fields = ('employee', 'date')


@admin.register(AttendanceData)
class AttendanceDataAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing attendance data.
    """
    list_display = ('employee_email', 'attendance_status', 'device_serial_number', 'timestamp',)
    search_fields = ('employee__employee_name', 'employee__employee_id', 'employee__personal_email_id')
    list_filter = ('attendance_status', 'device_serial_number', 'employee__department__name' )
    ordering = ('-created_at',)
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = AttendanceDataResource

    def employee_email(self, obj):
        return obj.employee.personal_email_id if obj.employee else "-"
    employee_email.short_description = 'Employee Email'
    employee_email.admin_order_field = 'employee__personal_email_id'


@admin.register(AttendanceAdjustmentRequest)
class AttendanceAdjustmentRequestAdmin(ModelAdmin):
    """
    Admin interface for managing attendance adjustment requests.
    """
    list_display = ('id', 'employee', 'date', 'check_type' , 'actual_duty_start_time', 'actual_arival_time', 'adjustment_type', 'status')
    search_fields = ('employee__personal_email_id', 'date', 'adjustment_type', 'status')
    list_filter = ('adjustment_type', 'status')

@admin.register(AttendanceAdjustmentApproval)
class AttendanceAdjustmentApprovalAdmin(ModelAdmin):
    """
    Admin interface for managing attendance adjustment approvals.
    """
    list_display = ('id', 'adjustment_request', 'approver', 'status', 'created_at', 'updated_at')
    list_filter = ('status',)

@admin.register(AttendanceHistory)
class AttendanceHistoryAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing attendance history.
    """
    list_display = ('id', 'employee', 'date', 'check_in_time', 'check_out_time', 'is_late', 'is_holiday', 'is_weekend', 'rfid_or_machine_code' ,'late_by', 'early_out_by', 'status', 'remarks')
    search_fields = ('employee__personal_email_id', 'date', 'status')

    list_filter = [   
        ('date'),
        ('is_late'),  
        ('is_holiday'),           
        ('is_weekend'),           
        ('employee', RelatedDropdownFilter), 
    ]
    list_filter_submit = True
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = AttendanceHistoryResource


@admin.register(CutOff)
class CutOffAdmin(ModelAdmin):
    """
    Admin interface for managing cut-off dates.
    """
    list_display = ('name', 'date', 'cut_off', 'created_at', 'updated_at')
    search_fields = ('name', 'date')

