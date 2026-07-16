"""Serializers for doctor schedule CRUD and overlap validation."""

from typing import Any

from rest_framework import serializers

from .models import DoctorSchedule


class DoctorScheduleSerializer(serializers.ModelSerializer):
    """Serialize doctor schedule blocks with overlap protection rules."""

    class Meta:
        model = DoctorSchedule
        fields = (
            'id',
            'doctor',
            'schedule_date',
            'start_time',
            'end_time',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'doctor', 'created_at', 'updated_at')

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate schedule boundaries and same-day overlaps.

        Args:
            attrs: Candidate serializer values.

        Returns:
            dict[str, Any]: Validated schedule attributes.

        Raises:
            serializers.ValidationError: If boundaries or overlaps are invalid.
        """
        request = self.context.get('request')

        if self.instance is not None:
            doctor_id = self.instance.doctor_id
            schedule_date = attrs.get('schedule_date', self.instance.schedule_date)
        else:
            if request and getattr(request.user, 'role', None) == 'doctor':
                doctor_id = request.user.pk
            else:
                doctor_id = self.initial_data.get('doctor')
            schedule_date = attrs.get('schedule_date')

        start_time = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end_time = attrs.get('end_time', getattr(self.instance, 'end_time', None))
        is_active = attrs.get('is_active', getattr(self.instance, 'is_active', True))

        if start_time:
            start_time = start_time.replace(second=0, microsecond=0)
            if start_time.minute not in (0, 30):
                raise serializers.ValidationError({'start_time': 'Start time must be on a 30-minute boundary (HH:00 or HH:30).'})
            attrs['start_time'] = start_time

        if end_time:
            end_time = end_time.replace(second=0, microsecond=0)
            if end_time.minute not in (0, 30):
                raise serializers.ValidationError({'end_time': 'End time must be on a 30-minute boundary (HH:00 or HH:30).'})
            attrs['end_time'] = end_time

        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({'end_time': 'End time must be later than start time.'})

        if doctor_id and schedule_date and start_time and end_time and is_active:
            overlap_qs = DoctorSchedule.objects.filter(
                doctor_id=doctor_id,
                schedule_date=schedule_date,
                is_active=True,
                start_time__lt=end_time,
                end_time__gt=start_time,
            )
            if self.instance is not None:
                overlap_qs = overlap_qs.exclude(pk=self.instance.pk)
            if overlap_qs.exists():
                raise serializers.ValidationError({'detail': 'Schedule block overlaps with an existing active block for this day.'})

        return attrs
