from django.contrib import admin
from .models import DoctorSchedule


@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'schedule_date', 'start_time', 'end_time', 'is_active')
    list_filter = ('schedule_date', 'is_active')
    search_fields = ('doctor__first_name', 'doctor__last_name', 'doctor__username')
    ordering = ('schedule_date', 'start_time')
