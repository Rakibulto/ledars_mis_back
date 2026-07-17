from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Todo
from .serializers import (
    TodoListSerializer,
    TodoDetailSerializer,
    TodoCreateSerializer,
    TodoUpdateSerializer,
    TodoAttachmentSerializer,
    UserMiniSerializer,
)

User = get_user_model()


def generate_recurring_todos_for_today(user):
    """
    For each recurring todo accessible by the user, auto-create an instance
    when the scheduled recurrence time arrives.

    Logic:
    - Check if today is a valid recurrence day (daily/weekly/monthly)
    - Check if next_expected_date is set and we're on or after it
    - Create instance with expected_date = next_expected_date
    - Advance next_expected_date by the recurrence interval
    """
    from datetime import timedelta
    from dateutil.relativedelta import relativedelta

    today = timezone.now().date()
    today_weekday = today.weekday()  # 0=Mon..6=Sun

    recurring_qs = Todo.objects.filter(
        is_recurring=True,
        recurrence_type__in=['daily', 'weekly', 'monthly'],
        parent_todo__isnull=True,
        status__in=['pending', 'hold'],
        next_expected_date__isnull=False,
    )

    # Only generate for todos the user can see
    if not user.is_superuser:
        recurring_qs = recurring_qs.filter(
            Q(creator=user) | Q(assign_users=user)
        ).distinct()

    for template in recurring_qs:
        # Check if today is a valid recurrence day
        is_valid_day = False
        if template.recurrence_type == 'daily':
            is_valid_day = True
        elif template.recurrence_type == 'weekly':
            if template.recurrence_weekdays and today_weekday in template.recurrence_weekdays:
                is_valid_day = True
        elif template.recurrence_type == 'monthly':
            if template.recurrence_day_of_month and today.day == template.recurrence_day_of_month:
                is_valid_day = True

        if not is_valid_day:
            continue

        # Check if we're on or after the next_expected_date
        # This prevents creating instances before the scheduled time
        if template.next_expected_date > today:
            continue

        # Calculate the expected_date for the new instance
        expected_date_for_new = template.next_expected_date

        # Idempotency: skip if an instance with this expected_date already exists
        exists = Todo.objects.filter(
            parent_todo=template,
            expected_date=expected_date_for_new,
        ).exists()
        if exists:
            continue

        # Create the instance
        new_todo = Todo.objects.create(
            todo_title=template.todo_title,
            description=template.description,
            expected_date=expected_date_for_new,
            status='pending',
            creator=template.creator,
            creator_name=template.creator_name,
            creator_email=template.creator_email,
            creator_user_id=template.creator_user_id,
            parent_todo=template,
            is_recurring=False,
            recurrence_type='none',
            recurrence_weekdays=None,
            recurrence_day_of_month=None,
        )
        new_todo.assign_users.set(template.assign_users.all())

        # Advance next_expected_date by the recurrence interval
        if template.recurrence_type == 'daily':
            template.next_expected_date = expected_date_for_new + timedelta(days=1)
        elif template.recurrence_type == 'weekly':
            template.next_expected_date = expected_date_for_new + timedelta(days=7)
        elif template.recurrence_type == 'monthly':
            template.next_expected_date = expected_date_for_new + relativedelta(months=1)
        template.save(update_fields=['next_expected_date'])


def get_todo_queryset_for_user(user):
    """
    Return the queryset of todos accessible by the given user based on access rules:
    - Superuser → ALL
    - Creator → own created (including draft)
    - Assigned user → assigned todos (excluding draft)
    - Both creator AND assigned → own created + assigned non-draft
    - Other → empty
    """
    if not user or not user.is_authenticated:
        return Todo.objects.none()

    if user.is_superuser:
        return Todo.objects.all()

    # Creator can see all their own todos including draft
    created_q = Q(creator=user)

    # Assigned users can only see non-draft todos
    assigned_q = Q(assign_users=user) & ~Q(status='draft')

    return Todo.objects.filter(created_q | assigned_q).distinct()


