"""URL routes for user authentication and account management."""

from django.urls import path
from .views import (
    AdminUserDetailView,
    AdminUserListView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    SwaggerLoginView,
    TokenRefreshAPIView,
    TokenRevokeView,
    UserDetailView,
    UserLoginView,
    UserLogoutView,
    UserRegistrationView,
)

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path('login/', UserLoginView.as_view(), name='user-login'),
    path('swagger-login/', SwaggerLoginView.as_view(), name='swagger-login'),
    path('logout/', UserLogoutView.as_view(), name='user-logout'),
    path('me/', UserDetailView.as_view(), name='user-detail'),
    path('token/refresh/', TokenRefreshAPIView.as_view(), name='token-refresh'),
    path('token/revoke/', TokenRevokeView.as_view(), name='token-revoke'),
    path('admin/users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/users/<uuid:user_id>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]
