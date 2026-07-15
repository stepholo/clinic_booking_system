"""Signals for maintaining doctor profile child rows."""

from typing import Any

from django.db import connections
from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import User
from .models import Doctor


@receiver(post_save, sender=User)
def ensure_doctor_profile(sender: type[User], instance: User, **kwargs: Any) -> None:
    """Ensure a doctor child-table row exists for doctor-role users.

    Args:
        sender: Signal sender class.
        instance: User model instance saved.
        **kwargs: Signal keyword arguments.
    """
    if instance.role != 'doctor':
        return

    if isinstance(instance, Doctor):
        return

    db_alias = instance._state.db or 'default'
    table_name = Doctor._meta.db_table

    # Multi-table inheritance child creation via ORM can reinsert the parent row.
    # Insert directly into child table to avoid unique collisions on parent fields.
    with connections[db_alias].cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {table_name} (user_ptr_id, speciality, work_start_time, work_end_time)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_ptr_id) DO NOTHING
            """,
            [str(instance.pk), '', '08:00:00', '17:00:00'],
        )
