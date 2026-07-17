from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAdminUser
from django.core.exceptions import PermissionDenied
from .serializers import ShiftSerializer
from .models import Shift
import re


class ShiftViewSet(generics.ListAPIView):
    serializer_class = ShiftSerializer

    def get_queryset(self):
        queryset = Shift.objects.all()
        # Sort by shift type first, then by number within each type
        def sort_key(shift):
            # Extract the shift type and number from the name
            # Examples: "Full Time Shift 10" -> ("Full Time Shift", 10)
            # "Primary Part-time DS 1" -> ("Primary Part-time DS", 1)
            match = re.match(r'(.+?)\s+(\d+)$', shift.name.strip())
            if match:
                shift_type = match.group(1).strip()
                shift_number = int(match.group(2))
                return (shift_type, shift_number)
            else:
                # Fallback for shifts without numbers
                return (shift.name, 0)

        # Convert to list and sort
        shifts_list = list(queryset)
        shifts_list.sort(key=sort_key)
        return shifts_list

# Retrieve a single shift
class ShiftDetailView(generics.RetrieveAPIView):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer
    lookup_field = 'id'

# create shift
class ShiftCreateView(generics.ListCreateAPIView):
    serializer_class = ShiftSerializer
    lookup_field = 'id'

    def get_queryset(self):
        queryset = Shift.objects.all()
        # Sort by shift type first, then by number within each type
        def sort_key(shift):
            # Extract the shift type and number from the name
            # Examples: "Full Time Shift 10" -> ("Full Time Shift", 10)
            # "Primary Part-time DS 1" -> ("Primary Part-time DS", 1)
            match = re.match(r'(.+?)\s+(\d+)$', shift.name.strip())
            if match:
                shift_type = match.group(1).strip()
                shift_number = int(match.group(2))
                return (shift_type, shift_number)
            else:
                # Fallback for shifts without numbers
                return (shift.name, 0)

        # Convert to list and sort
        shifts_list = list(queryset)
        shifts_list.sort(key=sort_key)
        return shifts_list

    def post(self, request, *args, **kwargs):
        if not request.user and request.user.has_perm('shift.add_shift'):
            raise PermissionDenied("You do not have permission to perform this action.")
        return self.create(request, *args, **kwargs)

# update/delete shift
class ShiftUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer
    lookup_field = 'id'
    permission_classes=[IsAdminUser]

    def put(self, request, *args, **kwargs):
        if not request.user or not request.user.has_perm('shift.change_shift'):
            raise PermissionDenied("You do not have permission to perform this action.")
        
        return self.update(request, *args, **kwargs)
    
    def delete(self, request, *args, **kwargs):
        if not request.user or not request.user.has_perm('shift.delete_shift'):
            raise PermissionDenied("You do not have permission to perform this action.")
        
        return self.destroy(request, *args, **kwargs)