from rest_framework import serializers
from .models import Holiday
from employee.models import Branch, Designation, Department, Employee


# Nested Serializers for Read-Only Output
class BranchSerializer(serializers.ModelSerializer):
    """
    Serializer for Branch model to include id and name in HolidaySerializer output.
    """

    class Meta:
        model = Branch
        fields = ["id", "name"]


class DesignationSerializer(serializers.ModelSerializer):
    """
    Serializer for Designation model to include id and name in HolidaySerializer output.
    """

    class Meta:
        model = Designation
        fields = ["id", "name"]


class DepartmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Department model to include id and name in HolidaySerializer output.
    """

    class Meta:
        model = Department
        fields = ["id", "name"]


class EmployeeSerializer(serializers.ModelSerializer):
    """
    Serializer for Employee model to include id and employee_name in HolidaySerializer output.
    """

    id = serializers.IntegerField(source="pk", read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "employee_name"]


# Main Serializer
class HolidaySerializer(serializers.ModelSerializer):
    """
    Serializer for the Holiday model to handle CRUD operations.
    Uses nested serializers for read-only output (id and name) and PrimaryKeyRelatedField for input (IDs only).
    """

    # Read-only fields with nested serializers for output
    branches_data = BranchSerializer(source="branches", many=True, read_only=True)
    designations_data = DesignationSerializer(
        source="designations", many=True, read_only=True
    )
    departments_data = DepartmentSerializer(
        source="departments", many=True, read_only=True
    )
    assigned_employees_data = EmployeeSerializer(
        source="assigned_employees", many=True, read_only=True
    )
    excluded_employees_data = EmployeeSerializer(
        source="excluded_employees", many=True, read_only=True
    )
    employment_type_name = serializers.CharField(
        source="employment_types.name", read_only=True
    )

    # Write-only fields for input using IDs
    branches = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Branch.objects.all(),
        required=False,
        write_only=True,
        help_text="List of branch IDs to which the holiday applies",
    )
    designations = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Designation.objects.all(),
        required=False,
        write_only=True,
        help_text="List of designation IDs to which the holiday applies",
    )
    departments = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Department.objects.all(),
        required=False,
        write_only=True,
        help_text="List of department IDs to which the holiday applies",
    )
    assigned_employees = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Employee.objects.all(),
        required=False,
        write_only=True,
        help_text="List of employee IDs specifically assigned to this holiday",
    )
    excluded_employees = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Employee.objects.all(),
        required=False,
        write_only=True,
        help_text="List of employee IDs explicitly excluded from this holiday",
    )
    created_at = serializers.DateTimeField(format="%Y-%m-%d, %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%Y-%m-%d, %H:%M:%S", read_only=True)

    class Meta:
        model = Holiday
        fields = [
            "id",
            "name",
            "from_date",
            "to_date",
            "description",
            "is_global",
            "branches",
            "employment_types",
            "employment_type_name",
            "branches_data",
            "designations",
            "designations_data",
            "departments",
            "departments_data",
            "assigned_employees",
            "assigned_employees_data",
            "excluded_employees",
            "excluded_employees_data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "created_at",
            "updated_at",
            "branches_data",
            "designations_data",
            "departments_data",
            "assigned_employees_data",
            "excluded_employees_data",
        ]

    def validate(self, data):
        """
        Validate that excluded_employees and assigned_employees do not overlap,
        ensure non-global holidays have at least one filter or assignment,
        and validate that to_date is not before from_date.
        """
        assigned_employees = data.get("assigned_employees", [])
        excluded_employees = data.get("excluded_employees", [])

        # Check for overlap between assigned and excluded employees
        if set(assigned_employees) & set(excluded_employees):
            raise serializers.ValidationError(
                "An employee cannot be both assigned and excluded from the same holiday."
            )

        # If not global, ensure at least one filter or assignment is provided
        if not data.get("is_global", True):
            if data.get("employment_types") is not None and not (
                data.get("branches", [])
                or data.get("designations", [])
                or data.get("departments", [])
                or data.get("assigned_employees", [])
                or data.get("employment_types")
            ):
                raise serializers.ValidationError(
                    "Non-global holidays must specify at least one branch, designation, "
                    "department, employment type, or assigned employee."
                )

        # Validate date range
        from_date = data.get("from_date")
        to_date = data.get("to_date")
        if from_date and to_date and to_date < from_date:
            raise serializers.ValidationError(
                "to_date cannot be earlier than from_date."
            )

        return data
