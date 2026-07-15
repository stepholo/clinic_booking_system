"""
This is the accounts app models.py file.
It contains the User model which is a custom user model that extends AbstractUser.
The User model will be used for user categorization, authentication and authorization in the application.
"""

from uuid import uuid4

from django.db import models
from django.contrib.auth.models import AbstractUser, Permission, Group
from django.core.validators import RegexValidator


# Create your models here.
class User(AbstractUser):
    """
    Custom User model that extends AbstractUser.
    This model will be used for user categorization, authentication and authorization in the application.
    """

    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('doctor', 'Doctor'),
        ('patient', 'Patient'),
    )

    user_id = models.UUIDField(
        primary_key=True, 
        default=uuid4, 
        editable=False,
        unique=True,
        help_text="Unique identifier for the user."
        )

    first_name = models.CharField(
        verbose_name="First name",
        max_length=30,
        help_text="First name of the user."
    )

    last_name = models.CharField(
        verbose_name="Last name",
        max_length=30,
        help_text="Last name of the user."
    )

    username = models.CharField(
        verbose_name="Username",
        max_length=150,
        unique=True,
        help_text="Username of the user."
    )

    email = models.EmailField(
        verbose_name="Email address",
        unique=True,
        help_text="Email address of the user."
    )

    phone_number = models.CharField(
        verbose_name="Phone number",
        max_length=15,
        unique=True,
        validators=[
            RegexValidator(regex=r'^\+?1?\d{9,15}$', 
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
            code='invalid_phone_number'
            )
        ],
        help_text="Phone number of the user."
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='patient',
        help_text="Role of the user."
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the user was created."
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the user was last updated."
    )

    last_login = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the user last logged in."
    )

    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        related_name='user_set',
        help_text="""The permissions this user has. 
                    A user will get all permissions granted to each of their groups."""
    )

    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        related_name='user_set',
        help_text="""The groups this user belongs to.
                    A user will get all permissions granted to each of their groups."""
    )

    def __str__(self) -> str:
        """Return a readable user display value.

        Returns:
            str: User full name and email.
        """
        return f"{self.first_name} {self.last_name} ({self.email})"

    
    class Meta:
        """
        Meta class for the User model.
        Defines the verbose name and ordering of the model.
        """
        verbose_name = 'user'
        verbose_name_plural = 'users'
        ordering = ['first_name', 'last_name', '-created_at']
        db_table = 'users_accounts'
        indexes = [
            models.Index(fields=['username'], name='username_idx'),
            models.Index(fields=['email'], name='email_idx'),
            models.Index(fields=['phone_number'], name='phone_number_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['username'], name='unique_username'),
            models.UniqueConstraint(fields=['email'], name='unique_email'),
            models.UniqueConstraint(fields=['phone_number'], name='unique_phone_number'),
        ]



