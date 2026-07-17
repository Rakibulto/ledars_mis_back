from rest_framework import serializers
from .models import FinalSettlement
from employee.models import Employee


class FinalSettlementListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FinalSettlement
        fields = [
            'id', 'project_name', 'name_of_staff', 'designation',
            'date', 'status', 'created_at', 'created_by_name',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''


class FinalSettlementDetailSerializer(serializers.ModelSerializer):
    created_by_info = serializers.SerializerMethodField()

    class Meta:
        model = FinalSettlement
        fields = '__all__'
        read_only_fields = [
            'created_by', 'created_at', 'updated_at',
            'status', 'supervisor_signature', 'finance_signature',
            'management_signature', 'payment_completed_at', 'payment_completed_by',
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

        for field in ('supervisor_signature', 'finance_signature', 'management_signature'):
            sig = ret.get(field)
            if sig and isinstance(sig, dict):
                email = sig.get('email')
                if email:
                    try:
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


class SignatureSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['supervisor', 'finance', 'management'])
    confirmed = serializers.BooleanField(required=True)

    def validate_confirmed(self, value):
        if not value:
            raise serializers.ValidationError("You must confirm the signature action.")
        return value