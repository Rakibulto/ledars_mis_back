from rest_framework import serializers
from .models import Meeting, MeetingAttachment


class MeetingListSerializer(serializers.ModelSerializer):
    assigned_to_names = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            'id', 'meeting_id', 'title', 'date', 'start_time', 'end_time',
            'status', 'location', 'meeting_link', 'agenda', 'minutes',
            'assigned_to_names', 'created_by_name', 'created_by', 'created_at', 'updated_at',
        ]

    def get_assigned_to_names(self, obj):
        return [
            {'id': u.id, 'name': u.get_full_name() or u.username}
            for u in obj.assigned_to.all()
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return '—'


class MeetingDetailSerializer(serializers.ModelSerializer):
    assigned_to = serializers.SerializerMethodField()
    assigned_to_ids = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = '__all__'

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

    def get_attachments(self, obj):
        return MeetingAttachmentSerializer(obj.attachments.all(), many=True).data


class MeetingWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = '__all__'
        read_only_fields = ['meeting_id', 'created_at', 'updated_at']

    def create(self, validated_data):
        assigned_to_ids = validated_data.pop('assigned_to', [])
        meeting = Meeting.objects.create(**validated_data)
        if assigned_to_ids:
            meeting.assigned_to.set(assigned_to_ids)
        return meeting

    def update(self, instance, validated_data):
        assigned_to_ids = validated_data.pop('assigned_to', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if assigned_to_ids is not None:
            instance.assigned_to.set(assigned_to_ids)
        return instance


class MeetingAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingAttachment
        fields = ['id', 'file', 'file_name', 'file_size', 'uploaded_at']
        read_only_fields = ['file_name', 'file_size', 'uploaded_at']
