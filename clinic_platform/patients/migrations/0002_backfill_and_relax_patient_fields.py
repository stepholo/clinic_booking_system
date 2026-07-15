from django.db import migrations, models


def backfill_patients(apps, schema_editor):
    # Multi-table inheritance child rows must be inserted directly.
    # Using Patient.objects.get_or_create() may reinsert into parent users table.
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO patient_profile (user_ptr_id, county, location)
            SELECT u.user_id, '', ''
            FROM users_accounts u
            WHERE u.role = 'patient'
            ON CONFLICT (user_ptr_id) DO NOTHING
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patient',
            name='county',
            field=models.CharField(blank=True, default='', help_text='County where the patient lives.', max_length=100),
        ),
        migrations.AlterField(
            model_name='patient',
            name='location',
            field=models.CharField(blank=True, default='', help_text='Specific location or neighbourhood of the patient.', max_length=100),
        ),
        migrations.RunPython(backfill_patients, migrations.RunPython.noop),
    ]
