#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/clinic_platform"

exec gunicorn clinic_platform.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
