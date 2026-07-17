from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from rest_framework import viewsets, permissions
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from inventory.views import CreatedByMixin
from paginations import Pagination
from projects.models import Project, ProjectActivity
from projects.serializers.serializers import (
    ProjectSerializer,
    ProjectActivitySerializer,
    SimpleProjectSerializer,
)


class ProjectViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "donor", "manager", "description"]
    ordering_fields = ["name", "code", "status", "start_date", "end_date", "created_at"]
    ordering = ["-created_at"]
    filterset_fields = ["status"]

    def get_queryset(self):
        return Project.objects.all()
    

class SimpleProjectViews(generics.ListAPIView):
    queryset = Project.objects.all()
    serializer_class = SimpleProjectSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = ["name", "code"]
    ordering_fields = ["created_at", "name"]  
    ordering = ["-created_at"] 


    # ✅ Filters
    filterset_fields = [
        "name",   
        "code",     
    ]

class ProjectActivityViewSet(CreatedByMixin, viewsets.ModelViewSet):
    serializer_class = ProjectActivitySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "description"]
    ordering_fields = [
        "title",
        "start_date",
        "due_date",
        "status",
        "priority",
        "created_at",
    ]
    ordering = ["-created_at"]
    filterset_fields = ["project", "status", "priority", "type"]

    def get_queryset(self):
        return ProjectActivity.objects.select_related(
            "project", "department", "created_by"
        ).all()
