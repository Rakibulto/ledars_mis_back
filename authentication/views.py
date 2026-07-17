from re import I
from paginations import Pagination
from django.db.models import Q
from django.shortcuts import render
from .models import CompanyInfo, User, PreApprovedIP, Role, Module, ModulePermission, PermissionGroup
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.decorators import APIView, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import VendorTokenObtainPairSerializer
from django.contrib.auth.models import Permission
from .serializers import (
    CompanyInfoSerializer,
    PermissionSerializer,
    PreApprovedIPSerializer,
    UserRoleSerializer,
    UserSerializer,
    SimpleUserSerializer,
    ModuleSerializer,
    ModulePermissionSerializer,
    PermissionGroupSerializer,
)
import requests
from django.http import HttpResponse, Http404
from django.contrib.sites.shortcuts import get_current_site
from djoser.views import UserViewSet as DjoserUserViewSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.permissions import IsAuthenticated, AllowAny


# Dynamic Company Name Name and Logo View
class CompanyInfoView(generics.RetrieveAPIView):
    queryset = CompanyInfo.objects.all()
    serializer_class = CompanyInfoSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        obj = CompanyInfo.objects.first()
        if obj is None:
            obj = CompanyInfo.objects.create()  # Create default empty company info
        return obj


# Custom User Views
class UpdateUserView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_all_permissions(request):
    permissions = Permission.objects.all().values(
        "id", "name", "codename", "content_type__model", "content_type__app_label"
    )
    return Response(list(permissions))


class UserPermissionsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            permissions = user.user_permissions.all() | Permission.objects.filter(
                group__user=user
            )
            permissions = permissions.distinct()
            serializer = PermissionSerializer(permissions, many=True)

            return Response(serializer.data, status=200)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_user_permissions(request, user_id):
    user = User.objects.get(id=user_id)
    permission_ids = request.data.get("permission_ids", [])
    # Set the permissions
    user.user_permissions.set(Permission.objects.filter(id__in=permission_ids))
    user.save()

    return Response(
        {
            "status": "Permissions updated successfully",
            "permissions": user.get_all_permissions(),
        }
    )


# Activate user account using uid and token
def activate_account(request, uid, token):
    domain = f"{request.scheme}://{request.get_host()}"
    activation_url = f"{domain}/api/auth/users/activation/"
    data = {"uid": uid, "token": token}
    current_site = get_current_site(request)
    site_name = current_site.name

    try:
        response = requests.post(activation_url, json=data)
        if response.status_code == 204:
            # Activation successful - render success page
            return render(
                request,
                "email/activation_success.html",
                {
                    "site_name": site_name,
                    "domain": request.get_host(),
                },
            )
        else:
            # Activation failed - render failure page
            return render(
                request,
                "email/activation_failed.html",
                {
                    "site_name": site_name,
                    "domain": request.get_host(),
                    "error_code": response.status_code,
                },
            )
    except requests.exceptions.RequestException as e:
        return HttpResponse(
            f"Activation failed: {response}", status=response.status_code
        )


# PreApproved IP List View
class PreApprovedIpListView(generics.ListAPIView):
    queryset = PreApprovedIP.objects.all()
    serializer_class = PreApprovedIPSerializer
    permission_classes = [IsAdminUser]


# PreApproved IP Create View
class PreApprovedIpCreateView(generics.ListCreateAPIView):
    queryset = PreApprovedIP.objects.all()
    serializer_class = PreApprovedIPSerializer
    permission_classes = [IsAdminUser]


# PreApproved IP update & delete View
class PreApprovedIpUpdateandDistroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PreApprovedIP.objects.all()
    serializer_class = PreApprovedIPSerializer
    permission_classes = [IsAdminUser]


## Viewset for User Role management
class UserRoleListCreateAPIView(generics.ListCreateAPIView):
    """
    Viewset for listing and creating user roles.
    """

    queryset = Role.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsAuthenticated]  # Only allow admin users to access this view

    def has_admin_role(self, user):
        return hasattr(user, "role") and user.role and user.role.name == "Admin"

    def create(self, request, *args, **kwargs):
        if not self.has_admin_role(request.user):
            raise PermissionDenied("Only admins can create user roles.")
        return super().create(request, *args, **kwargs)


class UserRoleRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Viewset for retrieving, updating, and deleting a specific user role.
    """

    queryset = Role.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsAuthenticated]  # Only allow admin users to access this view

    def has_admin_role(self, user):
        return hasattr(user, "role") and user.role and user.role.name == "Admin"

    def get_object(self):
        if not self.has_admin_role(self.request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().get_object()


class ModuleListView(generics.ListAPIView):
    """List available frontend modules for assignment."""

    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [IsAuthenticated]


class UserModulePermissionListCreateAPIView(APIView):
    """List and update module permissions for a specific user."""

    permission_classes = [IsAuthenticated]

    def has_admin_role(self, user):
        return hasattr(user, "role") and user.role and user.role.name == "Admin"

    def get(self, request, user_id):
        if request.user.id != int(user_id) and not self.has_admin_role(request.user):
            raise PermissionDenied(
                "You do not have permission to view this user's module permissions."
            )

        module_permissions = ModulePermission.objects.filter(
            user_id=user_id
        ).select_related("module")
        serializer = ModulePermissionSerializer(module_permissions, many=True)
        return Response(serializer.data)

    def post(self, request, user_id):
        if request.user.id != int(user_id) and not self.has_admin_role(request.user):
            raise PermissionDenied(
                "You do not have permission to update this user's module permissions."
            )

        user = User.objects.get(id=user_id)
        payload = request.data.get("module_permissions", [])

        if not isinstance(payload, list):
            return Response({"error": "module_permissions must be a list."}, status=400)

        updated_permissions = []
        for item in payload:
            module_id = item.get("module")
            if not module_id:
                continue

            module = Module.objects.filter(id=module_id).first()
            if not module:
                continue

            module_permission, _ = ModulePermission.objects.get_or_create(
                user=user,
                module=module,
            )
            module_permission.can_create = bool(
                item.get("can_create", module_permission.can_create)
            )
            module_permission.can_update = bool(
                item.get("can_update", module_permission.can_update)
            )
            module_permission.can_delete = bool(
                item.get("can_delete", module_permission.can_delete)
            )
            module_permission.can_add = bool(
                item.get("can_add", module_permission.can_add)
            )
            module_permission.can_view = bool(
                item.get("can_view", module_permission.can_view)
            )
            module_permission.save()
            updated_permissions.append(module_permission)

        serializer = ModulePermissionSerializer(updated_permissions, many=True)
        return Response({"module_permissions": serializer.data}, status=200)


class UserModulePermissionRetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a single user module permission record."""

    queryset = ModulePermission.objects.all()
    serializer_class = ModulePermissionSerializer
    permission_classes = [IsAuthenticated]

    def has_admin_role(self, user):
        return hasattr(user, "role") and user.role and user.role.name == "Admin"

    def get_object(self):
        obj = super().get_object()
        if self.request.user.id != obj.user_id and not self.has_admin_role(
            self.request.user
        ):
            raise PermissionDenied(
                "You do not have permission to access this module permission."
            )
        return obj


class CustomUserViewSet(DjoserUserViewSet):
    """
    Custom User ViewSet extending Djoser's UserViewSet with filtering capabilities.
    """

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "is_staff"]
    search_fields = ["username", "email", "role__name"]
    ordering_fields = ["created_at", "updated_at", "username", "email"]
    ordering = ["-created_at"]
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        role_names = self.request.query_params.getlist("role")
        if role_names:
            # Create Q objects for case-insensitive role name matching
            role_queries = Q()
            for role_name in role_names:
                role_queries |= Q(role__name__iexact=role_name)
            queryset = queryset.filter(role_queries)
        return queryset


class SimpleUserViews(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = SimpleUserSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = ["username"]
    ordering_fields = ["created_at", "username"]
    ordering = ["-created_at"]

    # ✅ Filters
    filterset_fields = [
        "username",
    ]


def _is_superuser_only(user):
    return bool(user and user.is_superuser)


class PermissionGroupListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = PermissionGroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = PermissionGroup.objects.prefetch_related(
            "permissions__content_type"
        ).all()
        module_key = self.request.query_params.get("module_key")
        if module_key:
            queryset = queryset.filter(
                permissions__content_type__app_label=module_key
            ).distinct()
        return queryset

    def list(self, request, *args, **kwargs):
        if not _is_superuser_only(request.user):
            raise PermissionDenied("Only superusers can manage permission groups.")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not _is_superuser_only(request.user):
            raise PermissionDenied("Only superusers can manage permission groups.")
        return super().create(request, *args, **kwargs)


class PermissionGroupRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PermissionGroup.objects.prefetch_related("permissions__content_type").all()
    serializer_class = PermissionGroupSerializer
    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        if not _is_superuser_only(request.user):
            raise PermissionDenied("Only superusers can manage permission groups.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not _is_superuser_only(request.user):
            raise PermissionDenied("Only superusers can manage permission groups.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not _is_superuser_only(request.user):
            raise PermissionDenied("Only superusers can manage permission groups.")
        return super().destroy(request, *args, **kwargs)


class VendorTokenObtainPairView(TokenObtainPairView):
    """
    POST api/auth/jwt/vendor-create/
    Returns JWT access + refresh tokens only for users whose role is 'Vendor'.
    Any other role receives 401 Unauthorized.
    """

    serializer_class = VendorTokenObtainPairSerializer
