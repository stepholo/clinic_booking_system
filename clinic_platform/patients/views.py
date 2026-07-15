"""API views for patient CRUD operations."""

from typing import Any

from rest_framework import generics, permissions
from rest_framework.request import Request

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from .models import Patient
from .serializers import PatientSerializer


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                name='bookings',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Booking scope in nested patient response: all or upcoming. Defaults to all.",
            ),
        ]
    )
)
class PatientListCreateView(generics.ListCreateAPIView):
    """List patient profiles and create new patient accounts."""

    queryset = Patient.objects.filter(role='patient')
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer: PatientSerializer) -> None:
        """Persist a newly created patient with the patient role.

        Args:
            serializer: Patient serializer instance.
        """
        serializer.save(role='patient')


class PatientDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a patient profile by UUID."""

    queryset = Patient.objects.filter(role='patient')
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'user_id'

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='bookings',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Booking scope in nested patient response: all or upcoming. Defaults to all.",
            ),
        ]
    )
    def get(self, request: Request, *args: Any, **kwargs: Any):
        """Return a patient detail response.

        Args:
            request: DRF request.
            *args: Positional view args.
            **kwargs: Keyword view args.

        Returns:
            Response: Serialized patient payload.
        """
        return super().get(request, *args, **kwargs)