class TodoViewSet(ModelViewSet):
    queryset = Todo.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return TodoListSerializer
        if self.action == 'retrieve':
            return TodoDetailSerializer
        if self.action == 'create':
            return TodoCreateSerializer
        if self.action in ('update', 'partial_update'):
            return TodoUpdateSerializer
        return TodoListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        user = self.request.user

        if self.action == 'list':
            qs = get_todo_queryset_for_user(user)
            # Search
            search = self.request.query_params.get('search', '').strip()
            if search:
                qs = qs.filter(
                    Q(todo_title__icontains=search) |
                    Q(creator_name__icontains=search) |
                    Q(creator_email__icontains=search)
                )
            # Status filter
            status_filter = self.request.query_params.get('status', '').strip()
            if status_filter:
                qs = qs.filter(status=status_filter)
                
            # Role filter
            role_filter = self.request.query_params.get('role', '').strip()
            if role_filter == 'created':
                qs = qs.filter(creator=user)
            elif role_filter == 'assigned':
                qs = qs.filter(assign_users=user)

            # Month / date-range filter
            month_filter = self.request.query_params.get('month', '').strip()
            start_date = self.request.query_params.get('start_date', '').strip()
            end_date = self.request.query_params.get('end_date', '').strip()

            if month_filter:
                try:
                    year, month = month_filter.split('-')
                    qs = qs.filter(created_at__year=int(year), created_at__month=int(month))
                except (ValueError, IndexError):
                    pass
            elif start_date and end_date:
                qs = qs.filter(expected_date__gte=start_date, expected_date__lte=end_date)

            # Expected date tab filter
            date_tab = self.request.query_params.get('date_tab', '').strip()
            today = timezone.now().date()
            if date_tab == 'today':
                qs = qs.filter(expected_date=today)
            elif date_tab == 'yesterday':
                yesterday = today - timezone.timedelta(days=1)
                qs = qs.filter(expected_date=yesterday)
            elif date_tab == 'missed':
                qs = qs.filter(
                    expected_date__lt=today
                ).exclude(status__in=['completed', 'hold'])
            elif date_tab == 'tomorrow':
                tomorrow = today + timezone.timedelta(days=1)
                qs = qs.filter(expected_date=tomorrow)
            elif date_tab == 'next':
                tomorrow = today + timezone.timedelta(days=1)
                qs = qs.filter(expected_date__gt=tomorrow)

            # Ordering
            qs = qs.order_by('-created_at')
            return qs

        # For detail/edit, access control is handled in check_object_permissions
        return Todo.objects.all()

    def check_object_permissions(self, request, obj):
        """
        - Anyone can view (GET) if they have access via get_todo_queryset_for_user
        - Creator or superuser can edit/delete anything
        - Assigned user can only PATCH (update status) — cannot PUT or DELETE
        """
        super().check_object_permissions(request, obj)

        if request.method == 'DELETE':
            if not (request.user.is_superuser or obj.creator == request.user):
                self.permission_denied(
                    request,
                    message="You do not have permission to delete this todo.",
                    code='permission_denied'
                )

        if request.method == 'PUT':
            if not (request.user.is_superuser or obj.creator == request.user):
                self.permission_denied(
                    request,
                    message="You do not have permission to edit this todo.",
                    code='permission_denied'
                )

        # PATCH is allowed for both creator and assigned users (for status updates)
        # Full edit (PUT) is restricted to creator/superuser only

    def list(self, request, *args, **kwargs):
        user = request.user
        # Auto-generate recurring todos for today before listing
        generate_recurring_todos_for_today(user)

        base_qs = get_todo_queryset_for_user(user)

        if not base_qs.exists():
            return Response({
                'count': 0,
                'next': None,
                'previous': None,
                'results': [],
                'message': 'You are not eligible to view any list.',
                'total_pages': 0,
                'current_page': 1,
                'page_size': int(request.query_params.get('page_size', 10)),
            })

        queryset = self.filter_queryset(self.get_queryset())

        # Pagination
        page_size = int(request.query_params.get('page_size', 10))
        page = int(request.query_params.get('page', 1))
        total = queryset.count()
        total_pages = max(1, -(-total // page_size))  # ceiling division
        start = (page - 1) * page_size
        end = start + page_size
        page_queryset = queryset[start:end]

        serializer = self.get_serializer(page_queryset, many=True)
        return Response({
            'count': total,
            'next': f'?page={page + 1}&page_size={page_size}' if page < total_pages else None,
            'previous': f'?page={page - 1}&page_size={page_size}' if page > 1 else None,
            'results': serializer.data,
            'total_pages': total_pages,
            'current_page': page,
            'page_size': page_size,
        })

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """Return role-filtered summary counts."""
        user = request.user
        generate_recurring_todos_for_today(user)
        qs = get_todo_queryset_for_user(user)

        today = timezone.now().date()
        yesterday = today - timezone.timedelta(days=1)
        tomorrow = today + timezone.timedelta(days=1)

        return Response({
            'total': qs.count(),
            'draft': qs.filter(status='draft').count(),
            'pending': qs.filter(status='pending').count(),
            'hold': qs.filter(status='hold').count(),
            'completed': qs.filter(status='completed').count(),
            'today': qs.filter(expected_date=today).count(),
            'yesterday': qs.filter(expected_date=yesterday).count(),
            'missed': qs.filter(expected_date__lt=today).exclude(status__in=['completed', 'hold']).count(),
            'tomorrow': qs.filter(expected_date=tomorrow).count(),
            'next': qs.filter(expected_date__gt=tomorrow).count(),
        })

    @action(detail=False, methods=['get'], url_path='users')
    def users_list(self, request):
        """Return all users for assign_users dropdown (searchable)."""
        search = request.query_params.get('search', '').strip()
        users = User.objects.filter(is_active=True)
        if search:
            users = users.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search)
            )
        users = users.order_by('username')[:50]
        serializer = UserMiniSerializer(users, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'post'], url_path='attachments',
            permission_classes=[IsAuthenticated])
    def attachments(self, request, pk=None):
        todo = self.get_object()

        # Mirror the existing accessibility rule (creator, assigned user, or superuser)
        # for both read and write
        if todo not in get_todo_queryset_for_user(request.user):
            self.permission_denied(request, message="You do not have access to this todo.")

        if request.method == 'GET':
            qs = todo.attachments.all()
            user_id = request.query_params.get('user_id')
            if user_id:
                qs = qs.filter(user_id=user_id)

            page_size = int(request.query_params.get('page_size', 10))
            page = int(request.query_params.get('page', 1))
            total = qs.count()
            total_pages = max(1, -(-total // page_size))
            start = (page - 1) * page_size
            serializer = TodoAttachmentSerializer(
                qs[start:start + page_size], many=True, context={'request': request}
            )
            return Response({
                'count': total,
                'total_pages': total_pages,
                'current_page': page,
                'page_size': page_size,
                'results': serializer.data,
            })

        # POST — only ever creates an entry for the logged-in user
        serializer = TodoAttachmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(todo=todo, user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'put', 'patch', 'delete'], url_path='attachments/(?P<attachment_id>[^/.]+)',
            permission_classes=[IsAuthenticated])
    def attachment_detail(self, request, pk=None, attachment_id=None):
        """Retrieve, update or delete a specific attachment.

        Permission logic:
        - Anyone with access to the parent Todo can GET (view) attachments.
        - Only the attachment owner (attachment.user) or superuser can PUT/PATCH/DELETE.
        - We bypass check_object_permissions here because it enforces Todo-level
          restrictions (only Todo creator can PUT/DELETE) which would incorrectly
          block assigned users from editing their own attachments.
        """
        # Fetch todo directly to avoid check_object_permissions (which blocks
        # non-creator PUT/DELETE at the Todo level)
        try:
            todo = Todo.objects.get(pk=pk)
        except Todo.DoesNotExist:
            return Response({'detail': 'Todo not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Still verify the user has access to the parent todo
        if todo not in get_todo_queryset_for_user(request.user):
            self.permission_denied(request, message="You do not have access to this todo.")

        attachment = todo.attachments.filter(id=attachment_id).first()
        if not attachment:
            return Response({'detail': 'Attachment not found.'}, status=status.HTTP_404_NOT_FOUND)

        # GET — anyone with todo access can view
        if request.method == 'GET':
            serializer = TodoAttachmentSerializer(attachment, context={'request': request})
            return Response(serializer.data)

        # PUT/PATCH/DELETE — only the attachment owner or superuser
        if not (request.user.is_superuser or attachment.user == request.user):
            self.permission_denied(
                request,
                message="You do not have permission to modify this attachment.",
                code='permission_denied'
            )

        if request.method in ('PUT', 'PATCH'):
            serializer = TodoAttachmentSerializer(
                attachment, data=request.data, context={'request': request},
                partial=(request.method == 'PATCH')
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        if request.method == 'DELETE':
            attachment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
