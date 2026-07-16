"""URL routes for doctor schedule APIs."""

from django.urls import path
from .views import DoctorScheduleListCreateView, DoctorScheduleDetailView

urlpatterns = [
    path('', DoctorScheduleListCreateView.as_view(), name='schedule-list-create'),
    path('<int:pk>/', DoctorScheduleDetailView.as_view(), name='schedule-detail'),
]
