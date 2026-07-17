from rest_framework import serializers
from .models import Project, ProjectActivity, Notification


# -----------------------------
# Project Activity Serializer
# -----------------------------
class ProjectActivitySerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = ProjectActivity
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at')


# -----------------------------
# Project Serializer
# -----------------------------
class ProjectSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    activities = ProjectActivitySerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at', 'updated_at')

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
    

# -----------------------------
# Notification Serializer
# -----------------------------
class NotificationSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    activity_title = serializers.CharField(source='activity.title', read_only=True)

    class Meta:
        model = Notification
        fields = '__all__'