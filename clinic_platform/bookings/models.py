"""Booking domain models and scheduling helpers."""

from datetime import date
from typing import Any
from uuid import UUID

from django.db import models, router
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from users.models import User


class Appointment(models.Model):
    """Represents a patient appointment with a doctor.

    The model enforces booking rules such as doctor-slot uniqueness,
    patient-slot uniqueness, schedule boundaries, and lead-time limits.
    """

    STATUS_CHOICES = [
        ('booked', 'Booked'),
        ('cancelled', 'Cancelled'),
    ]

    doctor_id = models.UUIDField()
    patient_id = models.UUIDField()
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='booked')
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'appointments'
        ordering = ['scheduled_at']
        constraints = [
            models.UniqueConstraint(
                fields=['doctor_id', 'scheduled_at'],
                condition=models.Q(status='booked'),
                name='unique_doctor_slot_when_booked',
            ),
            models.UniqueConstraint(
                fields=['patient_id', 'scheduled_at'],
                condition=models.Q(status='booked'),
                name='unique_patient_slot_when_booked',
            ),
        ]

    def clean(self) -> None:
        """Validate appointment business rules before persisting.

        Raises:
            ValidationError: If any booking rule fails.
        """
        try:
            doctor_uuid = UUID(str(self.doctor_id))
            patient_uuid = UUID(str(self.patient_id))
        except ValueError:
            raise ValidationError({'detail': 'doctor_id and patient_id must be valid UUIDs.'})

        try:
            doctor_user = User.objects.get(pk=doctor_uuid)
        except User.DoesNotExist:
            raise ValidationError({'doctor_id': 'Doctor not found.'})

        from doctors.models import Doctor
        try:
            doctor = Doctor.objects.get(pk=doctor_uuid)
        except Doctor.DoesNotExist:
            raise ValidationError({'doctor_id': 'Doctor profile not found.'})

        from schedules.models import DoctorSchedule
        DoctorSchedule.deactivate_expired()

        try:
            patient = User.objects.get(pk=patient_uuid)
        except User.DoesNotExist:
            raise ValidationError({'patient_id': 'Patient not found.'})

        local_dt = timezone.localtime(self.scheduled_at)
        schedule_date = local_dt.date()

        schedules = DoctorSchedule.objects.filter(
            doctor=doctor,
            schedule_date=schedule_date,
            is_active=True,
        ).order_by('start_time')
        if not schedules.exists():
            raise ValidationError({'scheduled_at': 'Doctor is not available on the selected date.'})

        if self.scheduled_at <= timezone.now():
            raise ValidationError({'scheduled_at': 'Appointment must be in the future.'})

        if self.scheduled_at <= timezone.now() + timezone.timedelta(hours=1):
            raise ValidationError({'scheduled_at': 'Appointments must be booked at least 1 hour ahead.'})

        if self.scheduled_at.minute not in (0, 30):
            raise ValidationError({'scheduled_at': 'Appointment must start on a 30-minute boundary.'})

        if doctor_user.role != 'doctor':
            raise ValidationError({'doctor_id': 'Selected user is not a doctor.'})

        if patient.role != 'patient':
            raise ValidationError({'patient_id': 'Selected user is not a patient.'})

        slot_start = timezone.make_aware(timezone.datetime.combine(schedule_date, local_dt.time()))
        slot_end = slot_start + timezone.timedelta(minutes=30)

        is_within_schedule = False
        for schedule in schedules:
            schedule_start = timezone.make_aware(timezone.datetime.combine(schedule_date, schedule.start_time))
            schedule_end = timezone.make_aware(timezone.datetime.combine(schedule_date, schedule.end_time))
            if slot_start >= schedule_start and slot_end <= schedule_end:
                is_within_schedule = True
                break

        if not is_within_schedule:
            raise ValidationError({'scheduled_at': 'Appointment must fall within the doctor\'s schedule for the selected day.'})

        conflict_qs = Appointment.objects.filter(
            doctor_id=self.doctor_id,
            scheduled_at=self.scheduled_at,
            status='booked',
        )
        if self.pk:
            conflict_qs = conflict_qs.exclude(pk=self.pk)
        if conflict_qs.exists():
            raise ValidationError({'scheduled_at': 'This slot is already booked.'})

        patient_conflict_qs = Appointment.objects.filter(
            patient_id=self.patient_id,
            scheduled_at=self.scheduled_at,
            status='booked',
        )
        if self.pk:
            patient_conflict_qs = patient_conflict_qs.exclude(pk=self.pk)
        if patient_conflict_qs.exists():
            raise ValidationError({'scheduled_at': 'Patient already has an appointment at this time.'})

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Persist the appointment after running full model validation.

        Args:
            *args: Positional save arguments.
            **kwargs: Keyword save arguments, optionally including ``using``.
        """
        using = kwargs.pop('using', None) or self._state.db or router.db_for_write(self.__class__, instance=self)
        if using:
            self._state.db = using
        self.full_clean()
        super().save(*args, using=using, **kwargs)

    @classmethod
    def get_available_slots(cls, doctor_id: UUID | str, date: date) -> list[str]:
        """Return available 30-minute slots for a doctor on a given date.

        Args:
            doctor_id: Doctor UUID.
            date: Date to inspect for available slots.

        Returns:
            list[str]: ISO 8601 date-time strings for open slots.

        Raises:
            ValidationError: If the doctor does not exist.
        """
        from doctors.models import Doctor
        from schedules.models import DoctorSchedule
        from .cache_utils import get_slots, set_slots

        cached_slots = get_slots(doctor_id, date)
        if cached_slots is not None:
            return cached_slots

        DoctorSchedule.deactivate_expired()

        try:
            doctor = Doctor.objects.get(pk=doctor_id)
        except Doctor.DoesNotExist:
            raise ValidationError({'doctor': 'Doctor not found.'})

        schedules = DoctorSchedule.objects.filter(
            doctor=doctor,
            schedule_date=date,
            is_active=True,
        ).order_by('start_time')
        if not schedules.exists():
            return []

        slots = []
        overall_start = timezone.make_aware(timezone.datetime.combine(date, schedules.first().start_time))
        overall_end = timezone.make_aware(timezone.datetime.combine(date, schedules.last().end_time))

        booked = set(cls.objects.filter(
            doctor_id=doctor_id,
            scheduled_at__gte=overall_start,
            scheduled_at__lte=overall_end,
            status='booked'
        ).values_list('scheduled_at', flat=True))

        for schedule in schedules:
            current = timezone.make_aware(timezone.datetime.combine(date, schedule.start_time))
            end_slot = timezone.make_aware(timezone.datetime.combine(date, schedule.end_time))

            while current + timezone.timedelta(minutes=30) <= end_slot:
                if current > timezone.now() and current not in booked:
                    slots.append(current.isoformat())
                current += timezone.timedelta(minutes=30)

            set_slots(doctor_id, date, slots, settings.CACHE_TTL_SECONDS)
        return slots
