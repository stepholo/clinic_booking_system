"""Serializers for doctor profile and schedule payloads."""

from typing import Any

from rest_framework import serializers
from django.utils import timezone

from .models import Doctor


class DoctorSerializer(serializers.ModelSerializer):
    """Serialize doctor details and schedule slot status summaries."""

    full_name = serializers.SerializerMethodField(read_only=True)
    schedules = serializers.SerializerMethodField(read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password2 = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Doctor
        fields = (
            'user_id',
            'first_name',
            'last_name',
            'full_name',
            'username',
            'email',
            'phone_number',
            'role',
            'speciality',
            'schedules',
            'password',
            'password2',
        )
        read_only_fields = ('user_id', 'role')
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'username': {'required': True},
            'email': {'required': True},
            'phone_number': {'required': True},
            'speciality': {'required': True},
        }

    def get_full_name(self, obj: Doctor) -> str:
        """Compose a display-friendly doctor full name.

        Args:
            obj: Doctor model instance.

        Returns:
            str: Combined first and last name.
        """
        return f"{obj.first_name} {obj.last_name}"

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate password confirmation fields when provided.

        Args:
            attrs: Candidate serializer attributes.

        Returns:
            dict[str, Any]: Final validated attributes.
        """
        password = attrs.get('password')
        password2 = attrs.get('password2')

        if password or password2:
            if password != password2:
                raise serializers.ValidationError({'password': "Password fields didn't match."})

        return attrs

    def create(self, validated_data: dict[str, Any]) -> Doctor:
        """Create a doctor profile and optional password.

        Args:
            validated_data: Validated serializer data.

        Returns:
            Doctor: Newly created doctor profile.
        """
        validated_data.pop('password2', None)
        password = validated_data.pop('password', None)
        validated_data['role'] = 'doctor'
        doctor = Doctor(**validated_data)
        if password:
            doctor.set_password(password)
        doctor.save()
        return doctor

    def update(self, instance: Doctor, validated_data: dict[str, Any]) -> Doctor:
        """Update doctor profile fields and optional password.

        Args:
            instance: Existing doctor instance.
            validated_data: Incoming validated fields.

        Returns:
            Doctor: Updated doctor instance.
        """
        validated_data.pop('password2', None)
        password = validated_data.pop('password', None)
        doctor = super().update(instance, validated_data)
        if password:
            doctor.set_password(password)
            doctor.save()
        return doctor

    def validate_role(self, value: str) -> str:
        """Ensure role remains doctor for doctor serializer payloads.

        Args:
            value: Candidate role value.

        Returns:
            str: Validated role value.
        """
        if value != 'doctor':
            raise serializers.ValidationError('Role must be doctor for doctor profiles.')
        return value

    def validate_phone_number(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError('Phone number must contain only digits.')
        if len(value) != 10:
            raise serializers.ValidationError('Phone number must be exactly 10 digits.')
        return value

    def get_schedules(self, obj: Doctor) -> list[dict[str, Any]]:
        """Return active schedules with per-slot booking status.

        Args:
            obj: Doctor model instance.

        Returns:
            list[dict[str, Any]]: Active schedule blocks with slot status entries.
        """
        from schedules.serializers import DoctorScheduleSerializer
        from schedules.models import DoctorSchedule
        from bookings.models import Appointment

        DoctorSchedule.deactivate_expired()
        schedules = obj.schedules.filter(is_active=True).order_by('schedule_date', 'start_time')
        serialized_schedules = DoctorScheduleSerializer(schedules, many=True).data

        if not schedules.exists():
            return serialized_schedules

        schedule_dates = {schedule.schedule_date for schedule in schedules}
        booked_appointments = Appointment.objects.filter(
            doctor_id=obj.user_id,
            status='booked',
            scheduled_at__date__in=schedule_dates,
        ).values_list('scheduled_at', flat=True)

        booked_slots = {
            timezone.localtime(appointment_dt).replace(second=0, microsecond=0)
            for appointment_dt in booked_appointments
        }

        for schedule_data, schedule_obj in zip(serialized_schedules, schedules):
            current = timezone.make_aware(
                timezone.datetime.combine(schedule_obj.schedule_date, schedule_obj.start_time)
            )
            end_slot = timezone.make_aware(
                timezone.datetime.combine(schedule_obj.schedule_date, schedule_obj.end_time)
            )

            slots = []
            while current + timezone.timedelta(minutes=30) <= end_slot:
                normalized_slot = current.replace(second=0, microsecond=0)
                slots.append(
                    {
                        'slot': normalized_slot.isoformat(),
                        'status': 'booked' if normalized_slot in booked_slots else 'available',
                    }
                )
                current += timezone.timedelta(minutes=30)

            schedule_data['slots'] = slots

        return serialized_schedules
