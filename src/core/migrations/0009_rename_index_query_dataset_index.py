# Generated by Django 5.0.7 on 2024-07-19 08:28

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0008_dataset'),
    ]

    operations = [
        migrations.RenameField(
            model_name='dataset',
            old_name='index_query',
            new_name='index',
        ),
    ]