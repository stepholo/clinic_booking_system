FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=clinic_platform.settings

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY clinic_platform/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY clinic_platform /app/clinic_platform
WORKDIR /app/clinic_platform

CMD ["sh", "-c", "python manage.py collectstatic --noinput && gunicorn clinic_platform.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
