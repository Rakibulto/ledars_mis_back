from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import PermissionDenied
from .models import Holiday
from .serializers import HolidaySerializer

# Create your views here.

class HolidayViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Holiday model providing CRUD operations using Model Viewset.
    Supports listing, retrieving, creating, updating, and deleting holidays.
    """
    queryset = Holiday.objects.all().order_by('-created_at')
    serializer_class = HolidaySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Optionally filter holidays by date range or name for authenticated users.
        """
        queryset = super().get_queryset()
        # Example filters (can be extended based on requirements)
        name = self.request.query_params.get('name', None)
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)

        if name:
            queryset = queryset.filter(name__icontains=name)
        if start_date:
            queryset = queryset.filter(from_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(to_date__lte=end_date)

        return queryset

    def perform_create(self, serializer):
        """
        Set the creator of the holiday and save the instance.
        Checks if the user has permission to add a holiday.
        """
        user = self.request.user
        if not user.has_perm('holiday.add_holiday'):
            raise PermissionDenied("You do not have permission to perform this action.")
        serializer.save()

    def perform_update(self, serializer):
        """
        Handle updates to the holiday instance.
        """
        user = self.request.user
        if not user.has_perm('holiday.change_holiday'):
            raise PermissionDenied("You do not have permission to perform this action.")
        serializer.save()
        

        