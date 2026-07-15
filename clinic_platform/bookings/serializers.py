"""Serializers for appointment creation and validation workflows."""

from datetime import datetime
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from .models import Appointment
from users.models import User


class AppointmentSerializer(serializers.ModelSerializer):
    """Serialize appointments and enforce request-level booking validation."""

    class Meta:
        model = Appointment
        fields = [
            'id',
            'doctor_id',
            'patient_id',
            'scheduled_at',
            'status',
            'reason',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'patient_id', 'status', 'created_at', 'updated_at']
        validators = []

    def validate_doctor_id(self, value: Any) -> Any:
        """Validate that the selected doctor user exists and has doctor role.

        Args:
            value: Candidate doctor UUID value.

        Returns:
            Any: The validated value.

        Raises:
            serializers.ValidationError: If the doctor is invalid.
        """
        try:
            user = User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError('Doctor not found.')
        if user.role != 'doctor':
            raise serializers.ValidationError('Selected user is not a doctor.')
        return value

    def validate_patient_id(self, value: Any) -> Any:
        """Validate that the selected patient user exists and has patient role.

        Args:
            value: Candidate patient UUID value.

        Returns:
            Any: The validated value.

        Raises:
            serializers.ValidationError: If the patient is invalid.
        """
        try:
            user = User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError('Patient not found.')
        if user.role != 'patient':
            raise serializers.ValidationError('Selected user is not a patient.')
        return value

    def validate_scheduled_at(self, value: datetime) -> datetime:
        """Validate that an appointment start time is bookable.

        Args:
            value: Requested appointment datetime.

        Returns:
            datetime: Normalized valid datetime value.

        Raises:
            serializers.ValidationError: If date-time violates booking rules.
        """
        minimum_start = timezone.now() + timezone.timedelta(hours=1)
        if value <= timezone.now():
            raise serializers.ValidationError('Appointment must be in the future.')
        if value <= minimum_start:
            raise serializers.ValidationError('Appointments must be booked at least 1 hour ahead.')
        if value.minute not in (0, 30):
            raise serializers.ValidationError('Appointment must start on a 30-minute boundary.')
        return value

    def build_slot_feedback(self, doctor_id: Any, scheduled_at: datetime, detail: str) -> dict[str, Any]:
        """Build contextual feedback for doctor-slot booking conflicts.

        Args:
            doctor_id: Doctor UUID.
            scheduled_at: Requested slot datetime.
            detail: Human-readable error message.

        Returns:
            dict[str, Any]: Conflict payload with alternatives.
        """
        from schedules.models import DoctorSchedule

        DoctorSchedule.deactivate_expired()
        local_dt = timezone.localtime(scheduled_at)
        schedule_date = local_dt.date()
        available_slots = Appointment.get_available_slots(doctor_id, schedule_date)
        schedules = DoctorSchedule.objects.filter(
            doctor_id=doctor_id,
            schedule_date=schedule_date,
            is_active=True,
        ).order_by('start_time')
        parsed_available_slots = [datetime.fromisoformat(slot) for slot in available_slots]

        available_schedule_blocks = []
        for schedule in schedules:
            schedule_start = timezone.make_aware(timezone.datetime.combine(schedule_date, schedule.start_time))
            schedule_end = timezone.make_aware(timezone.datetime.combine(schedule_date, schedule.end_time))

            has_available_slot = any(
                schedule_start <= slot < schedule_end
                for slot in parsed_available_slots
            )
            if has_available_slot:
                available_schedule_blocks.append(
                    {
                        'start_time': schedule.start_time.strftime('%H:%M:%S'),
                        'end_time': schedule.end_time.strftime('%H:%M:%S'),
                    }
                )

        return {
            'detail': detail,
            'requested_slot': local_dt.isoformat(),
            'nearest_available_slots': available_slots[:5],
            'schedule_blocks': available_schedule_blocks,
        }

    def build_patient_slot_conflict_feedback(
        self,
        patient_id: Any,
        scheduled_at: datetime,
        detail: str,
    ) -> dict[str, Any]:
        """Build feedback payload for patient same-time booking conflicts.

        Args:
            patient_id: Patient UUID.
            scheduled_at: Requested slot datetime.
            detail: Human-readable error message.

        Returns:
            dict[str, Any]: Conflict payload containing existing same-time bookings.
        """
        local_dt = timezone.localtime(scheduled_at)
        patient_conflicts = Appointment.objects.filter(
            patient_id=patient_id,
            scheduled_at=scheduled_at,
            status='booked',
        ).order_by('id')

        return {
            'detail': detail,
            'requested_slot': local_dt.isoformat(),
            'existing_bookings_at_slot': [
                {
                    'appointment_id': appt.id,
                    'doctor_id': str(appt.doctor_id),
                    'status': appt.status,
                }
                for appt in patient_conflicts
            ],
        }

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Run cross-field validation against schedule and conflict rules.

        Args:
            attrs: Incoming serializer attributes.

        Returns:
            dict[str, Any]: Validated attributes.

        Raises:
            serializers.ValidationError: If booking conflicts or schedule violations exist.
        """
        doctor_id = attrs.get('doctor_id')
        scheduled_at = attrs.get('scheduled_at')
        patient_id = attrs.get('patient_id') or getattr(self.instance, 'patient_id', None)

        request = self.context.get('request')
        if not patient_id and request and getattr(request.user, 'role', None) == 'patient':
            patient_id = request.user.pk

        if doctor_id and scheduled_at:
            from schedules.models import DoctorSchedule

            DoctorSchedule.deactivate_expired()
            local_dt = timezone.localtime(scheduled_at)
            schedule_date = local_dt.date()
            schedules = DoctorSchedule.objects.filter(
                doctor_id=doctor_id,
                schedule_date=schedule_date,
                is_active=True,
            ).order_by('start_time')
            if not schedules.exists():
                raise serializers.ValidationError(
                    self.build_slot_feedback(
                        doctor_id,
                        scheduled_at,
                        'Doctor is not available on the selected date.',
                    )
                )

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
                raise serializers.ValidationError(
                    self.build_slot_feedback(
                        doctor_id,
                        scheduled_at,
                        'Selected slot is outside the doctor\'s schedule for that day.',
                    )
                )

            if Appointment.objects.filter(doctor_id=doctor_id, scheduled_at=scheduled_at, status='booked').exists():
                raise serializers.ValidationError(
                    self.build_slot_feedback(
                        doctor_id,
                        scheduled_at,
                        'This slot is already booked.',
                    )
                )

            if patient_id:
                patient_conflicts = Appointment.objects.filter(
                    patient_id=patient_id,
                    scheduled_at=scheduled_at,
                    status='booked',
                )
                if self.instance is not None:
                    patient_conflicts = patient_conflicts.exclude(pk=self.instance.pk)

                if patient_conflicts.exists():
                    raise serializers.ValidationError(
                        self.build_patient_slot_conflict_feedback(
                            patient_id,
                            scheduled_at,
                            'You already have another booked appointment at this time.',
                        )
                    )
        return attrs
