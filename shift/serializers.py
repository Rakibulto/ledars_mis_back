from .models import Shift
from rest_framework import serializers

class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = ['id', 'name', 'office_start_time', 'office_start_time_consideration', 'office_end_time', 'office_end_time_consideration', 'check_in_start_time', 'check_in_end_time', 'check_out_start_time', 'check_out_end_time']