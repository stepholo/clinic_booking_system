"""Management command to seed demo doctors, patients, schedules, and bookings."""

from datetime import datetime, time, timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.models import Appointment
from doctors.models import Doctor
from patients.models import Patient
from schedules.models import DoctorSchedule


class Command(BaseCommand):
    """Seed deterministic demo data for non-production verification."""

    help = "Seed demo doctors, patients, schedules, and appointments."

    def add_arguments(self, parser: Any) -> None:
        """Register supported command-line arguments.

        Args:
            parser: Django command argument parser.
        """
        parser.add_argument(
            "--days-ahead",
            type=int,
            default=2,
            help="Number of days from today for seeded schedules/appointments (default: 2).",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="Pass1234!",
            help="Password to set for seeded users (default: Pass1234!).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow command to run even if seed users already exist.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Execute idempotent seed creation workflow.

        Args:
            *args: Positional command args.
            **options: Parsed command options.
        """
        days_ahead = options["days_ahead"]
        password = options["password"]
        force = options["force"]

        if not force and self._seed_already_exists():
            self.stdout.write(
                self.style.WARNING(
                    "Seed users already exist. Skipping to avoid reseeding production data. "
                    "Use --force to run anyway."
                )
            )
            return

        schedule_date = timezone.localdate() + timedelta(days=days_ahead)

        created = {
            "doctors": 0,
            "patients": 0,
            "schedules": 0,
            "appointments": 0,
        }

        doctor_specs = [
            ("seed_doc_01", "Amina", "Otieno", "seed_doc_01@example.com", "0701000001", "Cardiologist"),
            ("seed_doc_02", "Brian", "Mwangi", "seed_doc_02@example.com", "0701000002", "Dermatologist"),
            ("seed_doc_03", "Cynthia", "Wanjiku", "seed_doc_03@example.com", "0701000003", "Pediatrician"),
            ("seed_doc_04", "David", "Odhiambo", "seed_doc_04@example.com", "0701000004", "Neurologist"),
            (
                "seed_doc_05",
                "Esther",
                "Achieng",
                "seed_doc_05@example.com",
                "0701000005",
                "General Practitioner",
            ),
        ]

        seed_doctors = []
        for username, first_name, last_name, email, phone, speciality in doctor_specs:
            doctor, is_created = Doctor.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "phone_number": phone,
                    "role": "doctor",
                    "speciality": speciality,
                    "work_start_time": time(8, 0),
                    "work_end_time": time(17, 0),
                },
            )
            doctor.first_name = first_name
            doctor.last_name = last_name
            doctor.email = email
            doctor.phone_number = phone
            doctor.role = "doctor"
            doctor.speciality = speciality
            doctor.work_start_time = time(8, 0)
            doctor.work_end_time = time(17, 0)
            doctor.set_password(password)
            doctor.save()

            if is_created:
                created["doctors"] += 1
            seed_doctors.append(doctor)

        seed_patients = []
        for i in range(1, 21):
            username = f"seed_pat_{i:02d}"
            patient, is_created = Patient.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": f"Patient{i:02d}",
                    "last_name": "Demo",
                    "email": f"seed_pat_{i:02d}@example.com",
                    "phone_number": f"0712{i:06d}",
                    "role": "patient",
                    "county": "Nairobi",
                    "location": f"Location-{i:02d}",
                },
            )
            patient.first_name = f"Patient{i:02d}"
            patient.last_name = "Demo"
            patient.email = f"seed_pat_{i:02d}@example.com"
            patient.phone_number = f"0712{i:06d}"
            patient.role = "patient"
            patient.county = "Nairobi"
            patient.location = f"Location-{i:02d}"
            patient.set_password(password)
            patient.save()

            if is_created:
                created["patients"] += 1
            seed_patients.append(patient)

        # Intentional cross-doctor overlaps on the same day.
        schedule_windows = [
            (time(9, 0), time(13, 0)),
            (time(9, 30), time(12, 30)),
            (time(10, 0), time(14, 0)),
            (time(13, 0), time(17, 0)),
            (time(8, 30), time(11, 30)),
        ]

        for doctor, (start_t, end_t) in zip(seed_doctors, schedule_windows):
            schedule, is_created = DoctorSchedule.objects.get_or_create(
                doctor=doctor,
                schedule_date=schedule_date,
                start_time=start_t,
                end_time=end_t,
                defaults={"is_active": True},
            )
            if not schedule.is_active:
                schedule.is_active = True
                schedule.save(update_fields=["is_active", "updated_at"])
            if is_created:
                created["schedules"] += 1

        slot_times = [time(9, 0), time(10, 0), time(10, 30), time(13, 30), time(9, 30)]
        for idx, (doctor, slot_t) in enumerate(zip(seed_doctors, slot_times)):
            patient = seed_patients[idx]
            scheduled_at = timezone.make_aware(datetime.combine(schedule_date, slot_t))

            appointment = Appointment.objects.filter(
                doctor_id=doctor.user_id,
                scheduled_at=scheduled_at,
            ).first()

            if appointment is None:
                appointment = Appointment(
                    doctor_id=doctor.user_id,
                    patient_id=patient.user_id,
                    scheduled_at=scheduled_at,
                    status="booked",
                    reason="Seeded demo booking",
                )
                appointment.save()
                created["appointments"] += 1
            else:
                appointment.patient_id = patient.user_id
                appointment.status = "booked"
                appointment.reason = "Seeded demo booking"
                appointment.save()

        self.stdout.write(self.style.SUCCESS("seed_demo_data completed."))
        self.stdout.write(f"Seed date: {schedule_date}")
        self.stdout.write(f"Created doctors: {created['doctors']}")
        self.stdout.write(f"Created patients: {created['patients']}")
        self.stdout.write(f"Created schedules: {created['schedules']}")
        self.stdout.write(f"Created appointments: {created['appointments']}")
        self.stdout.write(f"Total doctors: {Doctor.objects.filter(username__startswith='seed_doc_').count()}")
        self.stdout.write(f"Total patients: {Patient.objects.filter(username__startswith='seed_pat_').count()}")

    def _seed_already_exists(self) -> bool:
        """Check whether demo seed users are already present.

        Returns:
            bool: ``True`` when seeded doctors or patients already exist.
        """
        return Doctor.objects.filter(username__startswith="seed_doc_").exists() or Patient.objects.filter(
            username__startswith="seed_pat_"
        ).exists()
