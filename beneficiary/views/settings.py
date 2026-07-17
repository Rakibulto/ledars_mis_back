from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from inventory.views import CreatedByMixin
from paginations import Pagination
from beneficiary.models import BeneficiarySetting
from beneficiary.serializers import BeneficiarySettingSerializer


class BeneficiarySettingViewSet(CreatedByMixin, ModelViewSet):
    queryset = BeneficiarySetting.objects.select_related("created_by").all()
    serializer_class = BeneficiarySettingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filterset_fields = ["category"]
    search_fields = ["setting", "value"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
