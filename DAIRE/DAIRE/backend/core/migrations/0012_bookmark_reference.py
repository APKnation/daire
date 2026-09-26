# Placeholder migration to force Makemigrations to emit next numbered migration

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_numeric_ids"),
    ]

    operations = []
