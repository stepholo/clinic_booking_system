"""Pytest coverage for doctor schedule validation rules."""

from datetime import time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from doctors.models import Doctor
from schedules.models import DoctorSchedule


def _create_doctor(index: int) -> Doctor:
	"""Create a doctor profile used by schedule tests."""
	return Doctor.objects.create(
		username=f"pytest_sched_doc_{index}",
		first_name=f"Sched{index}",
		last_name="Doctor",
		email=f"pytest_sched_doc_{index}@example.com",
		phone_number=f"0777{index:06d}",
		role="doctor",
		speciality="General",
	)


@pytest.mark.django_db(databases=["default", "user_db", "booking_db"])
def test_same_doctor_overlapping_blocks_raise_validation_error() -> None:
	"""Ensure overlapping blocks are rejected for same doctor and day."""
	doctor = _create_doctor(1)
	target_day = timezone.localdate() + timedelta(days=1)

	DoctorSchedule.objects.create(
		doctor=doctor,
		schedule_date=target_day,
		start_time=time(9, 0),
		end_time=time(11, 0),
		is_active=True,
	)

	with pytest.raises(ValidationError, match="overlaps"):
		DoctorSchedule.objects.create(
			doctor=doctor,
			schedule_date=target_day,
			start_time=time(10, 30),
			end_time=time(12, 0),
			is_active=True,
		)


@pytest.mark.django_db(databases=["default", "user_db", "booking_db"])
def test_different_doctors_can_have_overlapping_blocks() -> None:
	"""Ensure overlapping times are allowed across different doctors."""
	doctor_one = _create_doctor(2)
	doctor_two = _create_doctor(3)
	target_day = timezone.localdate() + timedelta(days=1)

	first = DoctorSchedule.objects.create(
		doctor=doctor_one,
		schedule_date=target_day,
		start_time=time(9, 0),
		end_time=time(11, 0),
		is_active=True,
	)
	second = DoctorSchedule.objects.create(
		doctor=doctor_two,
		schedule_date=target_day,
		start_time=time(9, 30),
		end_time=time(11, 30),
		is_active=True,
	)

	assert first.pk is not None
	assert second.pk is not None
