"""Cache key utilities for appointment availability data."""

from __future__ import annotations

from datetime import date
import logging
from uuid import UUID

from django.core.cache import cache


logger = logging.getLogger(__name__)


def _safe_cache_get(key: str):
    """Read cache value without surfacing backend/network errors."""
    try:
        return cache.get(key)
    except Exception as exc:
        logger.warning("Cache get failed for key %s; continuing without cache: %s", key, exc)
        return None


def _safe_cache_set(key: str, value, timeout) -> None:
    """Write cache value without surfacing backend/network errors."""
    try:
        cache.set(key, value, timeout)
    except Exception as exc:
        logger.warning("Cache set failed for key %s; continuing without cache: %s", key, exc)


def _version_key(doctor_id: UUID | str, day: date) -> str:
    """Build cache key that tracks availability version for a doctor-date.

    Args:
        doctor_id: Doctor UUID.
        day: Date for availability scope.

    Returns:
        str: Cache key for doctor-date version state.
    """
    return f"availability:version:{doctor_id}:{day.isoformat()}"


def _slots_key(doctor_id: UUID | str, day: date, version: int) -> str:
    """Build cache key for resolved availability slots payload.

    Args:
        doctor_id: Doctor UUID.
        day: Date for availability scope.
        version: Active version for this doctor-date.

    Returns:
        str: Cache key for slot list payload.
    """
    return f"availability:slots:{doctor_id}:{day.isoformat()}:v{version}"


def get_or_init_version(doctor_id: UUID | str, day: date) -> int:
    """Get an availability version counter, initializing when absent.

    Args:
        doctor_id: Doctor UUID.
        day: Date for availability scope.

    Returns:
        int: Current version counter.
    """
    key = _version_key(doctor_id, day)
    version = _safe_cache_get(key)
    if version is None:
        _safe_cache_set(key, 1, None)
        return 1
    return int(version)


def get_slots(doctor_id: UUID | str, day: date) -> list[str] | None:
    """Fetch cached slots payload for a doctor-date.

    Args:
        doctor_id: Doctor UUID.
        day: Date for availability scope.

    Returns:
        list[str] | None: Cached slots list or ``None`` when missing.
    """
    version = get_or_init_version(doctor_id, day)
    return _safe_cache_get(_slots_key(doctor_id, day, version))


def set_slots(doctor_id: UUID | str, day: date, slots: list[str], ttl_seconds: int) -> None:
    """Store slots payload in cache for a doctor-date version.

    Args:
        doctor_id: Doctor UUID.
        day: Date for availability scope.
        slots: Availability slot payload.
        ttl_seconds: Cache TTL in seconds.
    """
    version = get_or_init_version(doctor_id, day)
    _safe_cache_set(_slots_key(doctor_id, day, version), slots, ttl_seconds)


def invalidate_slots(doctor_id: UUID | str, day: date) -> None:
    """Bump doctor-date version to invalidate existing slots cache.

    Args:
        doctor_id: Doctor UUID.
        day: Date for availability scope.
    """
    key = _version_key(doctor_id, day)
    version = _safe_cache_get(key)
    if version is None:
        _safe_cache_set(key, 2, None)
        return
    _safe_cache_set(key, int(version) + 1, None)
