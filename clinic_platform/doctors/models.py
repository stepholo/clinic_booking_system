"""Doctor profile model definitions."""

from datetime import time

from django.db import models

from users.models import User


class Doctor(User):
    """Doctor profile extending the base user model."""

    speciality = models.CharField(
        max_length=100,
        help_text='Speciality of the doctor.',
        blank=True,
        default='',
    )
    work_start_time = models.TimeField(
        default=time(8, 0),
        help_text='Doctor working day start time.',
    )
    work_end_time = models.TimeField(
        default=time(17, 0),
        help_text='Doctor working day end time.',
    )

    class Meta:
        db_table = 'doctor_profile'
        verbose_name = 'doctor'
        verbose_name_plural = 'doctors'

    def __str__(self) -> str:
        """Return a readable doctor profile label.

        Returns:
            str: Doctor name and speciality.
        """
        return f"Dr. {self.first_name} {self.last_name} - {self.speciality}"
