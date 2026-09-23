from contextlib import ExitStack
from datetime import timedelta
from unittest import mock
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Borrower, BorrowerAccount, BorrowerFinancialProfile, BorrowerLoan, Consent, CreditProfile, Lender
from .services import (
    ExternalServiceUnavailable, FeatureGenerationService, AIReputationService,
    create_integration_request, merge_vendor_borrower_data, validate_and_normalize,
    validate_and_filter_lender_payload,
    blockchain_dimensions, build_credit_risk_row, CREDIT_RISK_MODEL_FEATURES,
    CREDIT_RISK_MODEL_VERSION, summarize_transactions,
)


class IntegrationServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="lender-user", password="password")
        self.lender = Lender.objects.create(
            lender_id="LENDER-001", institution_name="Test Bank",
            institution_type="COMMERCIAL_BANK", api_base_url="https://example.test",
        )
        self.borrower = Borrower.objects.create(borrower_reference="BRW-001")

    def test_borrower_pull_uses_compact_response(self):
        response = self.client.get(f"/api/borrowers/{self.borrower.pk}/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("borrower_reference", body)
        self.assertIn("financial_profile", body)
        self.assertIn("accounts", body)
        self.assertIn("loans", body)
        self.assertNotIn("data_conflicts", body)
        self.assertNotIn("created_at", body)
        self.assertNotIn("cash_flow_patterns", body["financial_profile"] or {})

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

    def test_ai_service_scores_in_valid_range(self):
        # With no AI_ENGINE_URL the service scores with the trained joblib model
        # (legacy deterministic formula only if the model file is missing).
        from core.services import _local_ai_reputation

        self.assertEqual(_local_ai_reputation({"on_time_payment_ratio": 1, "defaulted_loan_count": 0, "missed_payment_count": 0, "balance_stability": 1, "completed_loan_count": 5, "late_payment_count": 0})["reputation"], "EXCELLENT")
        self.assertEqual(_local_ai_reputation({"on_time_payment_ratio": 0.1, "defaulted_loan_count": 3, "missed_payment_count": 5, "balance_stability": 0.2, "completed_loan_count": 0, "late_payment_count": 4})["reputation"], "HIGH_RISK")
        result = AIReputationService().calculate(self.borrower_assessment(), {"on_time_payment_ratio": 0.95, "defaulted_loan_count": 0, "missed_payment_count": 0, "balance_stability": 0.9, "completed_loan_count": 4, "late_payment_count": 0})
        self.assertTrue(0 <= float(result.score) <= 1)

    def borrower_assessment(self):
        from core.models import Assessment

        assessment, _ = Assessment.objects.update_or_create(
            assessment_reference="A-1",
            defaults={"borrower": self.borrower},
        )
        return assessment

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
                    "loan_id": "4002",
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
            account_reference="3002",
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

    def test_payload_outside_contract_is_ignored(self):
        """Fields outside the DAIRE lender format are dropped, not merged."""
        lender = Lender.objects.create(
            lender_id="IGN-01", institution_name="Ignored Bank",
            institution_type="COMMERCIAL_BANK", api_base_url="https://ign.example.test",
        )
        clean, ignored = validate_and_filter_lender_payload({
            "borrower_reference": "1001",
            "customer_id": "002",
            "age": 34,
            "income": 3500000,
            # ---- outside the contract: must be ignored ----
            "internal_branch_code": "DSM-042",
            "officer_notes": "offered tea",
            "pin_hint": "must-never-be-stored",
            "credit_bureau_raw": {"score": 600},
        })
        self.assertNotIn("internal_branch_code", clean)
        self.assertNotIn("officer_notes", clean)
        self.assertNotIn("pin_hint", clean)
        self.assertNotIn("credit_bureau_raw", clean)
        self.assertIn("internal_branch_code", ignored)
        self.assertIn("officer_notes", ignored)
        self.assertIn("pin_hint", ignored)
        self.assertIn("credit_bureau_raw", ignored)
        # Contract fields survive untouched.
        self.assertEqual(clean["customer_id"], "002")
        self.assertEqual(clean["age"], 34)
        self.assertEqual(clean["income"], 3500000)

    def test_invalid_values_inside_contract_fields_are_dropped(self):
        clean, ignored = validate_and_filter_lender_payload({
            "borrower_reference": "1001",
            "age": "very old",            # wrong type
            "income": -50,                 # negative money
            "balance_stability": 1.5,      # out of range (0-1 or 0-100)
            "transactions": "all at once", # not a list
            "loans": [
                {"loan_id": "4001", "loan_amount": 500000, "repayments": [
                    {"repayment_amount": 42000}, {"nonsense": True},
                ]},
                {"no_identity": True},     # loan without loan_id
                "junk-row",                # not an object
            ],
        })
        self.assertNotIn("age", clean)
        self.assertIn("age (invalid value)", ignored)
        self.assertNotIn("income", clean)
        self.assertIn("income (invalid value)", ignored)
        self.assertNotIn("balance_stability", clean)
        self.assertEqual(clean["transactions"], [])
        self.assertIn("transactions (not a list)", ignored)
        self.assertEqual(len(clean["loans"]), 1)
        self.assertEqual(clean["loans"][0]["loan_id"], "4001")
        # Repayment row with only unknown keys is dropped; valid one kept.
        self.assertEqual(len(clean["loans"][0]["repayments"]), 1)
        self.assertIn("loans[1] (missing loan_id)", ignored)
        self.assertIn("loans[2] (not an object)", ignored)

    def test_merge_stores_ignored_fields_for_audit(self):
        lender = Lender.objects.create(
            lender_id="IGN-02", institution_name="Audit Bank",
            institution_type="COMMERCIAL_BANK", api_base_url="https://aud.example.test",
        )
        merge_vendor_borrower_data(
            lender=lender,
            borrower_reference="BRW-IGN-1",
            payload={
                "borrower_reference": "BRW-IGN-1",
                "customer_id": "003",
                "income": 1000000,
                "secret_field": "drop-me",
                "loans": [],
            },
            account_reference="3003",
        )
        account = BorrowerAccount.objects.get(borrower__borrower_reference="BRW-IGN-1", lender=lender)
        self.assertIn("secret_field", account.metadata.get("ignored_fields", []))

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

    def _borrower_with_loan(self, reference="BRW-MODEL-1", loan_status="ACTIVE"):
        from decimal import Decimal

        borrower = Borrower.objects.create(
            borrower_reference=reference, age=30, income=Decimal("1200000"),
        )
        account = borrower.accounts.create(
            lender=self.lender, account_reference="ACC-MODEL-1",
            account_name="Model Test", customer_id="CUST-MODEL-1",
            metadata={"account_activity": {
                "first_transaction_date": "2020-01-01",
                "last_transaction_date": "2024-01-01",
            }},
        )
        loan = BorrowerLoan.objects.create(
            borrower=borrower, lender=self.lender, source_account=account,
            loan_id="LOAN-MODEL-1", loan_amount=Decimal("500000"),
            interest_rate=Decimal("12.5"), outstanding_balance=Decimal("320000"),
            status=loan_status,
        )
        return borrower, loan

    def test_credit_risk_row_matches_model_schema(self):
        borrower, _ = self._borrower_with_loan()
        row = build_credit_risk_row(borrower)
        self.assertEqual(set(row), set(CREDIT_RISK_MODEL_FEATURES))
        self.assertEqual(row["person_age"], 30)
        self.assertEqual(row["person_income"], 1200000.0)
        self.assertEqual(row["loan_amnt"], 500000.0)
        self.assertEqual(row["loan_int_rate"], 12.5)
        self.assertAlmostEqual(row["loan_percent_income"], 500000.0 / 1200000.0, places=4)
        self.assertEqual(row["cb_person_default_on_file"], "N")
        self.assertAlmostEqual(row["cb_person_cred_hist_length"], 4.0, places=1)
        # Fields the central system does not collect stay None for imputation.
        self.assertIsNone(row["person_home_ownership"])
        self.assertIsNone(row["person_emp_length"])
        self.assertIsNone(row["loan_intent"])
        self.assertIsNone(row["loan_grade"])

    def test_credit_risk_row_flags_defaulted_loans(self):
        borrower, _ = self._borrower_with_loan(reference="BRW-MODEL-2", loan_status="DEFAULTED")
        row = build_credit_risk_row(borrower)
        self.assertEqual(row["cb_person_default_on_file"], "Y")

    def test_credit_risk_row_without_loans_still_maps(self):
        borrower = Borrower.objects.create(borrower_reference="BRW-MODEL-3", age=40)
        row = build_credit_risk_row(borrower)
        self.assertEqual(set(row), set(CREDIT_RISK_MODEL_FEATURES))
        self.assertIsNone(row["loan_amnt"])
        self.assertEqual(row["cb_person_default_on_file"], "N")

    def test_ai_service_scores_from_trained_model(self):
        borrower, _ = self._borrower_with_loan(reference="BRW-MODEL-4")
        assessment = self.borrower_assessment()
        assessment.borrower = borrower
        assessment.save(update_fields=("borrower",))
        result = AIReputationService().calculate(assessment, {})
        self.assertEqual(result.model_version, CREDIT_RISK_MODEL_VERSION)
        self.assertTrue(0 <= float(result.score) <= 1)
        self.assertIn(result.reputation, ("EXCELLENT", "GOOD", "MODERATE", "HIGH_RISK"))
        self.assertEqual(result.raw_result["engine"], "TRAINED_MODEL")
        self.assertEqual(set(result.raw_result["model_inputs"]), set(CREDIT_RISK_MODEL_FEATURES))

    def test_ai_service_scores_borrower_without_loans(self):
        borrower = Borrower.objects.create(borrower_reference="BRW-MODEL-5", age=40)
        assessment = self.borrower_assessment()
        assessment.borrower = borrower
        assessment.save(update_fields=("borrower",))
        result = AIReputationService().calculate(assessment, {})
        self.assertEqual(result.model_version, CREDIT_RISK_MODEL_VERSION)
        self.assertTrue(0 <= float(result.score) <= 1)


class LenderApiKeyTests(TestCase):
    """Subsystem integration runs keyless by default (one trusted network).

    API keys are opt-in hardening via REQUIRE_API_KEYS=true; these tests cover
    both modes. The override patches core.services.api_keys_required, which is
    the symbol views._check_lender_key looks up, so tests need no env mutation.
    """

    def setUp(self):
        self.lender = Lender.objects.create(
            lender_id="KEY-01", institution_name="Key Bank",
            institution_type="COMMERCIAL_BANK", api_base_url="https://key.example.test",
        )

    def _enforce_keys(self):
        """Patch REQUIRE_API_KEYS=true for both import sites (views imported
        api_keys_required by name, so the services symbol alone is not enough)."""
        stack = ExitStack()
        for target in ("core.services.api_keys_required", "core.views.api_keys_required"):
            stack.enter_context(mock.patch(target, return_value=True))
        return stack

    def _push(self, key=None, lender_id="KEY-01", reference="BRW-KEY-1"):
        return self.client.post(
            "/api/lender-data/receive/",
            data={
                "lender_id": lender_id, "borrower_reference": reference,
                "payload": {"borrower_reference": reference, "customer_id": "C-1"},
            },
            content_type="application/json",
            **({"HTTP_X_API_KEY": key} if key else {}),
        )

    def test_registration_assigns_id_and_key(self):
        resp = self.client.post("/api/lenders/", data={
            "lender_id": "NMB-001", "institution_name": "NMB Bank",
            "institution_type": "COMMERCIAL_BANK", "api_base_url": "https://nmb.example.test",
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        raw = resp.json()["api_key"]
        self.assertTrue(raw.startswith("daire_live_"))
        lender = Lender.objects.get(lender_id="NMB-001")
        self.assertNotEqual(lender.api_key_hash, raw)
        self.assertTrue(lender.check_api_key(raw))
        self.assertEqual(lender.api_key_prefix, raw[:12])
        # Plaintext and hash are never exposed afterwards.
        listed = self.client.get(f"/api/lenders/{lender.id}/").json()
        self.assertNotIn("api_key", listed)
        self.assertNotIn("api_key_hash", listed)
        self.assertEqual(listed["api_key_prefix"], raw[:12])

    def test_push_requires_key_when_set(self):
        raw = self.lender.issue_api_key()
        with self._enforce_keys():
            self.assertEqual(self._push().status_code, 401)
            self.assertEqual(self._push(key="wrong").status_code, 401)
            resp = self._push(key=raw)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["lender_id"], "KEY-01")

    def test_legacy_lender_without_key_still_accepted(self):
        with self._enforce_keys():
            resp = self._push()
        self.assertEqual(resp.status_code, 201)

    def test_regenerate_key_revokes_old(self):
        old = self.lender.issue_api_key()
        with self._enforce_keys():
            resp = self.client.post(f"/api/lenders/{self.lender.id}/regenerate-key/")
            new = resp.json()["api_key"]
            self.assertEqual(resp.status_code, 200)
            self.assertNotEqual(new, old)
            self.assertEqual(self._push(key=old).status_code, 401)
            self.assertEqual(self._push(key=new, reference="BRW-KEY-2").status_code, 201)

    def test_save_auto_issues_key_for_legacy_lender(self):
        # Legacy lender without a key gets one on first save (shown once).
        resp = self.client.patch(f"/api/lenders/{self.lender.id}/", data={
            "institution_name": "Key Bank Renamed",
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        raw = resp.json()["api_key"]
        self.assertTrue(raw.startswith("daire_live_"))
        self.lender.refresh_from_db()
        self.assertTrue(self.lender.check_api_key(raw))
        # Second save keeps the existing key: no rotation, no leak.
        resp2 = self.client.patch(f"/api/lenders/{self.lender.id}/", data={
            "institution_name": "Key Bank Renamed Again",
        }, content_type="application/json")
        self.assertEqual(resp2.status_code, 200)
        self.assertNotIn("api_key", resp2.json())
        self.assertTrue(Lender.objects.get(pk=self.lender.pk).check_api_key(raw))

    def test_keyless_push_accepted_by_default(self):
        """Trusted-network default: no key headers at all still merges the push."""
        self.lender.issue_api_key()  # even with a key registered
        resp = self._push()
        self.assertEqual(resp.status_code, 201)

    def test_keyless_push_accepted_when_keys_required_but_lender_has_no_key(self):
        """A lender registered with no key keeps working in enforcement mode too."""
        with self._enforce_keys():
            resp = self._push(reference="BRW-KEY-NOKEY")
        self.assertEqual(resp.status_code, 201)

    def test_push_accepts_django_primary_key_as_legacy_lender_id(self):
        resp = self._push(lender_id=str(self.lender.pk), reference="BRW-KEY-PK")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["lender_id"], "KEY-01")

    def test_push_accepts_nested_lender_identity(self):
        resp = self.client.post(
            "/api/lender-data/receive/",
            data={
                "lender": {"lender_id": "key-01"},
                "borrower_reference": "BRW-KEY-NESTED",
                "payload": {"customer_id": "C-1"},
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["lender_id"], "KEY-01")

    def test_push_can_identify_lender_from_api_key(self):
        raw = self.lender.issue_api_key()
        resp = self.client.post(
            "/api/lender-data/receive/",
            data={
                "borrower_reference": "BRW-KEY-HEADER",
                "payload": {"customer_id": "C-1"},
            },
            content_type="application/json",
            HTTP_X_API_KEY=raw,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["lender_id"], "KEY-01")


class AssessmentFlowTests(TestCase):
    """Lender data -> open assessment -> score, with no consent flow involved."""

    def setUp(self):
        self.lender = Lender.objects.create(
            lender_id="FLOW-01", institution_name="Flow Bank",
            institution_type="COMMERCIAL_BANK", api_base_url="https://flow.example.test",
        )

    def _push(self, reference="BRW-FLOW-1"):
        return self.client.post("/api/lender-data/receive/", data={
            "lender_id": "FLOW-01", "borrower_reference": reference,
            "account_reference": "ACC-FLOW-1",
            "payload": {
                "borrower_reference": reference, "customer_id": "C-FLOW-1",
                "age": 34, "income": 3000000,
                "transaction_frequency": 40, "income_frequency": 4, "savings": 500000,
                "loans": [{
                    "loan_id": "LN-FLOW-1", "loan_amount": 1000000,
                    "loan_date": "2024-01-10", "loan_duration_months": 12,
                    "interest_rate": 15.0, "outstanding_balance": 600000,
                    "status": "ACTIVE",
                    "repayments": [{
                        "repayment_amount": 90000, "repayment_date": "2024-02-10",
                        "due_date": "2024-02-10", "days_overdue": 5,
                        "missed_payments": 0, "late_payments": 1,
                        "default_status": "CLEAR",
                    }],
                }],
            },
        }, content_type="application/json")

    def test_create_assessment_requires_known_borrower(self):
        self.assertEqual(self.client.post(
            "/api/assessments/", data={}, content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(
            "/api/assessments/", data={"borrower_reference": "NOPE"},
            content_type="application/json").status_code, 404)

    def test_full_flow_push_assess_score(self):
        self.assertEqual(self._push().status_code, 201)
        created = self.client.post("/api/assessments/", data={
            "borrower_reference": "BRW-FLOW-1",
        }, content_type="application/json")
        self.assertEqual(created.status_code, 201)
        reference = created.json()["assessment_reference"]
        self.assertTrue(reference.startswith("ASM-"))
        # Scoring profile was synthesized from the pushed records.
        profile = CreditProfile.objects.filter(
            borrower__borrower_reference="BRW-FLOW-1").order_by("-created_at").first()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.source_version, "lender-push-v1")
        self.assertEqual(profile.features.count(), 11)
        self.assertEqual(profile.profile_data["active_loan_count"], 1)
        self.assertEqual(profile.profile_data["late_payment_count"], 1)
        self.assertEqual(profile.profile_data["max_days_overdue"], 5)
        # AI scores with the trained model straight away.
        scored = self.client.post(f"/api/assessments/{reference}/ai-reputation/",
                                   data={}, content_type="application/json")
        self.assertEqual(scored.status_code, 200)
        self.assertEqual(scored.json()["model_version"], CREDIT_RISK_MODEL_VERSION)
        # Re-pushing lender data refreshes the synthesized profile.
        self._push()
        profile.refresh_from_db()
        self.assertEqual(profile.source_version, "lender-push-v1")

    def test_consent_profile_is_never_overwritten(self):
        from .services import ensure_credit_profile

        borrower = Borrower.objects.create(borrower_reference="BRW-FLOW-9")
        consent_profile = CreditProfile.objects.create(
            borrower=borrower, profile_data={"active_loan_count": 9},
            source_version="1.2.0",
        )
        ensured = ensure_credit_profile(borrower)
        self.assertEqual(ensured.pk, consent_profile.pk)
        self.assertEqual(ensured.profile_data, {"active_loan_count": 9})


class TransactionSummaryTests(TestCase):
    def setUp(self):
        self.lender = Lender.objects.create(
            lender_id="TX-01", institution_name="Tx Bank",
            institution_type="COMMERCIAL_BANK", api_base_url="https://tx.example.test",
        )

    def test_summary_only_push_avoids_rows(self):
        summary = summarize_transactions({
            "transaction_count": 240, "transaction_total_amount": 18400000,
            "transaction_currency": "TZS", "income_count": 24,
            "income_total_amount": 14400000,
        })
        self.assertEqual(summary["count"], 240)
        self.assertEqual(summary["total_amount"], 18400000.0)
        self.assertEqual(summary["currency"], "TZS")
        self.assertEqual(summary["income_count"], 24)
        self.assertEqual(summary["income_total_amount"], 14400000.0)

    def test_nested_summary_shape_accepted(self):
        summary = summarize_transactions({
            "transaction_summary": {"count": 100, "total_amount": 5000000, "currency": "TZS"},
        })
        self.assertEqual(summary["count"], 100)
        self.assertEqual(summary["total_amount"], 5000000.0)

    def test_array_wins_and_derives(self):
        summary = summarize_transactions({
            "transaction_count": 5, "transaction_total_amount": 1,
            "transactions": [
                {"transaction_id": "T1", "type": "INCOME", "amount": 1000},
                {"transaction_id": "T2", "type": "EXPENSE", "amount": 400},
                {"transaction_id": "T3", "type": "INCOME", "amount": "600"},
            ],
        })
        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["total_amount"], 2000.0)
        self.assertEqual(summary["income_count"], 2)
        self.assertEqual(summary["income_total_amount"], 1600.0)

    def test_receive_stores_and_reports_aggregates(self):
        resp = self.client.post("/api/lender-data/receive/", data={
            "lender_id": "TX-01", "borrower_reference": "BRW-TX-1",
            "account_reference": "ACC-TX-1",
            "payload": {
                "borrower_reference": "BRW-TX-1", "customer_id": "C-TX-1",
                "transaction_count": 240, "transaction_total_amount": 18400000,
                "transaction_currency": "TZS",
            },
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["summary"]["transaction_count"], 240)
        self.assertEqual(body["summary"]["transaction_total_amount"], 18400000.0)
        self.assertEqual(body["summary"]["transaction_currency"], "TZS")
        account = Borrower.objects.get(borrower_reference="BRW-TX-1").accounts.get()
        self.assertEqual(account.metadata["transaction_count"], 240)
        self.assertEqual(account.metadata["transaction_total_amount"], 18400000.0)
        # Counts still feed the financial profile when no row data exists.
        self.assertEqual(account.metadata["transaction_frequency"], 240)


class PaginationTests(TestCase):
    def test_lists_are_paginated(self):
        for i in range(12):
            Lender.objects.create(
                lender_id=f"PAGE-{i:02d}", institution_name=f"Page Bank {i}",
                institution_type="COMMERCIAL_BANK", api_base_url="https://page.example.test",
            )
        first = self.client.get("/api/lenders/").json()
        self.assertEqual(first["count"], 12)
        self.assertEqual(len(first["results"]), 10)
        self.assertIsNotNone(first["next"])
        second = self.client.get("/api/lenders/?page=2").json()
        self.assertEqual(len(second["results"]), 2)
        self.assertIsNone(second["next"])


class StageRecordActionTests(TestCase):
    """View/Edit/Delete actions on the dashboard stage tables."""

    def setUp(self):
        self.lender = Lender.objects.create(
            lender_id="ACTION-001", institution_name="Action Bank",
            institution_type="COMMERCIAL_BANK", api_base_url="https://action.example.test",
        )
        self.borrower = Borrower.objects.create(borrower_reference="BRW-ACTION")
        self.exchange = DataExchange.objects.create(
            system=DataExchange.System.LENDER,
            direction=DataExchange.Direction.PULL,
            operation="pull_borrower_data",
            lender=self.lender,
            borrower=self.borrower,
        )

    def test_exchange_patch_updates_operation(self):
        response = self.client.patch(
            f"/api/data-exchanges/{self.exchange.id}/",
            data='{"operation": "renamed_operation"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.operation, "renamed_operation")

    def test_exchange_delete_is_allowed(self):
        response = self.client.delete(f"/api/data-exchanges/{self.exchange.id}/")
        self.assertIn(response.status_code, (200, 204))
        self.assertFalse(DataExchange.objects.filter(id=self.exchange.id).exists())

    def test_immutable_assessment_delete_is_rejected(self):
        assessment = Assessment.objects.create(
            assessment_reference="ASM-ACTION-0001", borrower=self.borrower,
        )
        response = self.client.delete(f"/api/assessments/{assessment.assessment_reference}/")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Assessment.objects.filter(id=assessment.id).exists())

    def test_assessment_patch_updates_risk_level(self):
        assessment = Assessment.objects.create(
            assessment_reference="ASM-ACTION-0002", borrower=self.borrower,
        )
        response = self.client.patch(
            f"/api/assessments/{assessment.assessment_reference}/",
            data='{"risk_level": "LOW"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        assessment.refresh_from_db()
        self.assertEqual(assessment.risk_level, "LOW")

    def test_dashboard_smoke_after_record_actions(self):
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, 200)
