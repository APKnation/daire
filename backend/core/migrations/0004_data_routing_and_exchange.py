from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0003_unified_borrower_data")]

    operations = [
        migrations.CreateModel(
            name="DataRoutingPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("policy_id", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("ai_fields", models.JSONField(blank=True, default=list)),
                ("blockchain_fields", models.JSONField(blank=True, default=list)),
                ("active", models.BooleanField(default=True)),
                ("version", models.CharField(default="1", max_length=64)),
            ],
        ),
        migrations.CreateModel(
            name="DataExchange",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("system", models.CharField(choices=[("LENDER", "Lender"), ("AI", "Ai"), ("BLOCKCHAIN", "Blockchain")], max_length=20)),
                ("direction", models.CharField(choices=[("PUSH", "Push"), ("PULL", "Pull")], max_length=10)),
                ("operation", models.CharField(max_length=100)),
                ("status", models.CharField(choices=[("STARTED", "Started"), ("COMPLETED", "Completed"), ("FAILED", "Failed")], default="STARTED", max_length=10)),
                ("fields_sent", models.JSONField(blank=True, default=list)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("response", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("assessment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="data_exchanges", to="core.assessment")),
                ("borrower", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="data_exchanges", to="core.borrower")),
                ("lender", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="data_exchanges", to="core.lender")),
                ("policy", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="data_exchanges", to="core.dataroutingpolicy")),
            ],
        ),
    ]
