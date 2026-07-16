"""Pytest configuration and shared fixtures for all tests."""

from datetime import time, timedelta
from uuid import uuid4

import pytest
from django.utils import timezone


@pytest.fixture
def doctor_user():
    """Create a test doctor user."""
    from doctors.models import Doctor
    from users.models import User

    user = User.objects.create_user(
        username='test_doctor',
        email='doctor@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Doctor',
        phone_number='0701234567',
        role='doctor',
    )
    doctor = Doctor.objects.get(pk=user.pk)
    doctor.speciality = 'Cardiologist'
    doctor.work_start_time = time(8, 0)
    doctor.work_end_time = time(17, 0)
    doctor.save()
    return doctor


@pytest.fixture
def second_doctor_user():
    """Create a second test doctor user."""
    from doctors.models import Doctor
    from users.models import User

    user = User.objects.create_user(
        username='test_doctor_2',
        email='doctor2@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Doctor2',
        phone_number='0701234568',
        role='doctor',
    )
    doctor = Doctor.objects.get(pk=user.pk)
    doctor.speciality = 'Dermatologist'
    doctor.work_start_time = time(8, 0)
    doctor.work_end_time = time(17, 0)
    doctor.save()
    return doctor


@pytest.fixture
def patient_user():
    """Create a test patient user."""
    from patients.models import Patient
    from users.models import User

    user = User.objects.create_user(
        username='test_patient',
        email='patient@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Patient',
        phone_number='0712345678',
        role='patient',
    )
    patient = Patient.objects.get(pk=user.pk)
    patient.county = 'Nairobi'
    patient.location = 'Westlands'
    patient.save()
    return patient


@pytest.fixture
def second_patient_user():
    """Create a second test patient user."""
    from patients.models import Patient
    from users.models import User

    user = User.objects.create_user(
        username='test_patient_2',
        email='patient2@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Patient2',
        phone_number='0712345679',
        role='patient',
    )
    patient = Patient.objects.get(pk=user.pk)
    patient.county = 'Nairobi'
    patient.location = 'Karen'
    patient.save()
    return patient


@pytest.fixture
def schedule_date():
    """Return a date 2 days from now."""
    return timezone.localdate() + timedelta(days=2)


@pytest.fixture
def doctor_schedule(doctor_user, schedule_date):
    """Create a doctor schedule for testing."""
    from schedules.models import DoctorSchedule

    schedule = DoctorSchedule.objects.create(
        doctor=doctor_user,
        schedule_date=schedule_date,
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_active=True,
    )
    return schedule


@pytest.fixture
def second_doctor_schedule(second_doctor_user, schedule_date):
    """Create a second doctor schedule for testing."""
    from schedules.models import DoctorSchedule

    schedule = DoctorSchedule.objects.create(
        doctor=second_doctor_user,
        schedule_date=schedule_date,
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_active=True,
    )
    return schedule
