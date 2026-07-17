from django.contrib import admin
from import_export import resources, fields, widgets
from .models import Shift
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ExportForm, ImportForm, SelectableFieldsExportForm
import logging

logger = logging.getLogger(__name__)

class ShiftResource(resources.ModelResource):
    """
    Resource class for importing/exporting Shift model data.
    Handles TimeField widgets and ensures consistent formatting.
    Excludes created_at and updated_at to allow Django's auto_now_add/auto_now.
    """
    name = fields.Field(column_name='name', attribute='name')
    
    office_start_time = fields.Field(
        column_name='office_start_time',
        attribute='office_start_time',
        widget=widgets.TimeWidget(format='%H:%M:%S')
    )
    office_end_time = fields.Field(
        column_name='office_end_time',
        attribute='office_end_time',
        widget=widgets.TimeWidget(format='%H:%M:%S')
    )
    office_start_time_consideration = fields.Field(
        column_name='office_start_time_consideration',
        attribute='office_start_time_consideration'
    )
    office_end_time_consideration = fields.Field(
        column_name='office_end_time_consideration',
        attribute='office_end_time_consideration'
    )
    check_in_start_time = fields.Field(
        column_name='check_in_start_time',
        attribute='check_in_start_time',
        widget=widgets.TimeWidget(format='%H:%M:%S')
    )
    check_in_end_time = fields.Field(
        column_name='check_in_end_time',
        attribute='check_in_end_time',
        widget=widgets.TimeWidget(format='%H:%M:%S')
    )
    check_out_start_time = fields.Field(
        column_name='check_out_start_time',
        attribute='check_out_start_time',
        widget=widgets.TimeWidget(format='%H:%M:%S')
    )
    check_out_end_time = fields.Field(
        column_name='check_out_end_time',
        attribute='check_out_end_time',
        widget=widgets.TimeWidget(format='%H:%M:%S')
    )

    class Meta:
        model = Shift
        fields = (
            'name',
            'office_start_time',
            'office_end_time',
            'office_start_time_consideration',
            'office_end_time_consideration',
            'check_in_start_time',
            'check_in_end_time',
            'check_out_start_time',
            'check_out_end_time',
        )
        export_order = fields
        import_id_fields = ('name',)
        skip_unchanged = True
        report_skipped = True



@admin.register(Shift)
class ShiftAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Admin interface for managing shifts.
    """
    list_display = ('name', 'office_start_time', 'office_end_time', 'created_at', 'updated_at')
    search_fields = ('name',)
    ordering = ('name',)
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    resource_class = ShiftResource
    