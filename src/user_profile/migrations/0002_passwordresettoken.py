# Generated by Django 5.0.6 on 2024-06-11 22:17

import django.db.models.deletion
import rest_framework.authtoken.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('user_profile', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PasswordResetToken',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                (
                    'key',
                    models.CharField(
                        default=rest_framework.authtoken.models.Token.generate_key, max_length=50
                    ),
                ),
                (
                    'auth_user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
    ]
