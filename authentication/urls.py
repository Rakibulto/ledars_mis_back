from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from rest_framework.routers import DefaultRouter
from django.urls import include, path, re_path
from .views import (
    CompanyInfoView,
    UserPermissionsListView,
    UserRoleListCreateAPIView,
    UserRoleRetrieveUpdateDestroyAPIView,
    UpdateUserView,
    CustomUserViewSet,
    list_all_permissions,
    set_user_permissions,
    activate_account,
    PreApprovedIpCreateView,
    PreApprovedIpListView,
    PreApprovedIpUpdateandDistroyView,
    SimpleUserViews,
    ModuleListView,
    UserModulePermissionListCreateAPIView,
    UserModulePermissionRetrieveUpdateAPIView,
    PermissionGroupListCreateAPIView,
    PermissionGroupRetrieveUpdateDestroyAPIView,
    VendorTokenObtainPairView,
)

# Create router for custom user viewset
user_router = DefaultRouter()
user_router.register(r"users", CustomUserViewSet, basename="user")


urlpatterns = [
    path("auth/", include(user_router.urls)),
    path("auth/", include("djoser.urls")),
    path("auth/", include("djoser.urls.jwt")),
    path("activate/<str:uid>/<str:token>/", activate_account, name="activate_account"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Vendor-only JWT login endpoint
    path(
        "auth/jwt/vendor-create/",
        VendorTokenObtainPairView.as_view(),
        name="vendor_token_obtain_pair",
    ),
    # Company Info API endpoint
    path("company-info/", CompanyInfoView.as_view(), name="company-info"),
    # Update user
    path("update-user/<int:pk>/", UpdateUserView.as_view(), name="update-user"),
    # User permissions management API endpoints
    path("permissions/", list_all_permissions, name="list_all_permissions"),
    path(
        "user-permissions/<int:user_id>/",
        UserPermissionsListView.as_view(),
        name="get_user_permissions",
    ),
    path(
        "set-user-permissions/<int:user_id>/",
        set_user_permissions,
        name="set_user_permissions",
    ),
    # User roles management API endpoints
    path(
        "user-roles/", UserRoleListCreateAPIView.as_view(), name="user_role_list_create"
    ),
    path(
        "user-roles/<int:pk>/",
        UserRoleRetrieveUpdateDestroyAPIView.as_view(),
        name="user_role_detail",
    ),
    path(
        "module-templates/",
        ModuleListView.as_view(),
        name="module_templates",
    ),
    path(
        "user-module-permissions/<int:user_id>/",
        UserModulePermissionListCreateAPIView.as_view(),
        name="user_module_permissions",
    ),
    path(
        "user-module-permissions/<int:user_id>/<int:pk>/",
        UserModulePermissionRetrieveUpdateAPIView.as_view(),
        name="user_module_permission_detail",
    ),
    path(
        "permission-groups/",
        PermissionGroupListCreateAPIView.as_view(),
        name="permission_group_list_create",
    ),
    path(
        "permission-groups/<int:pk>/",
        PermissionGroupRetrieveUpdateDestroyAPIView.as_view(),
        name="permission_group_detail",
    ),
    # Pre-approved IP management API endpoints
    path(
        "pre-approved-ip-list/",
        PreApprovedIpListView.as_view(),
        name="pre-approved-ip-list",
    ),
    path(
        "pre-approved-ip-create/",
        PreApprovedIpCreateView.as_view(),
        name="pre-approved-ip-create",
    ),
    path(
        "pre-approved-ip-update-and-delete/<int:pk>/",
        PreApprovedIpUpdateandDistroyView.as_view(),
        name="pre-approved-ip-update-delete",
    ),
    path("simple-user/", SimpleUserViews.as_view(), name="simple-users"),
]

# Available API endpoints from djoser:
# /auth/users/ - List all users or create new user
#   Example: GET http://localhost:8000/api/auth/users/
#
# /auth/users/me/ - Get or update authenticated user details
#   Example: GET http://localhost:8000/api/auth/users/me/
#
# /auth/users/resend_activation/ - Resend activation email
#   Example: POST http://localhost:8000/api/auth/users/resend_activation/
#
# /auth/users/set_password/ - Change user password
#   Example: POST http://localhost:8000/api/auth/users/set_password/
#
# /auth/users/reset_password/ - Request password reset email
#   Example: POST http://localhost:8000/api/auth/users/reset_password/
#
# /auth/users/reset_password_confirm/ - Confirm password reset
#   Example: POST http://localhost:8000/api/auth/users/reset_password_confirm/
#
# /auth/users/set_username/ - Change username
#   Example: POST http://localhost:8000/api/auth/users/set_username/
#
# /auth/users/reset_username/ - Request username reset
#   Example: POST http://localhost:8000/api/auth/users/reset_username/
#
# /auth/users/reset_username_confirm/ - Confirm username reset
#   Example: POST http://localhost:8000/api/auth/users/reset_username_confirm/
#
# /auth/jwt/create/ - Obtain JWT token pair
#   Example: POST http://localhost:8000/api/auth/jwt/create/
#
# /auth/jwt/refresh/ - Refresh JWT token
#   Example: POST http://localhost:8000/api/auth/jwt/refresh/
#
# /auth/jwt/verify/ - Verify JWT token
#   Example: POST http://localhost:8000/api/auth/jwt/verify/
