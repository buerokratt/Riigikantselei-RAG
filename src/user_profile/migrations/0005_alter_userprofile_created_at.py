# Generated by Django 5.1rc1 on 2024-08-02 18:47

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('user_profile', '0004_remove_userprofile_used_cost_userprofile_created_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]