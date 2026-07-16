"""Pytest coverage for appointment booking constraints."""

from datetime import datetime, time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from bookings.models import Appointment
from doctors.models import Doctor
from patients.models import Patient
from schedules.models import DoctorSchedule


def _future_slot(day_offset: int = 1, slot_time: time = time(10, 0)):
	"""Build a timezone-aware future slot on a 30-minute boundary."""
	target_day = timezone.localdate() + timedelta(days=day_offset)
	return timezone.make_aware(datetime.combine(target_day, slot_time))


def _create_doctor(index: int) -> Doctor:
	"""Create a doctor profile with unique identity fields."""
	return Doctor.objects.create(
		username=f"pytest_doc_{index}",
		first_name=f"Doc{index}",
		last_name="Tester",
		email=f"pytest_doc_{index}@example.com",
		phone_number=f"0799{index:06d}",
		role="doctor",
		speciality="General",
	)


def _create_patient(index: int) -> Patient:
	"""Create a patient profile with unique identity fields."""
	return Patient.objects.create(
		username=f"pytest_pat_{index}",
		first_name=f"Pat{index}",
		last_name="Tester",
		email=f"pytest_pat_{index}@example.com",
		phone_number=f"0788{index:06d}",
		role="patient",
		county="Nairobi",
		location="Test Location",
	)


@pytest.mark.django_db(databases=["default", "user_db", "booking_db"])
def test_patient_cannot_book_two_doctors_same_slot() -> None:
	"""Ensure one patient cannot hold two bookings at the same datetime."""
	slot = _future_slot()
	doctor_one = _create_doctor(1)
	doctor_two = _create_doctor(2)
	patient = _create_patient(1)

	DoctorSchedule.objects.create(
		doctor=doctor_one,
		schedule_date=slot.date(),
		start_time=time(9, 0),
		end_time=time(12, 0),
		is_active=True,
	)
	DoctorSchedule.objects.create(
		doctor=doctor_two,
		schedule_date=slot.date(),
		start_time=time(9, 0),
		end_time=time(12, 0),
		is_active=True,
	)

	Appointment.objects.create(
		doctor_id=doctor_one.user_id,
		patient_id=patient.user_id,
		scheduled_at=slot,
		status="booked",
		reason="first booking",
	)

	duplicate_slot = Appointment(
		doctor_id=doctor_two.user_id,
		patient_id=patient.user_id,
		scheduled_at=slot,
		status="booked",
		reason="conflict booking",
	)
	with pytest.raises(ValidationError, match="Patient already has an appointment"):
		duplicate_slot.save()


@pytest.mark.django_db(databases=["default", "user_db", "booking_db"])
def test_two_patients_cannot_book_same_doctor_slot() -> None:
	"""Ensure doctor slot collisions are blocked across patients."""
	slot = _future_slot()
	doctor = _create_doctor(3)
	patient_one = _create_patient(2)
	patient_two = _create_patient(3)

	DoctorSchedule.objects.create(
		doctor=doctor,
		schedule_date=slot.date(),
		start_time=time(9, 0),
		end_time=time(12, 0),
		is_active=True,
	)

	Appointment.objects.create(
		doctor_id=doctor.user_id,
		patient_id=patient_one.user_id,
		scheduled_at=slot,
		status="booked",
		reason="first booking",
	)

	duplicate_slot = Appointment(
		doctor_id=doctor.user_id,
		patient_id=patient_two.user_id,
		scheduled_at=slot,
		status="booked",
		reason="conflict booking",
	)
	with pytest.raises(ValidationError, match="This slot is already booked"):
		duplicate_slot.save()
