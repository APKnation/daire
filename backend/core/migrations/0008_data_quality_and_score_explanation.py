from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_borrower_is_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="borrower",
            name="data_conflicts",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="assessment",
            name="score_explanation",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="assessment",
            name="score_inputs",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="dataexchange",
            name="batch_reference",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
