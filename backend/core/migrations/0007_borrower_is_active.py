from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_four_decimal_places"),
    ]

    operations = [
        migrations.AddField(
            model_name="borrower",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]
