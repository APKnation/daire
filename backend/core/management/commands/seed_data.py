import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    AIReputationResult,
    Assessment,
    AuditLog,
    BlockchainTransaction,
    Borrower,
    Consent,
    CreditFeature,
    CreditProfile,
    IntegrationRequest,
    Lender,
    SmartContractResult,
)


class Command(BaseCommand):
    help = "Seeds comprehensive, realistic data for DAIRE Central System frontend and operations console."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding DAIRE Central System data..."))
        User = get_user_model()
        admin_user = User.objects.filter(is_superuser=True).first()

        now = timezone.now()

        # ---------------------------------------------------------------------
        # 1. LENDERS
        # ---------------------------------------------------------------------
        lenders_data = [
            {
                "lender_id": "LDR-CRDB-01",
                "institution_name": "CRDB Bank Plc",
                "institution_type": "Commercial Bank",
                "api_base_url": "https://api.crdbbank.co.tz/open-banking/v1",
                "api_status": Lender.Status.CONNECTED,
                "authentication_method": "MUTUAL_TLS",
            },
            {
                "lender_id": "LDR-NMB-02",
                "institution_name": "NMB Bank Microfinance",
                "institution_type": "Commercial Bank",
                "api_base_url": "https://api.nmbbank.co.tz/credit-scoring/v2",
                "api_status": Lender.Status.CONNECTED,
                "authentication_method": "OAUTH2",
            },
            {
                "lender_id": "LDR-EQT-03",
                "institution_name": "Equity Bank Agri-Credit",
                "institution_type": "Commercial Bank",
                "api_base_url": "https://api.equitybank.co.tz/lending/v1",
                "api_status": Lender.Status.CONNECTED,
                "authentication_method": "API_KEY",
            },
            {
                "lender_id": "LDR-TZP-04",
                "institution_name": "Tigo Pesa Nano-Lending",
                "institution_type": "Digital Lender",
                "api_base_url": "https://partner.tigo.co.tz/api/credit/v1",
                "api_status": Lender.Status.CONNECTED,
                "authentication_method": "API_KEY",
            },
            {
                "lender_id": "LDR-AIR-05",
                "institution_name": "Airtel Money QuickLoan",
                "institution_type": "Digital Lender",
                "api_base_url": "https://api.airtelmoney.tz/micro-loans",
                "api_status": Lender.Status.DEGRADED,
                "authentication_method": "API_KEY",
            },
            {
                "lender_id": "LDR-MWG-06",
                "institution_name": "Mwanga Community Bank",
                "institution_type": "Microfinance Institution",
                "api_base_url": "https://api.mwangabank.co.tz/v1",
                "api_status": Lender.Status.DISCONNECTED,
                "authentication_method": "API_KEY",
            },
        ]

        lenders = {}
        for ld in lenders_data:
            obj, _ = Lender.objects.update_or_create(
                lender_id=ld["lender_id"],
                defaults=ld,
            )
            lenders[ld["lender_id"]] = obj
        self.stdout.write(self.style.SUCCESS(f"✓ Seeded {len(lenders)} Lenders"))

        # ---------------------------------------------------------------------
        # 2. BORROWERS
        # ---------------------------------------------------------------------
        borrower_refs = [
            "BRW-TZ-1001",
            "BRW-TZ-1002",
            "BRW-TZ-1003",
            "BRW-TZ-1004",
            "apk-09",
            "apk 01",
        ]
        borrowers = {}
        for ref in borrower_refs:
            obj, _ = Borrower.objects.get_or_create(borrower_reference=ref)
            borrowers[ref] = obj
        self.stdout.write(self.style.SUCCESS(f"✓ Seeded {len(borrowers)} Borrowers"))

        # ---------------------------------------------------------------------
        # 3. CONSENTS
        # ---------------------------------------------------------------------
        consents_data = [
            {
                "consent_id": "CST-2026-001",
                "borrower": borrowers["BRW-TZ-1001"],
                "lender": lenders["LDR-CRDB-01"],
                "purpose": "Working capital facility underwriting and credit normalization",
                "granted_at": now - timedelta(days=20),
                "expires_at": now + timedelta(days=70),
                "status": Consent.Status.ACTIVE,
            },
            {
                "consent_id": "CST-2026-002",
                "borrower": borrowers["BRW-TZ-1001"],
                "lender": lenders["LDR-NMB-02"],
                "purpose": "Commercial agricultural asset financing evaluation",
                "granted_at": now - timedelta(days=15),
                "expires_at": now + timedelta(days=45),
                "status": Consent.Status.ACTIVE,
            },
            {
                "consent_id": "CST-2026-003",
                "borrower": borrowers["BRW-TZ-1002"],
                "lender": lenders["LDR-EQT-03"],
                "purpose": "Clean energy mini-grid expansion loan assessment",
                "granted_at": now - timedelta(days=10),
                "expires_at": now + timedelta(days=110),
                "status": Consent.Status.ACTIVE,
            },
            {
                "consent_id": "CST-2026-004",
                "borrower": borrowers["BRW-TZ-1003"],
                "lender": lenders["LDR-CRDB-01"],
                "purpose": "Fleet logistics working capital line appraisal",
                "granted_at": now - timedelta(days=5),
                "expires_at": now + timedelta(days=85),
                "status": Consent.Status.ACTIVE,
            },
            {
                "consent_id": "CST-2026-005",
                "borrower": borrowers["BRW-TZ-1004"],
                "lender": lenders["LDR-TZP-04"],
                "purpose": "Retail pharmaceutical inventory replenishment loan",
                "granted_at": now - timedelta(days=2),
                "expires_at": now + timedelta(days=28),
                "status": Consent.Status.ACTIVE,
            },
            {
                "consent_id": "CST-2026-006",
                "borrower": borrowers["apk-09"],
                "lender": lenders["LDR-CRDB-01"],
                "purpose": "Enterprise SME line of credit and reputation scoring",
                "granted_at": now - timedelta(days=30),
                "expires_at": now + timedelta(days=150),
                "status": Consent.Status.ACTIVE,
            },
            {
                "consent_id": "CST-2026-007",
                "borrower": borrowers["apk 01"],
                "lender": lenders["LDR-NMB-02"],
                "purpose": "Historical consumer credit cross-check",
                "granted_at": now - timedelta(days=90),
                "expires_at": now - timedelta(days=10),
                "status": Consent.Status.EXPIRED,
            },
            {
                "consent_id": "CST-2026-008",
                "borrower": borrowers["BRW-TZ-1002"],
                "lender": lenders["LDR-AIR-05"],
                "purpose": "Short-term operational liquidity pre-approval",
                "granted_at": now - timedelta(days=12),
                "expires_at": now + timedelta(days=18),
                "status": Consent.Status.REVOKED,
            },
        ]

        consents = {}
        for cd in consents_data:
            obj, _ = Consent.objects.update_or_create(
                consent_id=cd["consent_id"],
                defaults=cd,
            )
            consents[cd["consent_id"]] = obj
        self.stdout.write(self.style.SUCCESS(f"✓ Seeded {len(consents)} Consents"))

        # ---------------------------------------------------------------------
        # 4. INTEGRATION REQUESTS & CREDIT PROFILES
        # ---------------------------------------------------------------------
        integrations_data = [
            {
                "consent_id": "CST-2026-001",
                "status": IntegrationRequest.Status.COMPLETED,
                "profile_metrics": {
                    "active_loan_count": 1,
                    "completed_loan_count": 7,
                    "defaulted_loan_count": 0,
                    "total_outstanding_debt": 4500000.0,
                    "on_time_payment_ratio": 0.98,
                    "missed_payment_count": 0,
                    "late_payment_count": 1,
                    "max_days_overdue": 3,
                    "transaction_frequency": 62,
                    "income_frequency": 6,
                    "balance_stability": 0.94,
                },
            },
            {
                "consent_id": "CST-2026-003",
                "status": IntegrationRequest.Status.COMPLETED,
                "profile_metrics": {
                    "active_loan_count": 2,
                    "completed_loan_count": 4,
                    "defaulted_loan_count": 0,
                    "total_outstanding_debt": 12800000.0,
                    "on_time_payment_ratio": 0.93,
                    "missed_payment_count": 0,
                    "late_payment_count": 2,
                    "max_days_overdue": 6,
                    "transaction_frequency": 45,
                    "income_frequency": 4,
                    "balance_stability": 0.88,
                },
            },
            {
                "consent_id": "CST-2026-004",
                "status": IntegrationRequest.Status.COMPLETED,
                "profile_metrics": {
                    "active_loan_count": 2,
                    "completed_loan_count": 3,
                    "defaulted_loan_count": 0,
                    "total_outstanding_debt": 8900000.0,
                    "on_time_payment_ratio": 0.87,
                    "missed_payment_count": 1,
                    "late_payment_count": 3,
                    "max_days_overdue": 12,
                    "transaction_frequency": 38,
                    "income_frequency": 3,
                    "balance_stability": 0.76,
                },
            },
            {
                "consent_id": "CST-2026-005",
                "status": IntegrationRequest.Status.COMPLETED,
                "profile_metrics": {
                    "active_loan_count": 3,
                    "completed_loan_count": 2,
                    "defaulted_loan_count": 1,
                    "total_outstanding_debt": 6200000.0,
                    "on_time_payment_ratio": 0.68,
                    "missed_payment_count": 4,
                    "late_payment_count": 5,
                    "max_days_overdue": 45,
                    "transaction_frequency": 22,
                    "income_frequency": 2,
                    "balance_stability": 0.52,
                },
            },
            {
                "consent_id": "CST-2026-006",
                "status": IntegrationRequest.Status.COMPLETED,
                "profile_metrics": {
                    "active_loan_count": 1,
                    "completed_loan_count": 5,
                    "defaulted_loan_count": 0,
                    "total_outstanding_debt": 2100000.0,
                    "on_time_payment_ratio": 0.95,
                    "missed_payment_count": 0,
                    "late_payment_count": 1,
                    "max_days_overdue": 4,
                    "transaction_frequency": 54,
                    "income_frequency": 5,
                    "balance_stability": 0.90,
                },
            },
        ]

        feature_names = (
            "active_loan_count",
            "completed_loan_count",
            "defaulted_loan_count",
            "total_outstanding_debt",
            "on_time_payment_ratio",
            "missed_payment_count",
            "late_payment_count",
            "max_days_overdue",
            "transaction_frequency",
            "income_frequency",
            "balance_stability",
        )

        integration_requests = []
        for item in integrations_data:
            cst = consents[item["consent_id"]]
            metrics = item["profile_metrics"]
            raw_payload = {
                "borrower_reference": cst.borrower.borrower_reference,
                "institution": cst.lender.institution_name,
                "loans": [
                    {"status": "ACTIVE", "outstanding_amount": metrics["total_outstanding_debt"]},
                    {"status": "COMPLETED", "outstanding_amount": 0},
                ],
                "payments": [
                    {"status": "ON_TIME", "days_overdue": 0} for _ in range(int(metrics["on_time_payment_ratio"] * 20))
                ] + [
                    {"status": "LATE", "days_overdue": metrics["max_days_overdue"]} for _ in range(metrics["late_payment_count"])
                ],
                "transactions": [
                    {"type": "INCOME", "amount": 1200000} for _ in range(metrics["income_frequency"])
                ] + [
                    {"type": "EXPENSE", "amount": 250000} for _ in range(metrics["transaction_frequency"] - metrics["income_frequency"])
                ],
                "balance_stability": metrics["balance_stability"],
            }

            req = IntegrationRequest.objects.create(
                lender=cst.lender,
                borrower=cst.borrower,
                consent=cst,
                status=item["status"],
                raw_payload=raw_payload,
            )
            integration_requests.append(req)

            profile, _ = CreditProfile.objects.update_or_create(
                integration_request=req,
                defaults={
                    "borrower": cst.borrower,
                    "profile_data": metrics,
                    "source_version": "1.2.0",
                },
            )

            for name in feature_names:
                CreditFeature.objects.update_or_create(
                    profile=profile,
                    name=name,
                    defaults={
                        "value": Decimal(str(metrics[name])),
                        "feature_version": "1.0.0",
                    },
                )

        self.stdout.write(self.style.SUCCESS(f"✓ Seeded {len(integration_requests)} Integration Requests, Profiles & Features"))

        # ---------------------------------------------------------------------
        # 5. ASSESSMENTS, AI REPUTATION, SMART CONTRACT & BLOCKCHAIN
        # ---------------------------------------------------------------------
        assessments_data = [
            {
                "assessment_reference": "ASM-2026-8801",
                "borrower": borrowers["BRW-TZ-1001"],
                "reputation": "EXCELLENT",
                "reputation_score": Decimal("0.9450"),
                "risk_level": "LOW",
                "behavior_summary": "Consistent multi-year agricultural wholesale cash inflows. Zero historical defaults across 7 completed loan facilities.",
                "credit_score": 88,
                "ruleset_version": "daire-rules-v2.1",
                "model_version": "daire-ai-v3.0.4",
                "blockchain_transaction_hash": "0x7a3d9b1c5f8e2a4b6c8d0e1f3a5b7c9d1e3f5a7b9c1d3e5f7a9b1c3d5e7f9a1b",
                "blockchain_block_number": 19482710,
                "verification_status": "CONFIRMED",
                "contract_address": "0x71C677700ab35991A562D717A4072f05aB5eB5e3",
            },
            {
                "assessment_reference": "ASM-2026-8802",
                "borrower": borrowers["BRW-TZ-1002"],
                "reputation": "GOOD",
                "reputation_score": Decimal("0.8720"),
                "risk_level": "LOW",
                "behavior_summary": "Strong monthly recurring revenue from solar mini-grid subscriptions. Low debt service burden.",
                "credit_score": 81,
                "ruleset_version": "daire-rules-v2.1",
                "model_version": "daire-ai-v3.0.4",
                "blockchain_transaction_hash": "0x9e1f3a5b7c9d1e3f5a7b9c1d3e5f7a9b1c3d5e7f9a1b7a3d9b1c5f8e2a4b6c8d",
                "blockchain_block_number": 19482855,
                "verification_status": "CONFIRMED",
                "contract_address": "0x71C677700ab35991A562D717A4072f05aB5eB5e3",
            },
            {
                "assessment_reference": "ASM-2026-8803",
                "borrower": borrowers["BRW-TZ-1003"],
                "reputation": "MODERATE",
                "reputation_score": Decimal("0.7410"),
                "risk_level": "MEDIUM",
                "behavior_summary": "High asset utilization with freight contracts; moderate cash flow volatility due to seasonal fuel cost spikes.",
                "credit_score": 69,
                "ruleset_version": "daire-rules-v2.1",
                "model_version": "daire-ai-v3.0.4",
                "blockchain_transaction_hash": "0x3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d",
                "blockchain_block_number": 19482990,
                "verification_status": "CONFIRMED",
                "contract_address": "0x71C677700ab35991A562D717A4072f05aB5eB5e3",
            },
            {
                "assessment_reference": "ASM-2026-8804",
                "borrower": borrowers["BRW-TZ-1004"],
                "reputation": "HIGH_RISK",
                "reputation_score": Decimal("0.4890"),
                "risk_level": "HIGH",
                "behavior_summary": "Elevated trade supplier delinquency and irregular deposit volume. Overdue payment history observed.",
                "credit_score": 46,
                "ruleset_version": "daire-rules-v2.1",
                "model_version": "daire-ai-v3.0.4",
                "blockchain_transaction_hash": "",
                "blockchain_block_number": None,
                "verification_status": "PENDING",
                "contract_address": "0x71C677700ab35991A562D717A4072f05aB5eB5e3",
            },
            {
                "assessment_reference": "ASM-2026-8805",
                "borrower": borrowers["apk-09"],
                "reputation": "EXCELLENT",
                "reputation_score": Decimal("0.9200"),
                "risk_level": "LOW",
                "behavior_summary": "Top-tier liquidity buffer, verified institutional loan history, zero defaults across all tracked facilities.",
                "credit_score": 85,
                "ruleset_version": "daire-rules-v2.1",
                "model_version": "daire-ai-v3.0.4",
                "blockchain_transaction_hash": "0x5b7c9d1e3f5a7b9c1d3e5f7a9b1c3d5e7f9a1b7a3d9b1c5f8e2a4b6c8d0e1f3a",
                "blockchain_block_number": 19483120,
                "verification_status": "CONFIRMED",
                "contract_address": "0x71C677700ab35991A562D717A4072f05aB5eB5e3",
            },
        ]

        for ad in assessments_data:
            tx_hash = ad["blockchain_transaction_hash"]
            block_num = ad["blockchain_block_number"]
            contract_addr = ad["contract_address"]

            assessment_defaults = {
                "borrower": ad["borrower"],
                "reputation": ad["reputation"],
                "reputation_score": ad["reputation_score"],
                "risk_level": ad["risk_level"],
                "behavior_summary": ad["behavior_summary"],
                "credit_score": ad["credit_score"],
                "ruleset_version": ad["ruleset_version"],
                "model_version": ad["model_version"],
                "blockchain_transaction_hash": tx_hash,
                "blockchain_block_number": block_num,
                "verification_status": ad["verification_status"],
            }

            asm, _ = Assessment.objects.update_or_create(
                assessment_reference=ad["assessment_reference"],
                defaults=assessment_defaults,
            )

            AIReputationResult.objects.update_or_create(
                assessment=asm,
                defaults={
                    "reputation": ad["reputation"],
                    "score": ad["reputation_score"],
                    "risk_level": ad["risk_level"],
                    "behavior_summary": ad["behavior_summary"],
                    "model_version": ad["model_version"],
                    "raw_result": {
                        "reputation": ad["reputation"],
                        "score": float(ad["reputation_score"]),
                        "risk_level": ad["risk_level"],
                        "model_version": ad["model_version"],
                        "behavior_summary": ad["behavior_summary"],
                    },
                },
            )

            SmartContractResult.objects.update_or_create(
                assessment=asm,
                defaults={
                    "credit_score": ad["credit_score"],
                    "ruleset_version": ad["ruleset_version"],
                    "contract_address": contract_addr,
                    "raw_result": {
                        "credit_score": ad["credit_score"],
                        "ruleset_version": ad["ruleset_version"],
                        "contract_address": contract_addr,
                        "transaction_hash": tx_hash,
                        "block_number": block_num,
                    },
                },
            )

            if tx_hash:
                BlockchainTransaction.objects.update_or_create(
                    transaction_hash=tx_hash,
                    defaults={
                        "assessment": asm,
                        "network": "Polygon Amoy Testnet",
                        "block_number": block_num,
                        "status": "CONFIRMED",
                        "verification_data": {
                            "network": "Polygon Amoy Testnet",
                            "status": "CONFIRMED",
                            "block_number": block_num,
                            "assessment_reference": asm.assessment_reference,
                            "credit_score": asm.credit_score,
                        },
                    },
                )

        self.stdout.write(self.style.SUCCESS(f"✓ Seeded {len(assessments_data)} Assessments, AI Results, Smart Contracts & On-Chain Transactions"))

        # ---------------------------------------------------------------------
        # 6. AUDIT LOGS
        # ---------------------------------------------------------------------
        audit_events = [
            {
                "event_type": "CONSENT_VERIFIED",
                "request_reference": uuid.uuid4(),
                "details": {"consent_id": "CST-2026-001", "borrower": "BRW-TZ-1001", "lender": "CRDB Bank Plc", "status": "ACTIVE"},
            },
            {
                "event_type": "DATA_NORMALIZED",
                "request_reference": uuid.uuid4(),
                "details": {"borrower": "BRW-TZ-1001", "active_loans": 1, "completed_loans": 7, "on_time_ratio": 0.98},
            },
            {
                "event_type": "FEATURES_GENERATED",
                "request_reference": uuid.uuid4(),
                "details": {"profile_id": 1, "features_count": 11, "version": "1.0.0"},
            },
            {
                "event_type": "AI_REPUTATION_SCORING",
                "request_reference": uuid.uuid4(),
                "details": {"assessment": "ASM-2026-8801", "reputation": "EXCELLENT", "score": 0.9450, "model": "daire-ai-v3.0.4"},
            },
            {
                "event_type": "SMART_CONTRACT_CALCULATED",
                "request_reference": uuid.uuid4(),
                "details": {"assessment": "ASM-2026-8801", "credit_score": 88, "ruleset": "daire-rules-v2.1"},
            },
            {
                "event_type": "BLOCKCHAIN_ANCHORED",
                "request_reference": uuid.uuid4(),
                "details": {"network": "Polygon Amoy Testnet", "tx": "0x7a3d9b1c5f8e...", "block": 19482710, "status": "CONFIRMED"},
            },
            {
                "event_type": "CONSENT_VERIFIED",
                "request_reference": uuid.uuid4(),
                "details": {"consent_id": "CST-2026-006", "borrower": "apk-09", "lender": "CRDB Bank Plc", "status": "ACTIVE"},
            },
            {
                "event_type": "DATA_NORMALIZED",
                "request_reference": uuid.uuid4(),
                "details": {"borrower": "apk-09", "active_loans": 1, "completed_loans": 5, "on_time_ratio": 0.95},
            },
            {
                "event_type": "SCORE_VERIFIED",
                "request_reference": uuid.uuid4(),
                "details": {"assessment": "ASM-2026-8805", "credit_score": 85, "verified": True, "method": "on-chain proof"},
            },
            {
                "event_type": "SECURITY_AUDIT",
                "request_reference": None,
                "details": {"action": "SYSTEM_STARTUP", "status": "ALL_SERVICES_OPTIMAL", "environment": "local-dev"},
            },
        ]

        for log_data in audit_events:
            AuditLog.objects.create(
                event_type=log_data["event_type"],
                actor=admin_user,
                request_reference=log_data["request_reference"],
                details=log_data["details"],
            )

        self.stdout.write(self.style.SUCCESS(f"✓ Seeded {len(audit_events)} Audit Logs"))
        self.stdout.write(self.style.SUCCESS("All test data seeded successfully!"))
