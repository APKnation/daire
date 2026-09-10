from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Borrower, Consent, CreditProfile, Lender
from .services import (
    ExternalServiceUnavailable, FeatureGenerationService, AIReputationService,
    create_integration_request, validate_and_normalize,
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
