from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from .models import Todo, TodoAttachment

User = get_user_model()


class UserMiniSerializer(serializers.ModelSerializer):
    """Lightweight user serializer for dropdowns."""
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'name', 'email']

    def get_name(self, obj):
        return obj.username or obj.email or ''


class TodoAttachmentSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)

    class Meta:
        model = TodoAttachment
        fields = ['id', 'todo', 'user', 'file', 'remarks', 'created_at']
        read_only_fields = ['id', 'todo', 'user', 'created_at']


class TodoListSerializer(serializers.ModelSerializer):
    """List serializer with role field."""
    creator_name = serializers.CharField(read_only=True)
    creator_email = serializers.EmailField(read_only=True)
    assigned_users = serializers.SerializerMethodField()
    assigned_user_ids = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = Todo
        fields = [
            'id', 'todo_title', 'description', 'expected_date', 'status',
            'assigned_users', 'assigned_user_ids',
            'creator_name', 'creator_email', 'creator_user_id',
            'role', 'created_at', 'updated_at',
            'is_recurring', 'recurrence_type', 'parent_todo', 'next_expected_date',
        ]

    def get_assigned_users(self, obj):
        return [
            {
                'id': u.id,
                'name': u.username or u.email or '',
                'email': u.email or '',
                'attachments_count': obj.attachments.filter(user=u).count(),
                'last_submission_at': (
                    obj.attachments.filter(user=u).order_by('-created_at')
                    .values_list('created_at', flat=True).first()
                ),
            }
            for u in obj.assign_users.all()
        ]

    def get_assigned_user_ids(self, obj):
        return list(obj.assign_users.values_list('id', flat=True))

    def get_role(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if obj.creator == request.user:
                return 'created'
            if request.user in obj.assign_users.all():
                return 'assigned'
        return 'viewer'


class TodoDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single todo view."""
    assigned_users = serializers.SerializerMethodField()
    creator_name = serializers.CharField(read_only=True)
    creator_email = serializers.EmailField(read_only=True)
    role = serializers.SerializerMethodField()
    creator_attachments_count = serializers.SerializerMethodField()
    creator_last_submission_at = serializers.SerializerMethodField()

    class Meta:
        model = Todo
        fields = [
            'id', 'todo_title', 'description', 'expected_date', 'status',
            'assigned_users', 'creator', 'creator_name',
            'creator_email', 'creator_user_id',
            'role', 'created_at', 'updated_at',
            'creator_attachments_count', 'creator_last_submission_at',
            'is_recurring', 'recurrence_type', 'recurrence_weekdays',
            'recurrence_day_of_month', 'parent_todo', 'next_expected_date',
        ]
        read_only_fields = ['id', 'creator', 'creator_name', 'creator_email',
                            'creator_user_id', 'created_at', 'updated_at']

    def get_assigned_users(self, obj):
        return [
            {
                'id': u.id,
                'name': u.username or u.email or '',
                'email': u.email or '',
                'attachments_count': obj.attachments.filter(user=u).count(),
                'last_submission_at': (
                    obj.attachments.filter(user=u).order_by('-created_at')
                    .values_list('created_at', flat=True).first()
                ),
            }
            for u in obj.assign_users.all()
        ]

    def get_role(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if obj.creator == request.user:
                return 'created'
            if request.user in obj.assign_users.all():
                return 'assigned'
        return 'viewer'

    def get_creator_attachments_count(self, obj):
        return obj.attachments.filter(user=obj.creator).count()

    def get_creator_last_submission_at(self, obj):
        return (
            obj.attachments.filter(user=obj.creator).order_by('-created_at')
            .values_list('created_at', flat=True).first()
        )


class TodoCreateSerializer(serializers.ModelSerializer):
    """Create serializer - saves snapshot fields from request user."""
    assign_user_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, write_only=True
    )

    class Meta:
        model = Todo
        fields = [
            'id', 'todo_title', 'description', 'expected_date', 'status',
            'assign_user_ids', 'created_at', 'updated_at',
            'is_recurring', 'recurrence_type', 'recurrence_weekdays',
            'recurrence_day_of_month',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        recurrence_type = data.get('recurrence_type', 'none')
        is_recurring = data.get('is_recurring', False)

        if is_recurring and recurrence_type == 'weekly':
            weekdays = data.get('recurrence_weekdays')
            if not weekdays or not isinstance(weekdays, list):
                raise serializers.ValidationError(
                    {"recurrence_weekdays": "Provide a list of weekday numbers (0=Mon..6=Sun)."}
                )
            if not all(isinstance(d, int) and 0 <= d <= 6 for d in weekdays):
                raise serializers.ValidationError(
                    {"recurrence_weekdays": "Each weekday must be an integer between 0 (Mon) and 6 (Sun)."}
                )

        if is_recurring and recurrence_type == 'monthly':
            day = data.get('recurrence_day_of_month')
            if day is None or not (1 <= day <= 31):
                raise serializers.ValidationError(
                    {"recurrence_day_of_month": "Provide a valid day of month (1-31)."}
                )

        if not is_recurring:
            data['recurrence_type'] = 'none'
            data['recurrence_weekdays'] = None
            data['recurrence_day_of_month'] = None

        return data

    def validate_status(self, value):
        """Only draft, pending, and hold allowed at creation."""
        if value not in ['draft', 'hold', 'pending']:
            raise serializers.ValidationError(
                "Status at creation time can only be 'draft', 'pending' or 'hold'."
            )
        return value

    def create(self, validated_data):
        assign_user_ids = validated_data.pop('assign_user_ids', [])
        request = self.context.get('request')
        user = request.user if request else None

        # Save snapshot fields from logged-in user
        validated_data['creator'] = user
        validated_data['creator_name'] = user.username if user else None
        validated_data['creator_email'] = user.email if user else None
        validated_data['creator_user_id'] = user.id if user else None

        # Calculate next_expected_date for recurring todos
        is_recurring = validated_data.get('is_recurring', False)
        recurrence_type = validated_data.get('recurrence_type', 'none')
        expected_date = validated_data.get('expected_date')

        if is_recurring and expected_date and recurrence_type != 'none':
            from datetime import timedelta
            from dateutil.relativedelta import relativedelta

            if recurrence_type == 'daily':
                validated_data['next_expected_date'] = expected_date + timedelta(days=1)
            elif recurrence_type == 'weekly':
                validated_data['next_expected_date'] = expected_date + timedelta(days=7)
            elif recurrence_type == 'monthly':
                validated_data['next_expected_date'] = expected_date + relativedelta(months=1)

        todo = super().create(validated_data)

        if assign_user_ids:
            users = User.objects.filter(id__in=assign_user_ids)
            todo.assign_users.set(users)

        return todo


class TodoUpdateSerializer(serializers.ModelSerializer):
    """Update serializer - all 4 statuses allowed, no snapshot field updates."""
    assign_user_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, write_only=True
    )

    class Meta:
        model = Todo
        fields = [
            'id', 'todo_title', 'description', 'expected_date', 'status',
            'assign_user_ids', 'updated_at',
            'is_recurring', 'recurrence_type', 'recurrence_weekdays',
            'recurrence_day_of_month',
        ]
        read_only_fields = ['id', 'updated_at']

    def validate(self, data):
        recurrence_type = data.get('recurrence_type', self.instance.recurrence_type if self.instance else 'none')
        is_recurring = data.get('is_recurring', self.instance.is_recurring if self.instance else False)

        if is_recurring and recurrence_type == 'weekly':
            weekdays = data.get('recurrence_weekdays', self.instance.recurrence_weekdays if self.instance else None)
            if not weekdays or not isinstance(weekdays, list):
                raise serializers.ValidationError(
                    {"recurrence_weekdays": "Provide a list of weekday numbers (0=Mon..6=Sun)."}
                )
            if not all(isinstance(d, int) and 0 <= d <= 6 for d in weekdays):
                raise serializers.ValidationError(
                    {"recurrence_weekdays": "Each weekday must be an integer between 0 (Mon) and 6 (Sun)."}
                )

        if is_recurring and recurrence_type == 'monthly':
            day = data.get('recurrence_day_of_month', self.instance.recurrence_day_of_month if self.instance else None)
            if day is None or not (1 <= day <= 31):
                raise serializers.ValidationError(
                    {"recurrence_day_of_month": "Provide a valid day of month (1-31)."}
                )

        if not is_recurring:
            data['recurrence_type'] = 'none'
            data['recurrence_weekdays'] = None
            data['recurrence_day_of_month'] = None

        return data

    def update(self, instance, validated_data):
        assign_user_ids = validated_data.pop('assign_user_ids', None)

        # Never update snapshot fields
        validated_data.pop('creator_name', None)
        validated_data.pop('creator_email', None)
        validated_data.pop('creator_user_id', None)

        # Recalculate next_expected_date if recurrence settings changed
        is_recurring = validated_data.get('is_recurring', instance.is_recurring)
        recurrence_type = validated_data.get('recurrence_type', instance.recurrence_type)
        expected_date = validated_data.get('expected_date', instance.expected_date)

        if is_recurring and expected_date and recurrence_type and recurrence_type != 'none':
            from datetime import timedelta
            from dateutil.relativedelta import relativedelta

            if recurrence_type == 'daily':
                validated_data['next_expected_date'] = expected_date + timedelta(days=1)
            elif recurrence_type == 'weekly':
                validated_data['next_expected_date'] = expected_date + timedelta(days=7)
            elif recurrence_type == 'monthly':
                validated_data['next_expected_date'] = expected_date + relativedelta(months=1)
        elif not is_recurring:
            validated_data['next_expected_date'] = None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if assign_user_ids is not None:
            users = User.objects.filter(id__in=assign_user_ids)
            instance.assign_users.set(users)

        return instance