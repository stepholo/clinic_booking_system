from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Patient


@admin.register(Patient)
class PatientAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'county', 'location')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'county', 'location', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'county', 'location')
    ordering = ('username',)
