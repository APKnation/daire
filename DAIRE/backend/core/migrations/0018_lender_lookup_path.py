from django.db import migrations, models


def set_live_lender_lookup_path(apps, schema_editor):
    """The live NMB lender backend (.70:8002) serves the borrower lookup at
    /api/daire/borrowers/, not the documented /borrowers default."""
    Lender = apps.get_model("core", "Lender")
    Lender.objects.filter(lender_id="1200").update(lookup_path="api/daire/borrowers/")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_loanapplication"),
    ]

    operations = [
        migrations.AddField(
            model_name="lender",
            name="lookup_path",
            field=models.CharField(blank=True, default="borrowers", max_length=255),
        ),
        migrations.RunPython(set_live_lender_lookup_path, migrations.RunPython.noop),
    ]
