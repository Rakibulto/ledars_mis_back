from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from inventory.views import CreatedByMixin
from rest_framework.permissions import IsAuthenticated
from paginations import Pagination
from rest_framework.decorators import action
from beneficiary.models import HouseholdProfiling, CoverageArea
from beneficiary.serializers import HouseholdProfilingSerializer, CoverageAreaSerializer
from beneficiary.services import get_household_summary


class HouseholdProfilingViewSet(CreatedByMixin, ModelViewSet):

    queryset = HouseholdProfiling.objects.prefetch_related("created_by").order_by("-created_at")
    serializer_class = HouseholdProfilingSerializer
    filterset_fields = ["shelter", "block"]
    search_fields = ["household_code", "head_of_household", "location"]
    ordering_fields = ["id", "created_at"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["get"], url_path="summary")
    def household_summary(self, request):
        stats = get_household_summary()
        return Response(stats)


class CoverageAreaViewSet(CreatedByMixin, ModelViewSet):
    queryset = CoverageArea.objects.select_related("created_by").all()
    serializer_class = CoverageAreaSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    search_fields = ["division"]
    ordering_fields = ["beneficiaries", "created_at"]
    ordering = ["-beneficiaries"]
