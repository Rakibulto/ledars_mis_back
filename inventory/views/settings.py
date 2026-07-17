from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny
from paginations import Pagination
from inventory.models import InventorySettings
from inventory.serializers import InventorySettingsSerializer


class InventorySettingsViewSet(ModelViewSet):
    queryset = InventorySettings.objects.all()
    serializer_class = InventorySettingsSerializer
    permission_classes = [AllowAny]
    pagination_class = Pagination
