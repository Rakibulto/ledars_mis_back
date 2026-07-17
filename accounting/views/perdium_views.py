from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from accounting.models.perdium_models import Perdium
from accounting.serializers.perdium_serializers import PerdiumSerializer


class PerdiumViewSet(viewsets.ModelViewSet):
    queryset = Perdium.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["grade", "area_type", "is_active"]
    search_fields = ["description", "grade", "area_type"]
    ordering_fields = ["grade", "area_type", "created_at", "total"]
    ordering = ["-created_at"]
    serializer_class = PerdiumSerializer

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Return only active perdium configurations."""
        active_perdiums = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(active_perdiums, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=["get"])
    def lookup(self, request):
        grade = request.query_params.get("grade")
        area_type = request.query_params.get("area_type")
        if not grade or not area_type:
            return Response({"detail": "grade and area_type are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rate = self.get_queryset().get(grade=grade, area_type=area_type, is_active=True)
        except Perdium.DoesNotExist:
            return Response({"detail": "No rate found for this grade/area."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(rate).data)