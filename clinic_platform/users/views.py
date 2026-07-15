"""This module contains views related to user accounts, including registration,
login, logout, email verification, password reset, and admin user management.
"""

from typing import Any

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import update_last_login
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers

from .models import User
from .serializers import (
    UserRegistrationSerializer,
    UserDetailSerializer,
    PasswordResetConfirmSerializer,
)


class SwaggerLoginView(APIView):
    """Login endpoint for Swagger UI and token-based authentication."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Authentication'],
        summary='Login with username or email',
        description=(
            'Use username or email together with password to obtain a JWT access token. '
            'Swagger UI can use this endpoint to authenticate and send Authorization headers.'
        ),
        request=inline_serializer(
            name='SwaggerLoginRequest',
            fields={
                'username': drf_serializers.CharField(required=False, allow_blank=True),
                'email': drf_serializers.EmailField(required=False, allow_blank=True),
                'password': drf_serializers.CharField(),
                'grant_type': drf_serializers.CharField(
                    required=False,
                    default='password',
                    help_text='Auto-filled by Swagger UI — leave as "password".',
                ),
            },
        ),
        responses={
            200: inline_serializer(
                name='SwaggerLoginResponse',
                fields={
                    'access_token': drf_serializers.CharField(),
                    'token_type': drf_serializers.CharField(),
                    'refresh_token': drf_serializers.CharField(),
                    'role': drf_serializers.CharField(),
                },
            ),
            401: OpenApiResponse(description='Invalid credentials'),
            403: OpenApiResponse(description='Account inactive'),
        },
        auth=[],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Authenticate using username/email and return JWT credentials.

        Args:
            request: Incoming login request payload.
            *args: Positional view arguments.
            **kwargs: Keyword view arguments.

        Returns:
            Response: JWT token payload or error detail.
        """
        identifier = request.data.get('username') or request.data.get('email')
        password = request.data.get('password')

        if not identifier or not password:
            return Response(
                {'detail': 'Username or email and password are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = None
        if '@' in identifier:
            candidate = User.objects.filter(email__iexact=identifier).first()
            if not candidate:
                return Response(
                    {'detail': 'Invalid credentials.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            username = candidate.username
        else:
            username = identifier

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {'detail': 'Invalid credentials.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {'detail': 'Account is inactive.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        update_last_login(None, user)
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'access_token': str(refresh.access_token),
                'token_type': 'bearer',
                'refresh_token': str(refresh),
                'role': user.role,
            },
            status=status.HTTP_200_OK,
        )


class TokenRefreshAPIView(TokenRefreshView):
    """Refresh JWT access tokens."""
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Authentication'],
        summary='Refresh JWT access token',
        request=inline_serializer(
            name='TokenRefreshRequest',
            fields={
                'refresh': drf_serializers.CharField(),
            },
        ),
        responses={
            200: inline_serializer(
                name='TokenRefreshResponse',
                fields={
                    'access': drf_serializers.CharField(),
                    'refresh': drf_serializers.CharField(),
                },
            ),
            400: OpenApiResponse(description='Invalid refresh token'),
        },
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Refresh access token using refresh token payload.

        Args:
            request: Incoming refresh request.
            *args: Positional view arguments.
            **kwargs: Keyword view arguments.

        Returns:
            Response: New access token payload.
        """
        return super().post(request, *args, **kwargs)


class TokenRevokeView(APIView):
    """Revoke a refresh token by blacklisting it."""
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Authentication'],
        summary='Revoke JWT refresh token',
        request=inline_serializer(
            name='TokenRevokeRequest',
            fields={'refresh': drf_serializers.CharField()},
        ),
        responses={
            200: OpenApiResponse(description='Refresh token revoked'),
            400: OpenApiResponse(description='Invalid token'),
        },
    )
    def post(self, request: Request) -> Response:
        """Revoke a refresh token by adding it to blacklist.

        Args:
            request: Incoming token revoke request.

        Returns:
            Response: Success or failure detail.
        """
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {'detail': 'Invalid or expired refresh token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({'detail': 'Refresh token revoked.'}, status=status.HTTP_200_OK)


class UserRegistrationView(generics.CreateAPIView):
    """Register a new user account."""
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]


class UserDetailView(generics.RetrieveUpdateAPIView):
    """Get or update the currently authenticated user's profile."""
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self) -> User:
        """Return the currently authenticated user instance.

        Returns:
            User: Authenticated request user.
        """
        return self.request.user


class UserLoginView(APIView):
    """Authenticate a user and start a new session."""
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Authentication'],
        summary='Login using username or email',
        request=inline_serializer(
            name='UserLoginRequest',
            fields={
                'username': drf_serializers.CharField(required=False, allow_blank=True),
                'email': drf_serializers.EmailField(required=False, allow_blank=True),
                'password': drf_serializers.CharField(),
            },
        ),
        responses={
            200: inline_serializer(
                name='UserLoginResponse',
                fields={
                    'user_id': drf_serializers.CharField(),
                    'username': drf_serializers.CharField(),
                    'email': drf_serializers.EmailField(),
                    'role': drf_serializers.CharField(),
                },
            ),
            400: OpenApiResponse(description='Missing credentials'),
            401: OpenApiResponse(description='Invalid credentials'),
        },
    )
    def post(self, request: Request) -> Response:
        """Authenticate a user and return profile payload.

        Args:
            request: Incoming login request payload.

        Returns:
            Response: Authenticated user details or error payload.
        """
        identifier = request.data.get('username') or request.data.get('email')
        password = request.data.get('password')

        if not identifier or not password:
            return Response(
                {'detail': 'Username or email and password are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = None
        if '@' in identifier:
            candidate = User.objects.filter(email__iexact=identifier).first()
            if not candidate:
                return Response(
                    {'detail': 'Unable to log in with provided credentials.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            username = candidate.username
        else:
            username = identifier

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {'detail': 'Unable to log in with provided credentials.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        serializer = UserDetailSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserLogoutView(APIView):
    """Logout the currently authenticated user."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Logout current user session.

        Args:
            request: Authenticated logout request.

        Returns:
            Response: Logout confirmation.
        """
        logout(request)
        return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)


class AdminUserListView(generics.ListAPIView):
    """List all users for admin users."""
    queryset = User.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAdminUser]


class AdminUserDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a user by user_id for admin users."""
    queryset = User.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = 'user_id'


class PasswordResetRequestView(APIView):
    """Start the password reset flow by sending an email token."""
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Authentication'],
        summary='Request a password reset email',
        request=inline_serializer(
            name='PasswordResetRequest',
            fields={
                'email': drf_serializers.EmailField(),
            },
        ),
        responses={
            200: OpenApiResponse(description='Password reset email sent'),
            400: OpenApiResponse(description='Email is required'),
        },
    )
    def post(self, request: Request) -> Response:
        """Generate and send password reset token email.

        Args:
            request: Incoming password reset request.

        Returns:
            Response: Generic reset-request acknowledgement.
        """
        email = request.data.get('email')
        if not email:
            return Response(
                {'detail': 'Email is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email__iexact=email).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            subject = 'Password reset request'
            message = (
                f'Use the token below to reset your password:\n\n{token}\n\n'
                f'Your uid is {uid}. Use both values with the password reset confirm endpoint.'
            )
            send_mail(subject, message, None, [email], fail_silently=True)

        return Response(
            {'detail': 'If that email is registered, a password reset link has been sent.'},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """Confirm a password reset with uid and token."""
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(
        tags=['Authentication'],
        summary='Confirm password reset',
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(description='Password reset successfully'),
            400: OpenApiResponse(description='Invalid token or UID'),
        },
    )
    def post(self, request: Request) -> Response:
        """Validate reset token and set a new password.

        Args:
            request: Incoming reset confirmation payload.

        Returns:
            Response: Success or failure detail.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        uid = serializer.validated_data['uid']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            uid = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'detail': 'Invalid reset link.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'detail': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Password has been reset successfully.'}, status=status.HTTP_200_OK)
