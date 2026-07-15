"""API views for appointment booking, updates, and availability."""

from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, router, transaction
from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from .models import Appointment
from .serializers import AppointmentSerializer
from .cache_utils import invalidate_slots


class AppointmentCreateView(generics.CreateAPIView):
    """Create appointments for authenticated patients."""

    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer: AppointmentSerializer) -> None:
        """Create a booking inside an atomic transaction.

        Args:
            serializer: Appointment serializer instance.

        Raises:
            PermissionDenied: If caller is not a patient.
            ValidationError: If business validation or race conflicts occur.
        """
        if self.request.user.role != 'patient':
            raise PermissionDenied('Only patients can create appointments.')

        booking_db = router.db_for_write(Appointment)

        try:
            with transaction.atomic(using=booking_db):
                appointment = serializer.save(patient_id=self.request.user.pk)
                invalidate_slots(appointment.doctor_id, timezone.localtime(appointment.scheduled_at).date())
        except DjangoValidationError as exc:
            raise ValidationError(getattr(exc, 'message_dict', {'detail': exc.messages}))
        except IntegrityError:
            doctor_id = serializer.validated_data.get('doctor_id')
            scheduled_at = serializer.validated_data.get('scheduled_at')
            patient_id = self.request.user.pk

            doctor_slot_taken = Appointment.objects.filter(
                doctor_id=doctor_id,
                scheduled_at=scheduled_at,
                status='booked',
            ).exists()

            if doctor_slot_taken:
                raise ValidationError(
                    serializer.build_slot_feedback(
                        doctor_id,
                        scheduled_at,
                        'This slot was just booked. Please choose another slot.',
                    )
                )

            raise ValidationError(
                serializer.build_patient_slot_conflict_feedback(
                    patient_id,
                    scheduled_at,
                    'You already have another booked appointment at this time.',
                )
            )


