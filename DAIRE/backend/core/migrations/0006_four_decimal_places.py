from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0005_routing_policy_lender_fields")]

    operations = [
        migrations.AlterField(model_name="borrower", name="income", field=models.DecimalField(blank=True, decimal_places=4, max_digits=16, null=True)),
        migrations.AlterField(model_name="borrowerloan", name="loan_amount", field=models.DecimalField(decimal_places=4, default=0, max_digits=18)),
        migrations.AlterField(model_name="borrowerloan", name="outstanding_balance", field=models.DecimalField(decimal_places=4, default=0, max_digits=18)),
        migrations.AlterField(model_name="repaymentrecord", name="repayment_amount", field=models.DecimalField(decimal_places=4, default=0, max_digits=18)),
        migrations.AlterField(model_name="borrowerfinancialprofile", name="savings", field=models.DecimalField(decimal_places=4, default=0, max_digits=18)),
        migrations.AlterField(model_name="borrowerfinancialprofile", name="total_outstanding_debt", field=models.DecimalField(decimal_places=4, default=0, max_digits=18)),
        migrations.AlterField(model_name="borrowerfinancialprofile", name="monthly_repayment", field=models.DecimalField(decimal_places=4, default=0, max_digits=18)),
        migrations.AlterField(model_name="creditfeature", name="value", field=models.DecimalField(decimal_places=4, max_digits=20)),
    ]
