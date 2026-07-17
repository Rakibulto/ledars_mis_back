from rest_framework import serializers
from accounting.models import AccountingSettings, NumberSequence, ApprovalRule, ApprovalWorkflow, AuditLog, PostingRule, IntegrationRule, LockDate


class AccountingSettingsSerializer(serializers.ModelSerializer):
    # Expose a read-only URL for the logo and accept upload on write
    print_logo_url = serializers.SerializerMethodField(read_only=True)
    print_logo = serializers.ImageField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = AccountingSettings
        fields = "__all__"

    def get_print_logo_url(self, obj):
        try:
            if obj.print_logo:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(obj.print_logo.url)
                return obj.print_logo.url
        except Exception:
            pass
        return None


class NumberSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NumberSequence
        fields = "__all__"


class ApprovalRuleSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(
        source="approver.get_full_name", read_only=True
    )

    class Meta:
        model = ApprovalRule
        fields = "__all__"


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(
        source="user.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = AuditLog
        fields = "__all__"
        read_only_fields = ["__all__"]


class PostingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostingRule
        fields = "__all__"


class IntegrationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationRule
        fields = "__all__"


class ApprovalWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalWorkflow
        fields = "__all__"


class LockDateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LockDate
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]
