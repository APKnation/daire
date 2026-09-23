from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_lender_api_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="lender",
            name="broadcast_api_key",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
    ]
