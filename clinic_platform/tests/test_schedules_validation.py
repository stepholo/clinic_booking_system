"""
Test suite for doctor schedules.

Covers schedule creation, updates, overlaps, and edge cases.
"""

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import time, timedelta


@pytest.mark.django_db(databases='__all__')
class TestScheduleCreation:
    """Test doctor schedule creation and validation."""

    def test_create_valid_schedule(self, doctor_user, schedule_date):
        """Test creating a valid doctor schedule."""
        from schedules.models import DoctorSchedule

        schedule = DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        assert schedule.pk is not None
        assert schedule.doctor == doctor_user
        assert schedule.schedule_date == schedule_date
        assert schedule.is_active is True

    def test_start_time_before_end_time(self, doctor_user, schedule_date):
        """Test that start_time must be before end_time."""
        from schedules.models import DoctorSchedule

        schedule = DoctorSchedule(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(17, 0),
            end_time=time(9, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            schedule.full_clean()
        assert 'end time' in str(exc_info.value).lower()

    def test_schedule_duration_minimum(self, doctor_user, schedule_date):
        """Test minimum schedule duration (at least 1 hour)."""
        from schedules.models import DoctorSchedule

        schedule = DoctorSchedule(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(9, 30),
        )
        with pytest.raises(ValidationError):
            schedule.full_clean()


@pytest.mark.django_db(databases='__all__')
class TestScheduleOverlapPrevention:
    """Test prevention of overlapping schedule blocks."""

    def test_cannot_overlap_same_doctor_same_day(
        self, doctor_user, schedule_date
    ):
        """Test same doctor cannot have overlapping schedules on same day."""
        from schedules.models import DoctorSchedule

        # Create first schedule 9-12
        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        # Try to create overlapping schedule 11-14
        schedule2 = DoctorSchedule(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(11, 0),
            end_time=time(14, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            schedule2.full_clean()
        assert 'overlap' in str(exc_info.value).lower()

    def test_adjacent_schedules_allowed(self, doctor_user, schedule_date):
        """Test adjacent schedules (no gap, no overlap) are allowed."""
        from schedules.models import DoctorSchedule

        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        # Adjacent schedule should work
        schedule2 = DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(12, 0),
            end_time=time(15, 0),
        )
        assert schedule2.pk is not None

    def test_different_doctors_can_overlap(
        self, doctor_user, second_doctor_user, schedule_date
    ):
        """Test different doctors can have overlapping schedules."""
        from schedules.models import DoctorSchedule

        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        schedule2 = DoctorSchedule.objects.create(
            doctor=second_doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        assert schedule2.pk is not None

    def test_different_days_can_overlap(self, doctor_user):
        """Test same doctor can have same times on different days."""
        from schedules.models import DoctorSchedule

        date1 = timezone.localdate() + timedelta(days=1)
        date2 = timezone.localdate() + timedelta(days=2)

        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=date1,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        schedule2 = DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=date2,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        assert schedule2.pk is not None


@pytest.mark.django_db(databases='__all__')
class TestScheduleEdgeCases:
    """Test edge cases and boundary conditions for schedules."""

    def test_cannot_schedule_in_past(self, doctor_user):
        """Test cannot create schedule for past dates."""
        from schedules.models import DoctorSchedule

        past_date = timezone.localdate() - timedelta(days=1)
        schedule = DoctorSchedule(
            doctor=doctor_user,
            schedule_date=past_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            schedule.full_clean()
        assert 'past' in str(exc_info.value).lower()

    def test_schedule_update_preserves_appointments(
        self, doctor_user, patient_user, schedule_date
    ):
        """Test updating schedule doesn't invalidate existing appointments."""
        from bookings.models import Appointment
        from schedules.models import DoctorSchedule

        schedule = DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        slot_time = timezone.make_aware(
            timezone.datetime.combine(schedule_date, time(10, 0))
        )
        appt = Appointment.objects.create(
            doctor_id=doctor_user.user_id,
            patient_id=patient_user.user_id,
            scheduled_at=slot_time,
            status='booked',
        )

        # Extend schedule end time
        schedule.end_time = time(14, 0)
        schedule.save()

        # Appointment should still exist and be valid
        appt.refresh_from_db()
        assert appt.status == 'booked'

    def test_deactivate_schedule(self, doctor_user, schedule_date):
        """Test deactivating a schedule."""
        from schedules.models import DoctorSchedule

        schedule = DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_active=True,
        )

        schedule.is_active = False
        schedule.save()

        refreshed = DoctorSchedule.objects.get(pk=schedule.pk)
        assert refreshed.is_active is False
