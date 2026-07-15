"""Patient profile model definitions."""

from django.db import models

from users.models import User


class Patient(User):
    """Patient profile extending the base user model."""

    county = models.CharField(
        max_length=100,
        help_text='County where the patient lives.',
        blank=True,
        default='',
    )
    location = models.CharField(
        max_length=100,
        help_text='Specific location or neighbourhood of the patient.',
        blank=True,
        default='',
    )

    class Meta:
        db_table = 'patient_profile'
        verbose_name = 'patient'
        verbose_name_plural = 'patients'

    def __str__(self) -> str:
        """Return a readable patient profile label.

        Returns:
            str: Patient name and location.
        """
        return f"{self.first_name} {self.last_name} ({self.location})"
