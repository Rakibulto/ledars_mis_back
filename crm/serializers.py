from rest_framework import serializers
from .models import Lead, LeadProject, LeadFollowUp, LeadFollowUpAttachment


class LeadListSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            'id', 'lead_id', 'project_name', 'project_type', 'name',
            'phone', 'area', 'status', 'created_at', 'assigned_to_name',
        ]

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name() or obj.assigned_to.username
        return '—'


class LeadDetailSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = '__all__'

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return '—'

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name() or obj.assigned_to.username
        return '—'


class LeadWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = '__all__'
        read_only_fields = ['lead_id', 'created_at', 'updated_at']


class LeadProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadProject
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class LeadFollowUpAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadFollowUpAttachment
        fields = ['id', 'file', 'file_name', 'file_size', 'uploaded_at']
        read_only_fields = ['file_name', 'file_size', 'uploaded_at']


class LeadFollowUpReadSerializer(serializers.ModelSerializer):
    assigned_to = serializers.SerializerMethodField()
    assigned_to_ids = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    attachments = LeadFollowUpAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = LeadFollowUp
        fields = [
            'id', 'lead', 'title', 'description', 'next_contact_date',
            'assigned_to', 'assigned_to_ids', 'created_by', 'created_by_name',
            'attachments', 'created_at', 'updated_at',
        ]

    def get_assigned_to(self, obj):
        return [
            {'id': u.id, 'name': u.get_full_name() or u.username, 'email': u.email}
            for u in obj.assigned_to.all()
        ]

    def get_assigned_to_ids(self, obj):
        return list(obj.assigned_to.values_list('id', flat=True))

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return '—'


class LeadFollowUpWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadFollowUp
        fields = [
            'id', 'lead', 'title', 'description', 'next_contact_date',
            'assigned_to',
        ]
        read_only_fields = ['lead']

    def create(self, validated_data):
        assigned_to_ids = validated_data.pop('assigned_to', [])
        follow_up = LeadFollowUp.objects.create(**validated_data)
        if assigned_to_ids:
            follow_up.assigned_to.set(assigned_to_ids)
        else:
            follow_up.assigned_to.add(self.context['request'].user)
        return follow_up

    def update(self, instance, validated_data):
        assigned_to_ids = validated_data.pop('assigned_to', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if assigned_to_ids is not None:
            instance.assigned_to.set(assigned_to_ids)
        return instance
