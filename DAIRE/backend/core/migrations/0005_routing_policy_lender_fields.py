from django.db import migrations, models


def set_default_lender_fields(apps, schema_editor):
    Policy = apps.get_model("core", "DataRoutingPolicy")
    Policy.objects.filter(policy_id="DEFAULT-CREDIT-ROUTING").update(lender_fields=[
        "borrower_reference", "customer_id", "age", "gender", "employment_status", "income",
        "business_information", "account_information", "account_reference", "account_name",
        "transaction_frequency", "income_frequency", "savings", "cash_flow_patterns",
        "account_activity", "loans",
    ])


class Migration(migrations.Migration):
    dependencies = [("core", "0004_data_routing_and_exchange")]

    operations = [
        migrations.AddField(
            model_name="dataroutingpolicy",
            name="lender_fields",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(set_default_lender_fields, migrations.RunPython.noop),
    ]
