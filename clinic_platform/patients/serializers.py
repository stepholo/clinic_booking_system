"""Serializers for patient profile operations."""

from typing import Any

from rest_framework import serializers
from django.utils import timezone

from .models import Patient


class PatientSerializer(serializers.ModelSerializer):
    """Serialize patient profiles and nested booking summaries."""

    full_name = serializers.SerializerMethodField(read_only=True)
    bookings = serializers.SerializerMethodField(read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password2 = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Patient
        fields = (
            'user_id',
            'first_name',
            'last_name',
            'full_name',
            'username',
            'email',
            'phone_number',
            'role',
            'county',
            'location',
            'bookings',
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
            'county': {'required': True},
            'location': {'required': True},
        }

    def get_full_name(self, obj: Patient) -> str:
        """Compose a display-friendly patient full name.

        Args:
            obj: Patient model instance.

        Returns:
            str: Combined first and last name.
        """
        return f"{obj.first_name} {obj.last_name}"

    def get_bookings(self, obj: Patient) -> list[dict[str, Any]]:
        """Return patient bookings, optionally filtered by query scope.

        Args:
            obj: Patient model instance.

        Returns:
            list[dict[str, Any]]: Serialized appointment entries.
        """
        from bookings.models import Appointment
        from bookings.serializers import AppointmentSerializer

        request = self.context.get('request')
        bookings_scope = 'all'
        if request:
            bookings_scope = (request.query_params.get('bookings') or 'all').strip().lower()

        if bookings_scope not in ('all', 'upcoming'):
            raise serializers.ValidationError({'bookings': "Invalid value. Use 'all' or 'upcoming'."})

        appointments = Appointment.objects.filter(patient_id=obj.user_id)
        if bookings_scope == 'upcoming':
            appointments = appointments.filter(status='booked', scheduled_at__gte=timezone.now())

        appointments = appointments.order_by('scheduled_at')
        return AppointmentSerializer(appointments, many=True).data

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate cross-field serializer constraints.

        Args:
            attrs: Candidate validated attributes.

        Returns:
            dict[str, Any]: Final validated attribute mapping.
        """
        password = attrs.get('password')
        password2 = attrs.get('password2')

        if password or password2:
            if password != password2:
                raise serializers.ValidationError({'password': "Password fields didn't match."})

        return attrs

    def create(self, validated_data: dict[str, Any]) -> Patient:
        """Create a patient profile with optional password.

        Args:
            validated_data: Validated serializer payload.

        Returns:
            Patient: Newly created patient profile.
        """
        validated_data.pop('password2', None)
        password = validated_data.pop('password', None)
        validated_data['role'] = 'patient'
        patient = Patient(**validated_data)
        if password:
            patient.set_password(password)
        patient.save()
        return patient

    def update(self, instance: Patient, validated_data: dict[str, Any]) -> Patient:
        """Update patient profile fields and optional password.

        Args:
            instance: Existing patient instance.
            validated_data: Incoming validated fields.

        Returns:
            Patient: Updated patient instance.
        """
        validated_data.pop('password2', None)
        password = validated_data.pop('password', None)
        patient = super().update(instance, validated_data)
        if password:
            patient.set_password(password)
            patient.save()
        return patient

    def validate_phone_number(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError('Phone number must contain only digits.')
        if len(value) != 10:
            raise serializers.ValidationError('Phone number must be exactly 10 digits.')
        return value
