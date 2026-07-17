from django.urls import path
from .views import (
    CDataView,
    DeviceCmdView,
    GetRequestView,
)

urlpatterns = [
    # ZKTeco ADMS endpoints (called by device firmware - paths are fixed)
    path("iclock/cdata", CDataView.as_view(), name="cdata"),
    path("iclock/getrequest", GetRequestView.as_view(), name="getrequest"),
    path("iclock/devicecmd", DeviceCmdView.as_view(), name="devicecmd"),
]
