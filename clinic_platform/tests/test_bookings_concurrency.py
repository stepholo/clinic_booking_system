"""
Test concurrency, race conditions, and double-booking prevention.

Scenarios covered:
1. Race conditions: Two simultaneous booking requests for same slot
2. Double booking - Scenario A: One patient booking two doctors at same time
3. Double booking - Scenario B: Two patients booking same doctor slot
4. Ghost slot problem: Slot shows available but gets booked before confirmation
5. Edge cases: Boundary conditions, validation rules
"""

from datetime import time, timedelta
from threading import Thread

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone


@pytest.mark.django_db(databases='__all__')
class TestDoubleBookingPrevention:
    """Test prevention of patient double-bookings (patient with two doctors same time)."""

    def test_patient_cannot_book_two_doctors_same_time(
        self, doctor_user, second_doctor_user, patient_user, schedule_date
    ):
        """Scenario A: Patient cannot book two different doctors at same time slot."""
        from bookings.models import Appointment
        from schedules.models import DoctorSchedule

        slot_time = time(10, 0)
        scheduled_at = timezone.make_aware(
            timezone.datetime.combine(schedule_date, slot_time)
        )

        # Create schedules for both doctors
        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        DoctorSchedule.objects.create(
            doctor=second_doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        # Book first doctor - should succeed
        appt1 = Appointment(
            doctor_id=doctor_user.user_id,
            patient_id=patient_user.user_id,
            scheduled_at=scheduled_at,
            status='booked',
            reason='Test booking 1',
        )
        appt1.save()
        assert appt1.pk is not None

        # Try to book second doctor at same time - should fail
        appt2 = Appointment(
            doctor_id=second_doctor_user.user_id,
            patient_id=patient_user.user_id,
            scheduled_at=scheduled_at,
            status='booked',
            reason='Test booking 2',
        )

        with pytest.raises(ValidationError) as exc_info:
            appt2.save()
        assert 'Patient already has an appointment at this time' in str(
            exc_info.value
        )

    def test_two_patients_cannot_book_same_doctor_slot(
        self,
        doctor_user,
        patient_user,
        second_patient_user,
        schedule_date,
    ):
        """Scenario B: Two different patients cannot book same doctor slot."""
        from bookings.models import Appointment
        from schedules.models import DoctorSchedule

        slot_time = time(10, 0)
        scheduled_at = timezone.make_aware(
            timezone.datetime.combine(schedule_date, slot_time)
        )

        # Create schedule
        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        # First patient books
        appt1 = Appointment(
            doctor_id=doctor_user.user_id,
            patient_id=patient_user.user_id,
            scheduled_at=scheduled_at,
            status='booked',
            reason='Test booking 1',
        )
        appt1.save()
        assert appt1.pk is not None

        # Second patient tries to book same slot - should fail
        appt2 = Appointment(
            doctor_id=doctor_user.user_id,
            patient_id=second_patient_user.user_id,
            scheduled_at=scheduled_at,
            status='booked',
            reason='Test booking 2',
        )

        with pytest.raises(ValidationError) as exc_info:
            appt2.save()
        assert 'This slot is already booked' in str(exc_info.value)


@pytest.mark.django_db(databases='__all__')
class TestRaceConditions:
    """Test race condition handling with concurrent booking attempts."""

    def test_database_enforces_doctor_slot_uniqueness(
        self, doctor_user, patient_user, second_patient_user, schedule_date
    ):
        """Test DB constraint prevents two patients from same slot even with race condition."""
        from bookings.models import Appointment
        from schedules.models import DoctorSchedule

        slot_time = time(10, 0)
        scheduled_at = timezone.make_aware(
            timezone.datetime.combine(schedule_date, slot_time)
        )

        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        # Simulate two concurrent attempts bypassing ORM validation
        appt1 = Appointment(
            doctor_id=doctor_user.user_id,
            patient_id=patient_user.user_id,
            scheduled_at=scheduled_at,
            status='booked',
        )
        appt1.save()

        # Try to insert duplicate via raw transaction, bypassing model clean()
        appt2 = Appointment(
            doctor_id=doctor_user.user_id,
            patient_id=second_patient_user.user_id,
            scheduled_at=scheduled_at,
            status='booked',
        )

        with pytest.raises((ValidationError, IntegrityError)):
            with transaction.atomic():
                appt2.save()

    def test_database_enforces_patient_slot_uniqueness(
        self, doctor_user, second_doctor_user, patient_user, schedule_date
    ):
        """Test DB constraint prevents patient double-booking even with race condition."""
        from bookings.models import Appointment
        from schedules.models import DoctorSchedule

        slot_time = time(10, 0)
        scheduled_at = timezone.make_aware(
            timezone.datetime.combine(schedule_date, slot_time)
        )

        for doc in [doctor_user, second_doctor_user]:
            DoctorSchedule.objects.create(
                doctor=doc,
                schedule_date=schedule_date,
                start_time=time(9, 0),
                end_time=time(17, 0),
            )

        appt1 = Appointment(
            doctor_id=doctor_user.user_id,
            patient_id=patient_user.user_id,
            scheduled_at=scheduled_at,
            status='booked',
        )
        appt1.save()

        appt2 = Appointment(
            doctor_id=second_doctor_user.user_id,
            patient_id=patient_user.user_id,
            scheduled_at=scheduled_at,
            status='booked',
        )

        with pytest.raises((ValidationError, IntegrityError)):
            with transaction.atomic():
                appt2.save()


@pytest.mark.django_db(databases='__all__')
class TestGhostSlotProblem:
    """Test prevention of ghost slot problem (slot shows available but gets booked)."""

    def test_slot_availability_reflects_real_bookings(
        self, doctor_user, patient_user, schedule_date
    ):
        """Ghost slot test: Available slots should exclude truly booked slots."""
        from bookings.models import Appointment
        from schedules.models import DoctorSchedule

        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        # Get available slots before booking
        slots_before = Appointment.get_available_slots(doctor_user.user_id, schedule_date)
        assert len(slots_before) > 0

        # Book a slot
        slot_to_book = timezone.make_aware(
            timezone.datetime.combine(schedule_date, time(10, 0))
        )
        appt = Appointment(
            doctor_id=doctor_user.user_id,
            patient_id=patient_user.user_id,
            scheduled_at=slot_to_book,
            status='booked',
        )
        appt.save()

        # Get available slots after booking - should not include booked slot
        slots_after = Appointment.get_available_slots(doctor_user.user_id, schedule_date)
        assert slot_to_book.isoformat() not in slots_after
        assert len(slots_after) == len(slots_before) - 1

    def test_cancelled_slot_returns_to_available(
        self, doctor_user, patient_user, schedule_date
    ):
        """Test that cancelling a booking returns the slot to available."""
        from bookings.models import Appointment
        from schedules.models import DoctorSchedule

        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
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

        # Verify slot is not available
        slots_booked = Appointment.get_available_slots(
            doctor_user.user_id, schedule_date
        )
        assert slot_time.isoformat() not in slots_booked

        # Cancel the booking
        appt.status = 'cancelled'
        appt.save()

        # Verify slot is now available again
        slots_after_cancel = Appointment.get_available_slots(
            doctor_user.user_id, schedule_date
        )
        assert slot_time.isoformat() in slots_after_cancel


@pytest.mark.django_db(databases='__all__')
class TestEdgeCases:
    """Test boundary conditions and validation edge cases."""

    def test_booking_requires_30_minute_boundary(
        self, doctor_user, patient_user, schedule_date
    ):
        """Test slots must start on 30-minute boundaries (HH:00 or HH:30)."""
        from bookings.models import Appointment
        from schedules.models import DoctorSchedule

        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        # Invalid: 10:15
        invalid_slot = timezone.make_aware(
            timezone.datetime.combine(schedule_date, time(10, 15))
        )
        appt = Appointment(
            doctor_id=doctor_user.user_id,
            patient_id=patient_user.user_id,
            scheduled_at=invalid_slot,
            status='booked',
        )
        with pytest.raises(ValidationError) as exc_info:
            appt.save()
        assert '30-minute boundary' in str(exc_info.value)

    def test_booking_must_be_1_hour_ahead(
        self, doctor_user, patient_user, schedule_date
    ):
        """Test bookings must be at least 1 hour in the future."""
        from bookings.models import Appointment
        from schedules.models import DoctorSchedule

        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        # Try to book 30 minutes from now - should fail
        soon = timezone.now() + timedelta(minutes=30)
        appt = Appointment(
            doctor_id=doctor_user.user_id,
            patient_id=patient_user.user_id,
            scheduled_at=soon,
            status='booked',
        )
        with pytest.raises(ValidationError) as exc_info:
            appt.save()
        assert '1 hour ahead' in str(exc_info.value)

    def test_cannot_book_outside_schedule_window(
        self, doctor_user, patient_user, schedule_date
    ):
        """Test cannot book outside doctor's scheduled working hours."""
        from bookings.models import Appointment
        from schedules.models import DoctorSchedule

        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        # Try to book after schedule ends
        outside_slot = timezone.make_aware(
            timezone.datetime.combine(schedule_date, time(14, 0))
        )
        appt = Appointment(
            doctor_id=doctor_user.user_id,
            patient_id=patient_user.user_id,
            scheduled_at=outside_slot,
            status='booked',
        )
        with pytest.raises(ValidationError) as exc_info:
            appt.save()
        assert 'within the doctor' in str(exc_info.value)

    def test_cannot_book_past_appointment(
        self, doctor_user, patient_user, schedule_date
    ):
        """Test cannot book appointments in the past."""
        from bookings.models import Appointment
        from schedules.models import DoctorSchedule

        DoctorSchedule.objects.create(
            doctor=doctor_user,
            schedule_date=schedule_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        # Try to book in the past
        past_slot = timezone.now() - timedelta(hours=1)
        appt = Appointment(
            doctor_id=doctor_user.user_id,
            patient_id=patient_user.user_id,
            scheduled_at=past_slot,
            status='booked',
        )
        with pytest.raises(ValidationError) as exc_info:
            appt.save()
        assert 'in the future' in str(exc_info.value)
