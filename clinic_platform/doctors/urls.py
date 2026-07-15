"""URL routes for doctor profile and availability APIs."""

from django.urls import path
from .views import DoctorListCreateView, DoctorDetailView, DoctorMeView
from bookings.views import DoctorAvailabilityView

urlpatterns = [
    path('', DoctorListCreateView.as_view(), name='doctor-list-create'),
    path('me/', DoctorMeView.as_view(), name='doctor-me'),
    path('<uuid:user_id>/', DoctorDetailView.as_view(), name='doctor-detail'),
    path('<uuid:user_id>/availability/', DoctorAvailabilityView.as_view(), name='doctor-availability'),
]
