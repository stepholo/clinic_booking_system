"""URL routes for appointment and availability APIs."""

from django.urls import path
from .views import (
    AppointmentCreateView,
    AppointmentCancelView,
    AppointmentRescheduleView,
    PatientAppointmentsView,
    DoctorAvailabilityView,
)

urlpatterns = [
    path('', AppointmentCreateView.as_view(), name='appointment-create'),
    path('<int:pk>/cancel/', AppointmentCancelView.as_view(), name='appointment-cancel'),
    path('<int:pk>/reschedule/', AppointmentRescheduleView.as_view(), name='appointment-reschedule'),
    path('patients/<uuid:patient_id>/', PatientAppointmentsView.as_view(), name='patient-appointments'),
    path('doctors/<uuid:doctor_id>/availability/', DoctorAvailabilityView.as_view(), name='doctor-availability'),
]
