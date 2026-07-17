from rest_framework import serializers
from .models import ReturnHeader, ReturnLine, ReturnDamageHistory


class ReturnLineSerializer(serializers.ModelSerializer):
    available_quantity = serializers.SerializerMethodField()

    class Meta:
        model = ReturnLine
        fields = '__all__'
        read_only_fields = ['id', 'return_header']

    def get_available_quantity(self, obj):
        avail = float(obj.issued_quantity or 0) - float(obj.previously_returned_quantity or 0)
        return max(avail, 0)


class ReturnDamageHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnDamageHistory
        fields = '__all__'
        read_only_fields = ['id', 'recorded_at']


class ReturnHeaderReadSerializer(serializers.ModelSerializer):
    lines = ReturnLineSerializer(many=True, read_only=True)
    damage_histories = ReturnDamageHistorySerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)
    received_by_name = serializers.CharField(source='received_by.username', read_only=True)
    total_return_quantity = serializers.SerializerMethodField()
    total_good_quantity = serializers.SerializerMethodField()
    total_damaged_quantity = serializers.SerializerMethodField()
    resolved_source_location = serializers.SerializerMethodField()
    resolved_destination_location = serializers.SerializerMethodField()

    class Meta:
        model = ReturnHeader
        fields = '__all__'

    def get_total_return_quantity(self, obj):
        return sum(float(l.return_quantity or 0) for l in obj.lines.all())

    def get_total_good_quantity(self, obj):
        return sum(float(l.good_quantity or 0) for l in obj.lines.all())

    def get_total_damaged_quantity(self, obj):
        return sum(float(l.damaged_quantity or 0) for l in obj.lines.all())

    def _get_source_doc_num(self, obj):
        first_line = obj.lines.first()
        return first_line.source_document_number if first_line else None

    def get_resolved_source_location(self, obj):
        """Return stored value if present, else look up from source document."""
        if obj.source_location:
            return obj.source_location
        doc_num = self._get_source_doc_num(obj)
        if not doc_num:
            return None
        try:
            if obj.source_document_type == 'GIN':
                from inventory.models.operations import GIN
                gin = GIN.objects.filter(gin_number=doc_num).first()
                if gin:
                    return gin.issued_to or gin.project or None
            elif obj.source_document_type == 'INTERNAL_TRANSFER':
                from inventory.models.operations import InternalTransfer
                it = InternalTransfer.objects.select_related('to_office').filter(
                    transfer_number=doc_num
                ).first()
                if it:
                    return it.to_office.name if it.to_office else None
        except Exception:
            pass
        return None

    def get_resolved_destination_location(self, obj):
        """Return stored value if present, else look up from source document."""
        if obj.destination_location:
            return obj.destination_location
        doc_num = self._get_source_doc_num(obj)
        if not doc_num:
            return None
        try:
            if obj.source_document_type == 'GIN':
                from inventory.models.operations import GIN
                gin = GIN.objects.select_related('office_location').filter(
                    gin_number=doc_num
                ).first()
                if gin:
                    return (
                        gin.office_location.name if gin.office_location
                        else gin.issue_from or None
                    )
            elif obj.source_document_type == 'INTERNAL_TRANSFER':
                from inventory.models.operations import InternalTransfer
                it = InternalTransfer.objects.select_related('from_office').filter(
                    transfer_number=doc_num
                ).first()
                if it:
                    return it.from_office.name if it.from_office else None
        except Exception:
            pass
        return None


class ReturnHeaderWriteSerializer(serializers.ModelSerializer):
    lines = ReturnLineSerializer(many=True, required=False)

    class Meta:
        model = ReturnHeader
        fields = '__all__'
        read_only_fields = ['return_number', 'created_at', 'updated_at',
                            'submitted_at', 'dispatched_at', 'received_at']

    def _save_lines(self, header, lines_data):
        if lines_data is None:
            return
        header.lines.all().delete()
        for item in lines_data:
            item.pop('id', None)
            item.pop('return_header', None)
            ReturnLine.objects.create(return_header=header, **item)

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        header = ReturnHeader.objects.create(**validated_data)
        self._save_lines(header, lines_data)
        return header

    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self._save_lines(instance, lines_data)
        return instance
