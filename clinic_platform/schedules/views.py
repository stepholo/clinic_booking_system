"""API views for doctor schedule management."""

from typing import Any

from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied

from .models import DoctorSchedule
from .serializers import DoctorScheduleSerializer
from doctors.models import Doctor
from bookings.cache_utils import invalidate_slots


class DoctorScheduleListCreateView(generics.ListCreateAPIView):
    """List active schedules and create new schedule blocks."""

    serializer_class = DoctorScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Build a role-scoped active schedule queryset.

        Returns:
            QuerySet: Filtered schedule records based on actor and query params.

        Raises:
            PermissionDenied: If caller is neither doctor nor admin.
        """
        user = self.request.user
        DoctorSchedule.deactivate_expired()
        queryset = DoctorSchedule.objects.select_related('doctor').filter(is_active=True)
        doctor_id = self.request.query_params.get('doctor_id')
        schedule_date = self.request.query_params.get('date')

        if user.role == 'doctor':
            queryset = queryset.filter(doctor_id=user.pk)
        elif user.role != 'admin':
            raise PermissionDenied('Only doctors or admins can view schedules.')

        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)
        if schedule_date:
            queryset = queryset.filter(schedule_date=schedule_date)
        return queryset

    def perform_create(self, serializer: DoctorScheduleSerializer) -> None:
        """Create a schedule block for doctor or admin context.

        Args:
            serializer: Schedule serializer instance.

        Raises:
            PermissionDenied: If role or doctor context is invalid.
        """
        user = self.request.user
        if user.role == 'doctor':
            try:
                doctor = Doctor.objects.get(pk=user.pk)
            except Doctor.DoesNotExist:
                raise PermissionDenied('Doctor profile not found. Please complete doctor profile setup.')
            schedule = serializer.save(doctor=doctor)
            invalidate_slots(schedule.doctor_id, schedule.schedule_date)
            return
        if user.role == 'admin':
            doctor_id = self.request.data.get('doctor')
            if not doctor_id:
                raise PermissionDenied('Admin must provide doctor when creating a schedule.')
            try:
                doctor = Doctor.objects.get(pk=doctor_id)
            except Doctor.DoesNotExist:
                raise PermissionDenied('Doctor not found for the provided id.')
            schedule = serializer.save(doctor=doctor)
            invalidate_slots(schedule.doctor_id, schedule.schedule_date)
            return
        raise PermissionDenied('Only doctors or admins can create schedules.')


class DoctorScheduleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a single active schedule block."""

    serializer_class = DoctorScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Build role-scoped queryset for schedule detail endpoints.

        Returns:
            QuerySet: Actor-filtered schedule queryset.

        Raises:
            PermissionDenied: If caller is neither doctor nor admin.
        """
        user = self.request.user
        DoctorSchedule.deactivate_expired()
        queryset = DoctorSchedule.objects.select_related('doctor').filter(is_active=True)
        if user.role == 'doctor':
            return queryset.filter(doctor_id=user.pk)
        if user.role == 'admin':
            return queryset
        raise PermissionDenied('Only doctors or admins can access schedules.')

    def perform_update(self, serializer: DoctorScheduleSerializer) -> None:
        """Update a schedule block and invalidate related availability cache."""
        existing = self.get_object()
        old_doctor_id = existing.doctor_id
        old_date = existing.schedule_date

        updated = serializer.save()
        invalidate_slots(old_doctor_id, old_date)
        invalidate_slots(updated.doctor_id, updated.schedule_date)

    def perform_destroy(self, instance: DoctorSchedule) -> None:
        """Delete a schedule block and invalidate related availability cache."""
        invalidate_slots(instance.doctor_id, instance.schedule_date)
        instance.delete()
