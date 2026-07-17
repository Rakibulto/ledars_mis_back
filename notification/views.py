from attendance.pagination import StandardResultsSetPagination
from .models import Notification
from .serializers import NofificationSerializer
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

class NotificationList(generics.ListAPIView):
    """
    APIView: NotificationList
    ListAPIView that returns Notification objects ordered by newest first.
    Behavior:
    
    - Returns a paginated JSON list of Notification instances, ordered by `created_at` descending.
    - Requires authentication (IsAuthenticated).
    - Uses `NofificationSerializer` to serialize notification objects and `StandardResultsSetPagination` for paging.
    Supported filtering
    - Built-in field filters via DjangoFilterBackend:
        - receiver: filter by the notification receiver (e.g., ?receiver=<id_or_value>)
        - employee: filter by associated employee (e.g., ?employee=<id_or_value>)
        - type: filter by notification type (e.g., ?type=<type_name>)
    - Additional query-parameter filters applied in get_queryset (case-insensitive):
        - read: filters notifications where `status` matches the provided value (e.g., ?read=read)
        - unread: same as `read` but using the `unread` query param (e.g., ?unread=unread)
        - leave: filters where `type` matches the provided value (e.g., ?leave=leave)
        - attendance: filters where `type` matches the provided value (e.g., ?attendance=attendance)
        - attendance_adjustment: filters where `type` matches the provided value
        - probation_period: filters where `type` matches the provided value
    Notes and caveats
    - All custom query-parameter filters use case-insensitive exact matching (field__iexact=<value>).
    - Supplying multiple custom type filters (e.g., ?leave=leave&attendance=attendance) will apply them cumulatively (logical AND), which may result in an empty queryset unless a notification matches all provided constraints.
    - Query parameters are optional; omitting them returns all notifications (still ordered and paginated).
    """
    serializer_class = NofificationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['receiver', 'employee', 'type']
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = Notification.objects.all().order_by('-created_at')
        # Filter by read/unread status
        read = self.request.query_params.get('read', None)
        unread = self.request.query_params.get('unread', None)
        if read is not None:
            queryset = queryset.filter(status__iexact=read)
        if unread is not None:
            queryset = queryset.filter(status__iexact=unread)

        # Filter by notification type
        leave = self.request.query_params.get('leave', None)
        attendance = self.request.query_params.get('attendance', None)
        attendance_adjustment = self.request.query_params.get('attendance_adjustment', None)
        probation_period = self.request.query_params.get('probation_period', None)
        
        if leave is not None:
            queryset = queryset.filter(type__iexact=leave)
        if attendance is not None:
            queryset = queryset.filter(type__iexact=attendance)
        if attendance_adjustment is not None:
            queryset = queryset.filter(type__iexact=attendance_adjustment)
        if probation_period is not None:
            queryset = queryset.filter(type__iexact=probation_period)
            
        return queryset
    
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Add unread notification count for the current user
        
        if request.user.role.name == 'Admin':
            unread_count = Notification.objects.filter(
                status='Unread'
            ).count()
        else:
            unread_count = Notification.objects.filter(
                receiver=request.user,
                status='Unread'
            ).count()
        
        # Handle both paginated and non-paginated responses
        if isinstance(response.data, list):
            response.data = {
                'results': response.data,
                'unread_count': unread_count
            }
        else:
            response.data['unread_count'] = unread_count
        
        return response
    
class NotificationDetails(generics.RetrieveUpdateDestroyAPIView):
    queryset = Notification.objects.all().order_by('-created_at') 
    serializer_class = NofificationSerializer
    lookup_field = 'pk'
    permission_classes = [IsAuthenticated]
    
    
class MarkAllNotificationsReadView(APIView):
    """
    APIView: MarkAllNotificationsReadView
    APIView that marks all notifications for the authenticated user as 'Read'.
    Behavior:
    
    - Updates all Notification instances where `receiver` is the authenticated user, setting `status` to 'Read'.
    - Requires authentication (IsAuthenticated).
    - Returns a success message upon completion.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role.name == 'Admin':
            Notification.objects.filter(status='Unread').update(status='Read')
        else:
            Notification.objects.filter(receiver=user, status='Unread').update(status='Read')

        return Response({"detail": "All notifications marked as read."}, status=status.HTTP_200_OK)

