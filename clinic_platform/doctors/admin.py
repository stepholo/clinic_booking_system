from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone

from bookings.models import Appointment
from .models import Doctor


@admin.register(Doctor)
class DoctorAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'speciality')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'speciality',
        'available_slots_today',
        'is_staff',
    )
    search_fields = ('username', 'email', 'first_name', 'last_name', 'speciality')
    ordering = ('username',)

    @admin.display(description='Available slots today')
    def available_slots_today(self, obj):
        today = timezone.localdate()
        return len(Appointment.get_available_slots(obj.pk, today))
