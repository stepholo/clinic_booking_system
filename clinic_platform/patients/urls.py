"""URL routes for patient profile, bookings, and availability APIs."""

from django.urls import path
from .views import PatientListCreateView, PatientDetailView
from bookings.views import DoctorAvailabilityView, MyPatientAppointmentsView, PatientAppointmentsView

urlpatterns = [
    path('', PatientListCreateView.as_view(), name='patient-list-create'),
    path('<uuid:user_id>/', PatientDetailView.as_view(), name='patient-detail'),
    path('me/appointments/', MyPatientAppointmentsView.as_view(), name='my-patient-appointments'),
    path('doctors/<uuid:doctor_id>/availability/', DoctorAvailabilityView.as_view(), name='patient-doctor-availability'),
    path('<uuid:user_id>/appointments/', PatientAppointmentsView.as_view(), name='patient-appointments'),
]
