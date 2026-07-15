"""API views for doctor profile management."""

from typing import Any

from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied

from .models import Doctor
from .serializers import DoctorSerializer


class DoctorListCreateView(generics.ListCreateAPIView):
    """List all doctors or create a doctor profile."""

    queryset = Doctor.objects.filter(role='doctor')
    serializer_class = DoctorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer: DoctorSerializer) -> None:
        """Persist new doctor with fixed doctor role.

        Args:
            serializer: Doctor serializer instance.
        """
        serializer.save(role='doctor')


class DoctorDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a doctor by UUID."""

    queryset = Doctor.objects.filter(role='doctor')
    serializer_class = DoctorSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'user_id'


class DoctorMeView(generics.RetrieveUpdateAPIView):
    """Retrieve or update the authenticated doctor's profile."""

    serializer_class = DoctorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self) -> Doctor:
        """Return authenticated doctor profile.

        Returns:
            Doctor: Doctor record for current user.

        Raises:
            PermissionDenied: If current user is not a doctor or profile is missing.
        """
        if self.request.user.role != 'doctor':
            raise PermissionDenied('Only doctors can access this endpoint.')

        try:
            return Doctor.objects.get(pk=self.request.user.pk)
        except Doctor.DoesNotExist:
            raise PermissionDenied('Doctor profile not found.')
