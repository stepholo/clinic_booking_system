"""Signals for maintaining patient profile child rows."""

from typing import Any

from django.db import connections
from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import User
from .models import Patient


@receiver(post_save, sender=User)
def ensure_patient_profile(sender: type[User], instance: User, **kwargs: Any) -> None:
    """Ensure a patient child-table row exists for patient-role users.

    Args:
        sender: Signal sender class.
        instance: User model instance saved.
        **kwargs: Signal keyword arguments.
    """
    if instance.role != 'patient':
        return

    if isinstance(instance, Patient):
        return

    db_alias = instance._state.db or 'default'
    table_name = Patient._meta.db_table

    # Multi-table inheritance child creation via ORM can reinsert the parent row.
    # Insert directly into child table to avoid unique collisions on parent fields.
    with connections[db_alias].cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {table_name} (user_ptr_id, county, location)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_ptr_id) DO NOTHING
            """,
            [str(instance.pk), '', ''],
        )
