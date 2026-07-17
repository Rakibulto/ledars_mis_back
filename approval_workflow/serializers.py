from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    ApprovalWorkflow,
    ApprovalLevel,
    ApprovalLevelUser,
    LEVEL_MAINTAIN_REQUIRE_CHOICES,
    MENU_CHOICES,
    MENU_CHOICES_BY_TYPE,
    MODULE_TYPE_CHOICES,
)

User = get_user_model()


# ── User mini serializer ───────────────────────────────────────────────────────

class UserMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email']

    def get_full_name(self, obj):
        return obj.username or obj.email or ''


# ── Module Type ────────────────────────────────────────────────────────────────

# ── Approval Level nested ─────────────────────────────────────────────────────

class ApprovalLevelUserSerializer(serializers.ModelSerializer):
    user_detail = UserMiniSerializer(source='user', read_only=True)

    class Meta:
        model = ApprovalLevelUser
        fields = ['id', 'user', 'user_detail', 'approval_order']


class ApprovalLevelSerializer(serializers.ModelSerializer):
    level_users = ApprovalLevelUserSerializer(many=True, read_only=True)

    class Meta:
        model = ApprovalLevel
        fields = [
            'id', 'level_number', 'from_amount', 'to_amount',
            'minimum_approval_required', 'level_maintain_require',
            'level_users', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ── Approval Workflow (write) ─────────────────────────────────────────────────

class ApprovalLevelUserWriteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    approval_order = serializers.IntegerField(min_value=1)


class ApprovalLevelWriteSerializer(serializers.Serializer):
    level_number = serializers.IntegerField(min_value=1)
    from_amount = serializers.DecimalField(max_digits=18, decimal_places=5, default=0)
    to_amount = serializers.DecimalField(max_digits=18, decimal_places=5, required=False, allow_null=True)
    minimum_approval_required = serializers.IntegerField(min_value=1, default=1)
    level_maintain_require = serializers.ChoiceField(choices=LEVEL_MAINTAIN_REQUIRE_CHOICES)
    users = serializers.ListField(
        child=ApprovalLevelUserWriteSerializer(),
        min_length=1,
        error_messages={'min_length': 'At least one approver is required per level.'},
    )


class ApprovalWorkflowWriteSerializer(serializers.Serializer):
    module_type_name = serializers.ChoiceField(choices=MODULE_TYPE_CHOICES)
    menu_name = serializers.ChoiceField(choices=MENU_CHOICES, required=False, allow_blank=True, allow_null=True)
    is_active = serializers.BooleanField(default=True)
    levels = serializers.ListField(child=ApprovalLevelWriteSerializer(), min_length=1)

    def validate(self, data):
        module_type = data.get('module_type_name')
        menu_name = data.get('menu_name')
        if module_type and menu_name:
            allowed = MENU_CHOICES_BY_TYPE.get(module_type, [])
            if menu_name not in allowed:
                raise serializers.ValidationError(
                    {'menu_name': 'The selected menu is not valid for the chosen module type.'}
                )
        return data

    def validate_levels(self, levels):
        # 1. Unique level numbers
        numbers = [lv['level_number'] for lv in levels]
        if len(numbers) != len(set(numbers)):
            raise serializers.ValidationError('Duplicate level numbers are not allowed.')

        for lv in levels:
            n = lv['level_number']
            users = lv.get('users', [])
            user_ids = [u['user_id'] for u in users]
            orders = [u['approval_order'] for u in users]

            # 2. No duplicate users within a level
            if len(user_ids) != len(set(user_ids)):
                raise serializers.ValidationError(
                    f'Level {n}: duplicate users are not allowed within the same level.'
                )

            # 3. Unique approval_order within a level
            if len(orders) != len(set(orders)):
                raise serializers.ValidationError(
                    f'Level {n}: duplicate approval order numbers are not allowed.'
                )

            # 4. minimum_approval_required <= total assigned users
            min_req = lv.get('minimum_approval_required', 1)
            if min_req > len(users):
                raise serializers.ValidationError(
                    f'Level {n}: minimum_approval_required ({min_req}) cannot exceed '
                    f'total assigned users ({len(users)}).'
                )

        # 5. Amount ranges must not overlap between levels
        ranges = []
        for lv in levels:
            lo = float(lv.get('from_amount', 0) or 0)
            hi = lv.get('to_amount')
            hi_val = float(hi) if hi is not None else float('inf')
            ranges.append((lo, hi_val, lv['level_number']))

        ranges.sort(key=lambda x: x[0])
        for i in range(len(ranges) - 1):
            if ranges[i][1] >= ranges[i + 1][0]:
                raise serializers.ValidationError(
                    f'Amount ranges overlap between Level {ranges[i][2]} '
                    f'and Level {ranges[i + 1][2]}.'
                )

        return levels


# ── Approval Workflow (read) ──────────────────────────────────────────────────

class ApprovalWorkflowSerializer(serializers.ModelSerializer):
    menu_name = serializers.CharField(read_only=True)
    module_type_name = serializers.CharField(read_only=True)
    total_levels = serializers.IntegerField(read_only=True)
    levels = ApprovalLevelSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ApprovalWorkflow
        fields = [
            'id', 'menu_name', 'module_type_name',
            'is_active', 'total_levels', 'levels',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            u = obj.created_by
            return u.username or u.email or ''
        return None


# ── List / lightweight serializer for the table ───────────────────────────────

class ApprovalWorkflowListSerializer(serializers.ModelSerializer):
    menu_name = serializers.CharField(read_only=True)
    module_type_name = serializers.CharField(read_only=True)
    total_levels = serializers.IntegerField(read_only=True)
    created_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ApprovalWorkflow
        fields = [
            'id', 'menu_name', 'module_type_name',
            'is_active', 'total_levels',
            'created_by', 'created_by_name', 'created_at',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            u = obj.created_by
            return u.username or u.email
        return None
