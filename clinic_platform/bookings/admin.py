from django.contrib import admin
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('doctor_id', 'patient_id', 'scheduled_at', 'status', 'created_at')
    list_filter = ('status', 'scheduled_at')
    search_fields = ('doctor_id', 'patient_id', 'reason')
