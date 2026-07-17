from rest_framework import serializers
from .models import MovementManagement


def normalize_project_name(value):
    """Handle backward compatibility: old string values → list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        return [value]
    return []


class MovementManagementListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()

    class Meta:
        model = MovementManagement
        fields = [
            'id', 'name', 'designation', 'grade', 'project_name',
            'grand_total', 'status', 'created_by_name', 'created_at',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None

    def get_project_name(self, obj):
        return normalize_project_name(obj.project_name)


class MovementManagementDetailSerializer(serializers.ModelSerializer):
    created_by_info = serializers.SerializerMethodField()

    class Meta:
        model = MovementManagement
        fields = '__all__'
        read_only_fields = [
            'created_by', 'created_at', 'updated_at',
            'submitted_by_signature', 'checked_supervised_signature',
            'approved_by_signature',
        ]

    def get_created_by_info(self, obj):
        if obj.created_by:
            return {
                'id': obj.created_by.id,
                'name': obj.created_by.get_full_name() or obj.created_by.email,
                'email': obj.created_by.email,
            }
        return None

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get('request')

        # Normalize project_name for backward compatibility
        ret['project_name'] = normalize_project_name(ret.get('project_name'))

        for field in ('submitted_by_signature', 'checked_supervised_signature', 'approved_by_signature'):
            sig = ret.get(field)
            if sig and isinstance(sig, dict):
                email = sig.get('email')
                if email:
                    try:
                        from employee.models import Employee
                        employee = Employee.objects.get(user__email=email)
                        if employee.signature:
                            sig['signature_image'] = (
                                request.build_absolute_uri(employee.signature.url)
                                if request
                                else employee.signature.url
                            )
                        else:
                            sig['signature_image'] = None
                    except Employee.DoesNotExist:
                        sig['signature_image'] = None
                else:
                    sig['signature_image'] = None

        return ret


class SignSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['submitted_by', 'checked_supervised', 'approved_by'])
    confirmed = serializers.BooleanField()
