from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from inventory.views import CreatedByMixin
from rest_framework.permissions import IsAuthenticated
from paginations import Pagination
from rest_framework.decorators import action
from beneficiary.models import Referral, ReferralNetworkPartner
from beneficiary.serializers import ReferralSerializer, ReferralNetworkPartnerSerializer
from beneficiary.services import get_referral_summary


class ReferralViewSet(CreatedByMixin, ModelViewSet):

    queryset = Referral.objects.prefetch_related("beneficiary", "created_by").order_by("-created_at")
    serializer_class = ReferralSerializer
    search_fields = ["referral_code", "beneficiary__name", "referred_to", "service"]
    filterset_fields = ["status", "priority"]
    ordering_fields = ["id", "created_at"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["get"], url_path="summary")
    def referral_summary(self, request):
        stats = get_referral_summary()
        return Response(stats)


class ReferralNetworkPartnerViewSet(CreatedByMixin, ModelViewSet):
    queryset = ReferralNetworkPartner.objects.select_related("created_by").all()
    serializer_class = ReferralNetworkPartnerSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["status", "type"]
    search_fields = ["organization", "coverage", "contact"]
    ordering_fields = ["referrals_made", "created_at"]
    ordering = ["-created_at"]
