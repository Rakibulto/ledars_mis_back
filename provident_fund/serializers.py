from rest_framework import serializers
from .models import ProvidentFundLoan


class ProvidentFundLoanListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ProvidentFundLoan
        fields = [
            'id', 'applicant_name', 'designation', 'program_name',
            'expected_loan_amount', 'application_date', 'status',
            'created_by_name', 'created_at',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None


class ProvidentFundLoanDetailSerializer(serializers.ModelSerializer):
    created_by_info = serializers.SerializerMethodField()

    class Meta:
        model = ProvidentFundLoan
        fields = '__all__'
        read_only_fields = [
            'created_by', 'created_at', 'updated_at',
            'supervisor_signature', 'upper_authority_signature',
            'accounts_officer_signature', 'trust_member_1_signature',
            'trust_member_2_signature', 'recommender_signature',
            'recorder_signature', 'approver_signature',
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

        signature_fields = [
            'supervisor_signature', 'upper_authority_signature',
            'accounts_officer_signature', 'trust_member_1_signature',
            'trust_member_2_signature', 'recommender_signature',
            'recorder_signature', 'approver_signature',
        ]

        for field in signature_fields:
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


class ProvidentFundLoanWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProvidentFundLoan
        fields = '__all__'
        read_only_fields = [
            'created_by', 'created_at', 'updated_at',
            'supervisor_signature', 'upper_authority_signature',
            'accounts_officer_signature', 'trust_member_1_signature',
            'trust_member_2_signature', 'recommender_signature',
            'recorder_signature', 'approver_signature',
        ]


class SignSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=[
        'supervisor', 'upper_authority', 'accounts_officer',
        'trust_member_1', 'trust_member_2',
        'recommender', 'recorder', 'approver',
    ])
    confirmed = serializers.BooleanField()
