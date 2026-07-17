

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShiftViewSet, ShiftDetailView, ShiftCreateView, ShiftUpdateDeleteView

urlpatterns = [
    path('shifts/create', ShiftCreateView.as_view(), name='shift-create'),
    path('shifts/', ShiftViewSet.as_view(), name='shift-list'),
    # path('shifts/<int:id>/', ShiftDetailView.as_view(), name='shift-detail'),
    path('shifts/<int:id>/', ShiftUpdateDeleteView.as_view(), name='shift-update-or-delete'),
]
