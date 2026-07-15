from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Appointment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scheduled_at', models.DateTimeField()),
                ('status', models.CharField(choices=[('booked', 'Booked'), ('cancelled', 'Cancelled')], default='booked', max_length=20)),
                ('reason', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('doctor_id', models.UUIDField()),
                ('patient_id', models.UUIDField()),
            ],
            options={
                'db_table': 'appointments',
                'ordering': ['scheduled_at'],
                'constraints': [models.UniqueConstraint(condition=models.Q(status='booked'), fields=('doctor_id', 'scheduled_at'), name='unique_doctor_slot_when_booked')],
            },
        ),
    ]
