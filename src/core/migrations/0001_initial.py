# Generated by Django 5.0.6 on 2024-05-31 10:36

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='CoreVariable',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                ('name', models.CharField(max_length=100)),
                ('value', models.TextField(default=None, null=True)),
            ],
        ),
    ]
