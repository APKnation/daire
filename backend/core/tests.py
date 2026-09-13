from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Borrower, BorrowerFinancialProfile, BorrowerLoan, Consent, CreditProfile, Lender
from .services import (
    ExternalServiceUnavailable, FeatureGenerationService, AIReputationService,
    create_integration_request, merge_vendor_borrower_data, validate_and_normalize,
    blockchain_dimensions,
)


class IntegrationServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="lender-user", password="password")
        self.lender = Lender.objects.create(
            lender_id="LENDER-001", institution_name="Test Bank",
            institution_type="COMMERCIAL_BANK", api_base_url="https://example.test",
        )
        self.borrower = Borrower.objects.create(borrower_reference="BRW-001")

    def test_expired_consent_is_rejected_before_data_fetch(self):
        consent = Consent.objects.create(
            consent_id="CONSENT-001", lender=self.lender, borrower=self.borrower,
            purpose="assessment", granted_at=timezone.now() - timedelta(days=2),
            expires_at=timezone.now() - timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            create_integration_request(
                lender=self.lender, borrower=self.borrower, consent=consent, actor=self.user,
            )

    def test_normalization_produces_standard_profile(self):
        profile = validate_and_normalize({
            "borrower_reference": "BRW-001",
            "loans": [{"status": "ACTIVE", "outstanding_amount": 100}],
            "payments": [{"status": "ON_TIME"}, {"status": "LATE", "days_overdue": 4}],
            "transactions": [{"type": "INCOME"}],
        }, "BRW-001")
        self.assertEqual(profile.active_loan_count, 1)
        self.assertEqual(profile.on_time_payment_ratio, 0.5)
        self.assertEqual(profile.max_days_overdue, 4)

    def test_mismatched_borrower_data_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_and_normalize(
                {"borrower_reference": "OTHER", "loans": [], "payments": [], "transactions": []},
                "BRW-001",
            )

    def test_feature_generation_is_deterministic_and_idempotent(self):
        profile = CreditProfile.objects.create(
            borrower=self.borrower,
            profile_data={"active_loan_count": 2, "on_time_payment_ratio": 0.75},
        )
        first = FeatureGenerationService().generate(profile)
        second = FeatureGenerationService().generate(profile)
        self.assertEqual(len(first), 11)
        self.assertEqual(len(second), 11)
        self.assertEqual(profile.features.get(name="active_loan_count").value, 2)

    def test_ai_service_without_url_is_explicitly_unavailable(self):
        with self.assertRaises(ExternalServiceUnavailable):
            AIReputationService().calculate(type("Assessment", (), {"assessment_reference": "A-1"})(), {})

    def test_blockchain_payload_is_five_bounded_dimensions(self):
        dimensions = blockchain_dimensions(features={
            "on_time_payment_ratio": 0.95, "max_days_overdue": 4,
            "missed_payment_count": 0, "transaction_frequency": 10,
            "income_frequency": 5, "balance_stability": 0.8,
            "defaulted_loan_count": 0, "completed_loan_count": 2,
            "total_outstanding_debt": 100,
        }, borrower=self.borrower)
        self.assertEqual(set(dimensions), {"D1", "D2", "D3", "D4", "D5"})
        self.assertTrue(all(0 <= value <= 100 for value in dimensions.values()))

    def test_merges_multi_vendor_borrower_profile(self):
        nmb = Lender.objects.create(
            lender_id="NMB-01", institution_name="NMB", institution_type="MICROFINANCE",
            api_base_url="https://nmb.example.test",
        )
        mpesa = Lender.objects.create(
            lender_id="MPESA-01", institution_name="M-Pesa", institution_type="MOBILE_MONEY",
            api_base_url="https://mpesa.example.test",
        )

        merge_vendor_borrower_data(
            lender=nmb,
            borrower_reference="BRW-001",
            payload={
                "customer_id": "CUST-001",
                "age": 29,
                "gender": "MALE",
                "employment_status": "EMPLOYED",
                "income": 1200000,
                "loans": [{
                    "loan_id": "NMB-LOAN-1",
                    "loan_amount": 500000,
                    "loan_date": "2025-01-12",
                    "loan_duration_months": 12,
                    "interest_rate": 12.5,
                    "outstanding_balance": 320000,
                    "status": "ACTIVE",
                    "repayments": [{
                        "repayment_amount": 42000,
                        "repayment_date": "2025-02-05",
                        "due_date": "2025-02-05",
                        "days_overdue": 0,
                        "missed_payments": 0,
                        "late_payments": 0,
                        "default_status": "CLEAR",
                    }],
                }],
                "transaction_frequency": 12,
                "income_frequency": 4,
                "savings": 250000,
            },
            account_reference="NMB-ACC-01",
        )
        merge_vendor_borrower_data(
            lender=mpesa,
            borrower_reference="BRW-001",
            payload={
                "customer_id": "CUST-001",
                "income": 1200000,
                "loans": [{
                    "loan_id": "MPESA-LOAN-1",
                    "loan_amount": 150000,
                    "loan_date": "2025-03-15",
                    "loan_duration_months": 6,
                    "interest_rate": 18.0,
                    "outstanding_balance": 85000,
                    "status": "ACTIVE",
                    "repayments": [{
                        "repayment_amount": 20000,
                        "repayment_date": "2025-03-25",
                        "due_date": "2025-03-25",
                        "days_overdue": 0,
                        "missed_payments": 0,
                        "late_payments": 0,
                        "default_status": "CLEAR",
                    }],
                }],
                "transaction_frequency": 20,
                "income_frequency": 3,
                "savings": 90000,
            },
            account_reference="MPESA-ACC-99",
        )

        borrower = Borrower.objects.get(borrower_reference="BRW-001")
        self.assertEqual(borrower.loans.count(), 2)
        self.assertEqual(BorrowerLoan.objects.filter(borrower=borrower, lender=nmb).count(), 1)
        self.assertEqual(BorrowerLoan.objects.filter(borrower=borrower, lender=mpesa).count(), 1)
        self.assertEqual(borrower.repayment_records.count(), 2)
        profile = BorrowerFinancialProfile.objects.get(borrower=borrower)
        self.assertEqual(profile.active_loans, 2)
        self.assertEqual(profile.total_outstanding_debt, 405000)
        self.assertEqual(profile.monthly_repayment, 62000)

    def test_search_by_lender_name_and_account_reference(self):
        lender = Lender.objects.create(
            lender_id="CRDB-01", institution_name="CRDB Bank",
            institution_type="COMMERCIAL_BANK", api_base_url="https://crdb.example.test",
        )
        borrower = Borrower.objects.create(borrower_reference="BRW-777")
        borrower.accounts.create(
            lender=lender,
            account_reference="CRDB-ACCOUNT-10",
            account_name="Amina M.",
            customer_id="CUST-777",
        )

        resp = self.client.get("/api/borrowers/search/", {"lender_name": "crdb", "account_reference": "ACCOUNT-10"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]["borrower_reference"], "BRW-777")