class AppointmentCancelView(generics.UpdateAPIView):
    """Cancel an appointment for patient, doctor, or admin owner."""

    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_locked_appointment(self) -> tuple[Appointment, str]:
        """Return a row-locked appointment after access checks.

        Returns:
            tuple[Appointment, str]: Locked appointment and booking DB alias.

        Raises:
            PermissionDenied: If user is not allowed to mutate the appointment.
        """
        booking_db = router.db_for_write(Appointment)
        appointment = Appointment.objects.using(booking_db).select_for_update().get(pk=self.kwargs['pk'])
        request_user = self.request.user

        is_patient_owner = request_user.role == 'patient' and str(appointment.patient_id) == str(request_user.pk)
        is_doctor_owner = request_user.role == 'doctor' and str(appointment.doctor_id) == str(request_user.pk)
        is_admin = request_user.role == 'admin'

        if not (is_patient_owner or is_doctor_owner or is_admin):
            raise PermissionDenied('Only the booked patient, booked doctor, or an admin can cancel this appointment.')

        return appointment, booking_db

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Cancel an appointment.

        Args:
            request: DRF request with cancellation reason.
            *args: Positional view args.
            **kwargs: Keyword view args.

        Returns:
            Response: Serialized updated appointment payload.
        """
        booking_db = router.db_for_write(Appointment)
        with transaction.atomic(using=booking_db):
            appointment, _ = self.get_locked_appointment()
            if appointment.status == 'cancelled':
                raise ValidationError({'detail': 'Appointment is already cancelled.'})
            reason = request.data.get('reason')
            if not reason:
                raise ValidationError({'reason': 'Cancel reason is required.'})
            appointment.status = 'cancelled'
            appointment.reason = reason
            appointment.save(using=booking_db)
            invalidate_slots(appointment.doctor_id, timezone.localtime(appointment.scheduled_at).date())
            return Response(self.get_serializer(appointment).data)


class AppointmentRescheduleView(generics.UpdateAPIView):
    """Reschedule an appointment for authorized actors."""

    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_locked_appointment(self) -> tuple[Appointment, str]:
        """Return a row-locked appointment after permission checks.

        Returns:
            tuple[Appointment, str]: Locked appointment and booking DB alias.
        """
        booking_db = router.db_for_write(Appointment)
        appointment = Appointment.objects.using(booking_db).select_for_update().get(pk=self.kwargs['pk'])
        request_user = self.request.user

        is_patient_owner = request_user.role == 'patient' and str(appointment.patient_id) == str(request_user.pk)
        is_doctor_owner = request_user.role == 'doctor' and str(appointment.doctor_id) == str(request_user.pk)
        is_admin = request_user.role == 'admin'

        if not (is_patient_owner or is_doctor_owner or is_admin):
            raise PermissionDenied('Only the booked patient, booked doctor, or an admin can reschedule this appointment.')

        return appointment, booking_db

    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Reschedule an appointment to a new date-time slot.

        Args:
            request: DRF request containing ``scheduled_at``.
            *args: Positional view args.
            **kwargs: Keyword view args.

        Returns:
            Response: Serialized updated appointment payload.
        """
        booking_db = router.db_for_write(Appointment)
        with transaction.atomic(using=booking_db):
            appointment, _ = self.get_locked_appointment()
            previous_doctor_id = appointment.doctor_id
            previous_date = timezone.localtime(appointment.scheduled_at).date()
            if appointment.status == 'cancelled':
                raise ValidationError({'detail': 'Cannot reschedule a cancelled appointment.'})
            new_scheduled_at = request.data.get('scheduled_at')
            if not new_scheduled_at:
                raise ValidationError({'scheduled_at': 'New scheduled time is required.'})
            try:
                appointment.scheduled_at = timezone.make_aware(datetime.fromisoformat(new_scheduled_at))
            except ValueError:
                raise ValidationError({'scheduled_at': 'Date/time must be in ISO format.'})
            try:
                appointment.save(using=booking_db)
            except DjangoValidationError as exc:
                raise ValidationError(getattr(exc, 'message_dict', {'detail': exc.messages}))
            except IntegrityError:
                doctor_slot_taken = Appointment.objects.filter(
                    doctor_id=appointment.doctor_id,
                    scheduled_at=appointment.scheduled_at,
                    status='booked',
                ).exclude(pk=appointment.pk).exists()

                if doctor_slot_taken:
                    raise ValidationError({'scheduled_at': 'Target slot is no longer available.'})

                raise ValidationError({'scheduled_at': 'Patient already has an appointment at this time.'})
            invalidate_slots(previous_doctor_id, previous_date)
            invalidate_slots(appointment.doctor_id, timezone.localtime(appointment.scheduled_at).date())
            return Response(self.get_serializer(appointment).data)


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                name='sort',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Sort direction by date/time: asc or desc. Defaults to asc.",
            ),
            OpenApiParameter(
                name='ordering',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Alternative ordering style: scheduled_at or -scheduled_at.',
            ),
        ]
    )
)
class PatientAppointmentsView(generics.ListAPIView):
    """List upcoming booked appointments for a patient."""

    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _get_ordering(self) -> str:
        """Resolve supported ordering query options.

        Returns:
            str: ORM ordering value.

        Raises:
            ValidationError: If sort option is invalid.
        """
        ordering = self.request.query_params.get('ordering')
        if ordering in ('scheduled_at', '-scheduled_at'):
            return ordering

        sort = (self.request.query_params.get('sort') or 'asc').strip().lower()
        if sort in ('asc', 'oldest'):
            return 'scheduled_at'
        if sort in ('desc', 'latest', 'newest'):
            return '-scheduled_at'

        raise ValidationError({'sort': "Invalid sort value. Use 'asc' or 'desc'."})

    def get_queryset(self):
        """Build authorized patient appointment queryset."""
        request_user = self.request.user
        patient_id = self.kwargs.get('patient_id') or self.kwargs.get('user_id')

        if request_user.role == 'patient':
            if patient_id and str(patient_id) != str(request_user.pk):
                raise PermissionDenied('Patients can only view their own appointments.')
            patient_id = request_user.pk
        elif request_user.role != 'admin':
            raise PermissionDenied('Only patients or admins can view patient appointments.')

        return Appointment.objects.filter(
            patient_id=patient_id,
            status='booked',
            scheduled_at__gte=timezone.now(),
        ).order_by(self._get_ordering())


class MyPatientAppointmentsView(PatientAppointmentsView):
    """List authenticated patient's own upcoming appointments."""

    def get_queryset(self):
        """Return own appointments if caller is a patient."""
        if self.request.user.role != 'patient':
            raise PermissionDenied('Only patients can access this endpoint.')
        return super().get_queryset()


class DoctorAvailabilityView(generics.GenericAPIView):
    """Return available slots for a given doctor and date."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='date',
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description='Date to check doctor availability for, in YYYY-MM-DD format.',
            ),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'available_slots': {
                        'type': 'array',
                        'items': {'type': 'string'},
                    }
                },
            }
        },
    )
    def get(self, request: Request, doctor_id: str | None = None, user_id: str | None = None) -> Response:
        """Fetch available slots for a doctor.

        Args:
            request: DRF request with required ``date`` query parameter.
            doctor_id: Doctor UUID from path.
            user_id: Alias UUID from alternate route.

        Returns:
            Response: Object containing available slot date-times.
        """
        doctor_id = doctor_id or user_id
        date_str = request.query_params.get('date')
        if not date_str:
            raise ValidationError({'date': 'Date query parameter is required in YYYY-MM-DD format.'})
        try:
            date = datetime.fromisoformat(date_str).date()
        except ValueError:
            raise ValidationError({'date': 'Invalid date format. Use YYYY-MM-DD.'})
        slots = Appointment.get_available_slots(doctor_id, date)
        return Response({'available_slots': slots})
