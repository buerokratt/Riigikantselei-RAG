# Generated by Django 5.0.7 on 2024-07-23 09:50

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('document_search', '0003_documentsearchconversation_max_year_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentsearchqueryresult',
            name='is_context_pruned',
            field=models.BooleanField(default=False),
        ),
    ]
