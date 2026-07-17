from .models import Notification
from rest_framework import serializers
from employee.models import Employee
from authentication.models import User

class EmployeeSerializer(serializers.ModelSerializer):
    employment_type = serializers.CharField(source='employment_type.name', read_only=True)
    
    class Meta:
        model = Employee
        fields = ['employee_id', 'employee_name', 'designation', 'joining_date', 'employment_type']

class UserWithEmployeeSerializer(serializers.ModelSerializer):
    employee_info = EmployeeSerializer(source='employee', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'employee_info']

class NofificationSerializer(serializers.ModelSerializer):
    employee = UserWithEmployeeSerializer()
    receiver = UserWithEmployeeSerializer()
    class Meta:
        model = Notification
        fields = '__all__'