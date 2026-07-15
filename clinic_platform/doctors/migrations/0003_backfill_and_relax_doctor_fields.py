from django.db import migrations, models


def backfill_doctors(apps, schema_editor):
    # Multi-table inheritance child rows must be inserted directly.
    # Using Doctor.objects.get_or_create() may reinsert into parent users table.
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO doctor_profile (user_ptr_id, speciality, work_start_time, work_end_time)
            SELECT u.user_id, '', '08:00:00'::time, '17:00:00'::time
            FROM users_accounts u
            WHERE u.role = 'doctor'
            ON CONFLICT (user_ptr_id) DO NOTHING
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0002_doctor_work_end_time_doctor_work_start_time'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='doctor',
            name='speciality',
            field=models.CharField(blank=True, default='', help_text='Speciality of the doctor.', max_length=100),
        ),
        migrations.RunPython(backfill_doctors, migrations.RunPython.noop),
    ]
