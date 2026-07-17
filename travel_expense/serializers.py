from decimal import Decimal
from rest_framework import serializers
from .models import TravelExpense, TravelExpenseAttachment


def calculate_row_total(row):
    travel_fare = Decimal(str(row.get('travel_fare') or 0))
    food = Decimal(str(row.get('food') or 0))
    lodging = Decimal(str(row.get('lodging') or 0))
    return travel_fare + food + lodging


def calculate_totals(expense_rows):
    total_travel_fare = Decimal('0')
    total_food = Decimal('0')
    total_lodging = Decimal('0')
    grand_total = Decimal('0')

    for row in expense_rows or []:
        travel_fare = Decimal(str(row.get('travel_fare') or 0))
        food = Decimal(str(row.get('food') or 0))
        lodging = Decimal(str(row.get('lodging') or 0))
        row_total = travel_fare + food + lodging

        row['row_total'] = float(row_total)
        total_travel_fare += travel_fare
        total_food += food
        total_lodging += lodging
        grand_total += row_total

    return {
        'total_travel_fare': total_travel_fare,
        'total_food': total_food,
        'total_lodging': total_lodging,
        'grand_total': grand_total,
    }


class TravelExpenseListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TravelExpense
        fields = [
            'id', 'project', 'name', 'designation', 'date_of_submission',
            'status', 'grand_total', 'created_by_name', 'created_at',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None


class TravelExpenseAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = TravelExpenseAttachment
        fields = ['id', 'row_index', 'file', 'file_url', 'original_name', 'file_size', 'uploaded_at']
        read_only_fields = ['original_name', 'file_size', 'uploaded_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        elif obj.file:
            return obj.file.url
        return None


class TravelExpenseDetailSerializer(serializers.ModelSerializer):
    created_by_info = serializers.SerializerMethodField()
    attachments = TravelExpenseAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = TravelExpense
        fields = '__all__'
        read_only_fields = [
            'created_by', 'created_at', 'updated_at',
            'total_travel_fare', 'total_food', 'total_lodging', 'grand_total',
            'prepared_received_signature', 'checked_by_signature',
            'accountant_signature', 'approved_by_signature',
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

        for field in ('prepared_received_signature', 'checked_by_signature', 'accountant_signature', 'approved_by_signature'):
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


class TravelExpenseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TravelExpense
        fields = [
            'id', 'project', 'date_of_submission', 'name', 'designation',
            'purpose', 'expense_rows', 'note', 'status',
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        expense_rows = validated_data.get('expense_rows', [])
        for row in expense_rows:
            row['row_total'] = float(calculate_row_total(row))
        totals = calculate_totals(expense_rows)
        validated_data['expense_rows'] = expense_rows
        validated_data.update(totals)
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        expense_rows = validated_data.get('expense_rows', instance.expense_rows)
        for row in expense_rows:
            row['row_total'] = float(calculate_row_total(row))
        totals = calculate_totals(expense_rows)
        validated_data['expense_rows'] = expense_rows
        validated_data.update(totals)
        return super().update(instance, validated_data)


class SignSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['prepared_received', 'checked_by', 'accountant', 'approved_by'])
    confirmed = serializers.BooleanField()
