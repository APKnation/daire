from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_aireputationresult_blockchaintransaction_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="borrower",
            name="customer_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="borrower",
            name="age",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="borrower",
            name="gender",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="borrower",
            name="employment_status",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="borrower",
            name="income",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True),
        ),
        migrations.AddField(
            model_name="borrower",
            name="business_information",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="borrower",
            name="account_information",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="BorrowerAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("account_reference", models.CharField(blank=True, default="", max_length=128)),
                ("account_name", models.CharField(blank=True, default="", max_length=255)),
                ("customer_id", models.CharField(blank=True, default="", max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("borrower", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="accounts", to="core.borrower")),
                ("lender", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="borrower_accounts", to="core.lender")),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("borrower", "lender", "account_reference"), name="unique_borrower_account_per_lender")],
            },
        ),
        migrations.CreateModel(
            name="BorrowerLoan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("loan_id", models.CharField(max_length=128)),
                ("loan_amount", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("loan_date", models.DateField(blank=True, null=True)),
                ("loan_duration_months", models.PositiveIntegerField(default=0)),
                ("interest_rate", models.DecimalField(decimal_places=4, default=0, max_digits=8)),
                ("outstanding_balance", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("status", models.CharField(default="ACTIVE", max_length=30)),
                ("borrower", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="loans", to="core.borrower")),
                ("lender", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="borrower_loans", to="core.lender")),
                ("source_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="loans", to="core.borroweraccount")),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("borrower", "lender", "loan_id"), name="unique_borrower_loan_per_lender")],
            },
        ),
        migrations.CreateModel(
            name="RepaymentRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("repayment_amount", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("repayment_date", models.DateField(blank=True, null=True)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("days_overdue", models.PositiveIntegerField(default=0)),
                ("missed_payments", models.PositiveIntegerField(default=0)),
                ("late_payments", models.PositiveIntegerField(default=0)),
                ("default_status", models.CharField(blank=True, default="", max_length=20)),
                ("borrower", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="repayment_records", to="core.borrower")),
                ("lender", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="repayment_records", to="core.lender")),
                ("loan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="repayments", to="core.borrowerloan")),
            ],
        ),
        migrations.CreateModel(
            name="BorrowerFinancialProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("transaction_frequency", models.PositiveIntegerField(default=0)),
                ("income_frequency", models.PositiveIntegerField(default=0)),
                ("cash_flow_patterns", models.JSONField(blank=True, default=dict)),
                ("savings", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("account_activity", models.JSONField(blank=True, default=dict)),
                ("active_loans", models.PositiveIntegerField(default=0)),
                ("total_outstanding_debt", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("monthly_repayment", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("previous_loans", models.PositiveIntegerField(default=0)),
                ("debt_to_income_ratio", models.DecimalField(decimal_places=4, default=0, max_digits=9)),
                ("borrower", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="financial_profile", to="core.borrower")),
            ],
        ),
    ]
