"""Schedule models defining doctor availability blocks."""

from datetime import datetime, timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

from doctors.models import Doctor


class DoctorSchedule(models.Model):
    """Represents one active or inactive schedule block for a doctor."""

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='schedules')
    schedule_date = models.DateField(help_text='Date this working schedule applies to.')
    start_time = models.TimeField(help_text='Schedule start time for the day.')
    end_time = models.TimeField(help_text='Schedule end time for the day.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'doctor_schedules'
        ordering = ['schedule_date', 'start_time']
        constraints = [
            models.UniqueConstraint(
                fields=['doctor', 'schedule_date', 'start_time', 'end_time'],
                name='unique_doctor_schedule_time_block',
            ),
            models.CheckConstraint(condition=Q(start_time__lt=F('end_time')), name='schedule_start_before_end'),
        ]

    @classmethod
    def deactivate_expired(cls) -> int:
        """Deactivate schedule blocks that are already in the past.

        Returns:
            int: Number of records updated.
        """
        now = timezone.localtime()
        return cls.objects.filter(
            is_active=True,
        ).filter(
            Q(schedule_date__lt=now.date()) |
            Q(schedule_date=now.date(), end_time__lte=now.time())
        ).update(is_active=False)

    def clean(self) -> None:
        """Validate time boundaries and active-block overlap rules.

        Raises:
            ValidationError: If schedule times are invalid or overlapping.
        """
        if self.schedule_date and self.end_time:
            now = timezone.localtime()
            if self.schedule_date < now.date():
                raise ValidationError({'schedule_date': 'Cannot create a schedule in the past.'})
            if self.schedule_date == now.date() and self.end_time <= now.time():
                raise ValidationError({'end_time': 'End time must be in the future for schedules on today.'})

        self.start_time = self.start_time.replace(second=0, microsecond=0)
        self.end_time = self.end_time.replace(second=0, microsecond=0)

        if self.start_time.minute not in (0, 30):
            raise ValidationError({'start_time': 'Start time must be on a 30-minute boundary (HH:00 or HH:30).'})

        if self.end_time.minute not in (0, 30):
            raise ValidationError({'end_time': 'End time must be on a 30-minute boundary (HH:00 or HH:30).'})

        if self.start_time >= self.end_time:
            raise ValidationError({'end_time': 'End time must be later than start time.'})

        duration = datetime.combine(self.schedule_date, self.end_time) - datetime.combine(self.schedule_date, self.start_time)
        if duration < timedelta(hours=1):
            raise ValidationError({'end_time': 'Schedule duration must be at least 1 hour.'})

        if not self.doctor_id or not self.schedule_date:
            return

        # Prevent overlapping active schedule blocks for the same doctor/day.
        if self.is_active:
            overlap_qs = DoctorSchedule.objects.filter(
                doctor_id=self.doctor_id,
                schedule_date=self.schedule_date,
                is_active=True,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            )
            if self.pk:
                overlap_qs = overlap_qs.exclude(pk=self.pk)
            if overlap_qs.exists():
                raise ValidationError({'detail': 'Schedule block overlaps with an existing active block for this day.'})

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Run model validation then persist schedule record.

        Args:
            *args: Positional save arguments.
            **kwargs: Keyword save arguments.
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Return a readable schedule label.

        Returns:
            str: Doctor, date, and time window label.
        """
        return f'{self.doctor} - {self.schedule_date} ({self.start_time} to {self.end_time})'
