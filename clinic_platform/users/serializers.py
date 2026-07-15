"""Models serializers for the users app.
   Including user registration, email verification and password reset serializers.
"""

from typing import Any

from rest_framework import serializers
from .models import User
from django.contrib.auth.password_validation import (
    validate_password,
    UserAttributeSimilarityValidator,
    MinimumLengthValidator,
    CommonPasswordValidator,
)


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the user model, used for registration and user details.
    """
    full_name = serializers.SerializerMethodField(read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password2 = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            'user_id',
            'first_name',
            'last_name',
            'full_name',
            'username',
            'email',
            'phone_number',
            'role',
            'password',
            'password2',
        )
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'username': {'required': True},
            'email': {'required': True},
            'phone_number': {'required': True},
            'role': {'required': True},
        }
        read_only_fields = ('user_id',)

    def get_full_name(self, obj: User) -> str:
        """Build a full name string for the user.

        Args:
            obj: User model instance.

        Returns:
            str: Combined first and last name.
        """
        return f"{obj.first_name} {obj.last_name}"

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate cross-field registration constraints.

        Args:
            attrs: Candidate serializer attributes.

        Returns:
            dict[str, Any]: Validated attributes.
        """
        password = attrs.get('password')
        password2 = attrs.get('password2')

        if self.instance is None:
            if not password or not password2:
                raise serializers.ValidationError({"password": "Password is required when registering."})

        if password or password2:
            if password != password2:
                raise serializers.ValidationError({"password": "Password fields didn't match."})

        return attrs

    def create(self, validated_data: dict[str, Any]) -> User:
        """Create a user instance with optional password.

        Args:
            validated_data: Validated serializer data.

        Returns:
            User: Newly created user instance.
        """
        validated_data.pop('password2', None)
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def validate_username(self, value: str) -> str:
        """Validate username uniqueness and naming format.

        Args:
            value: Proposed username.

        Returns:
            str: Validated username.
        """
        if User.objects.filter(username=value).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        if not value[0].isalpha():
            raise serializers.ValidationError("Username must start with a letter.")
        return value

    def validate_email(self, value: str) -> str:
        """Validate email format and uniqueness.

        Args:
            value: Proposed email address.

        Returns:
            str: Validated email address.
        """
        if not value:
            raise serializers.ValidationError("Email cannot be empty.")
        if '@' not in value:
            raise serializers.ValidationError("Enter a valid email address.")
        local, _, domain = value.partition('@')
        if not local or not domain or '.' not in domain:
            raise serializers.ValidationError("Enter a valid email address.")
        if local[0].isupper():
            raise serializers.ValidationError("Email must start with a lowercase letter.")
        if not local[0].isalpha():
            raise serializers.ValidationError("Email must start with a letter.")
        if User.objects.filter(email=value).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_role(self, value: str) -> str:
        """Validate that role is one of supported user roles.

        Args:
            value: Proposed role value.

        Returns:
            str: Validated role.
        """
        valid_roles = [choice[0] for choice in User.ROLE_CHOICES]
        if value not in valid_roles:
            raise serializers.ValidationError(
                f"Role must be one of {valid_roles}")
        return value

    def validate_password(self, value: str) -> str:
        """Validates the password while allowing numeric-only passwords."""
        user = self.instance if self.instance is not None else None
        validators = [
            UserAttributeSimilarityValidator(),
            MinimumLengthValidator(),
            CommonPasswordValidator(),
        ]
        validate_password(value, user=user, password_validators=validators)
        return value

    def update(self, instance: User, validated_data: dict[str, Any]) -> User:
        """Update a user and hash password when supplied.

        Args:
            instance: Existing user record.
            validated_data: Incoming validated fields.

        Returns:
            User: Updated user instance.
        """
        password = validated_data.pop('password', None)
        validated_data.pop('password2', None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def validate_phone_number(self, value: str) -> str:
        """ Validates that the phone number is in a valid format. """
        if not value.isdigit():
            raise serializers.ValidationError("Phone number must contain only digits.")
        if len(value) != 10:
            raise serializers.ValidationError("Phone number must be exactly 10 digits.")
        return value


class UserRegistrationSerializer(UserSerializer):
    """Serializer for user registration, inherits from UserSerializer."""
    class Meta(UserSerializer.Meta):
        extra_kwargs = {
            **UserSerializer.Meta.extra_kwargs,
            'role': {'required': False},
        }


class UserDetailSerializer(UserSerializer):
    """Serializer for user details, inherits from UserSerializer."""
    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('first_name', 'last_name', 'username', 'email', 'phone_number', 'last_login')
        read_only_fields = UserSerializer.Meta.read_only_fields + ('first_name', 'last_name', 'username', 'email', 'phone_number', 'last_login')


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Validate password reset confirmation payload."""

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value: str) -> str:
        """Validate a new password against configured validators.

        Args:
            value: Candidate plaintext password.

        Returns:
            str: Validated password.
        """
        validators = [
            UserAttributeSimilarityValidator(),
            MinimumLengthValidator(),
            CommonPasswordValidator(),
        ]
        validate_password(value, password_validators=validators)
        return value