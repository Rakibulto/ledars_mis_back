from rest_framework import serializers
from projects.models import PMRole, PMUserRole


class PMRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PMRole
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class PMUserRoleSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = PMUserRole
        fields = "__all__"

    def get_user_name(self, obj):
        return obj.user.username or obj.user.email if obj.user else None

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None
