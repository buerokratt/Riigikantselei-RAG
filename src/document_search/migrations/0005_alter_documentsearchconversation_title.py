# Generated by Django 5.0.7 on 2024-07-31 13:01

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('document_search', '0004_documentsearchqueryresult_is_context_pruned'),
    ]

    operations = [
        migrations.AlterField(
            model_name='documentsearchconversation',
            name='title',
            field=models.TextField(default=''),
        ),
    ]