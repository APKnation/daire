from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_borrower_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="lender",
            name="api_key_hash",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="lender",
            name="api_key_prefix",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
    ]
