"""Project-level views for public entrypoints."""

from django.conf import settings
from django.db import connections
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render


def home(request: HttpRequest):
    """Return an API index page for interactive discovery.

    Args:
        request: Incoming HTTP request.

    Returns:
        HttpResponse | JsonResponse: HTML page by default, JSON when requested.
    """
    links = {
        'admin': request.build_absolute_uri('/admin/'),
        'swagger': request.build_absolute_uri('/api/docs/'),
        'schema': request.build_absolute_uri('/api/schema/'),
        'redoc': request.build_absolute_uri('/api/redoc/'),
        'users_api': request.build_absolute_uri('/api/users/'),
        'doctors_api': request.build_absolute_uri('/api/doctors/'),
        'patients_api': request.build_absolute_uri('/api/patients/'),
        'schedules_api': request.build_absolute_uri('/api/schedules/'),
        'appointments_api': request.build_absolute_uri('/api/appointments/'),
    }

    usage = {
        'step_1': 'Open /api/docs/ for interactive Swagger docs.',
        'step_2': 'Create an account and obtain JWT tokens from user auth endpoints.',
        'step_3': 'Click Authorize in Swagger and set Bearer <access_token>.',
        'step_4': 'Call protected endpoints under users, doctors, patients, schedules, and appointments.',
    }

    def db_ok(alias: str) -> bool:
        try:
            connections[alias].ensure_connection()
            return True
        except Exception:
            return False

    status = {
        'api_version': settings.SPECTACULAR_SETTINGS.get('VERSION', 'unknown'),
        'redis_mode': 'enabled' if getattr(settings, 'USE_REDIS_CACHE', False) else 'disabled',
        'user_db': 'connected' if db_ok('user_db') else 'disconnected',
        'booking_db': 'connected' if db_ok('booking_db') else 'disconnected',
    }

    payload = {
        'service': 'CareConnect Clinic Booking API',
        'message': 'Welcome. Use the links below to explore and test the API.',
        'links': links,
        'quick_start': usage,
        'status': status,
    }

    if request.GET.get('format') == 'json':
        return JsonResponse(payload)

    return render(request, 'home.html', payload)
