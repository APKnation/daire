from dataclasses import asdict, dataclass
import json
import os
from decimal import Decimal
from urllib.error import URLError
from urllib.request import Request, urlopen
from typing import Any
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import (
    AIReputationResult, AuditLog, BlockchainTransaction, Borrower, Consent,
    CreditFeature, CreditProfile, IntegrationRequest, Lender, SmartContractResult,
)


class ExternalServiceUnavailable(Exception):
    """Raised when a configured scoring dependency cannot be used."""


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not url:
        raise ExternalServiceUnavailable("External scoring service is unavailable: URL is not configured.")
    try:
        request = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode())
    except (OSError, ValueError, URLError) as exc:
        raise ExternalServiceUnavailable("External scoring service is unavailable.") from exc
    if not isinstance(result, dict):
        raise ExternalServiceUnavailable("External scoring service returned an invalid response.")
    return result


@dataclass
class NormalizedProfile:
    borrower_reference: str
    active_loan_count: int
    completed_loan_count: int
    defaulted_loan_count: int
    total_outstanding_debt: float
    on_time_payment_ratio: float
    missed_payment_count: int
    late_payment_count: int
    max_days_overdue: int
    transaction_frequency: int
    income_frequency: int
    balance_stability: float


class LenderAdapter:
    def fetch_credit_data(self, borrower_reference: str) -> dict[str, Any]:
        raise NotImplementedError


class MockLenderAdapter(LenderAdapter):
    """Deterministic local adapter for development; production adapters call lender APIs."""

    def fetch_credit_data(self, borrower_reference):
        return {"borrower_reference": borrower_reference, "loans": [], "payments": [], "transactions": []}


def validate_and_normalize(payload: dict[str, Any], borrower_reference: str) -> NormalizedProfile:
    if payload.get("borrower_reference") != borrower_reference:
        raise ValidationError("Lender data borrower_reference does not match the request.")
    for field in ("loans", "payments", "transactions"):
        if not isinstance(payload.get(field), list):
            raise ValidationError(f"{field} must be a list.")
    loans = payload["loans"]
    payments = payload["payments"]
    on_time = sum(1 for item in payments if item.get("status") == "ON_TIME")
    late = sum(1 for item in payments if item.get("status") == "LATE")
    missed = sum(1 for item in payments if item.get("status") == "MISSED")
    return NormalizedProfile(
        borrower_reference=borrower_reference,
        active_loan_count=sum(1 for loan in loans if loan.get("status") == "ACTIVE"),
        completed_loan_count=sum(1 for loan in loans if loan.get("status") == "COMPLETED"),
        defaulted_loan_count=sum(1 for loan in loans if loan.get("status") == "DEFAULTED"),
        total_outstanding_debt=sum(float(loan.get("outstanding_amount", 0)) for loan in loans),
        on_time_payment_ratio=on_time / len(payments) if payments else 1.0,
        missed_payment_count=missed,
        late_payment_count=late,
        max_days_overdue=max((int(item.get("days_overdue", 0)) for item in payments), default=0),
        transaction_frequency=len(payload["transactions"]),
        income_frequency=sum(1 for item in payload["transactions"] if item.get("type") == "INCOME"),
        balance_stability=float(payload.get("balance_stability", 0)),
    )


@transaction.atomic
def create_integration_request(*, lender: Lender, borrower: Borrower, consent: Consent, actor, adapter=None):
    if consent.lender_id != lender.id or consent.borrower_id != borrower.id:
        raise ValidationError("Consent does not belong to this lender and borrower.")
    if not consent.is_valid():
        raise ValidationError("Consent is not active or has expired.")
    request = IntegrationRequest.objects.create(lender=lender, borrower=borrower, consent=consent)
    AuditLog.objects.create(event_type="CONSENT_VERIFIED", actor=actor, request_reference=request.request_reference)
    adapter = adapter or MockLenderAdapter()
    payload = adapter.fetch_credit_data(borrower.borrower_reference)
    profile = validate_and_normalize(payload, borrower.borrower_reference)
    request.raw_payload = payload
    request.status = IntegrationRequest.Status.COMPLETED
    request.save(update_fields=("raw_payload", "status", "updated_at"))
    CreditProfile.objects.update_or_create(
        integration_request=request,
        defaults={"borrower": borrower, "profile_data": asdict(profile)},
    )
    AuditLog.objects.create(
        event_type="DATA_NORMALIZED", actor=actor, request_reference=request.request_reference,
        details={"active_loan_count": profile.active_loan_count, "on_time_payment_ratio": profile.on_time_payment_ratio},
    )
    return request


class FeatureGenerationService:
    """Deterministically derives features from a normalized profile."""

    def generate(self, profile: CreditProfile) -> list[CreditFeature]:
        values = profile.profile_data
        names = (
            "active_loan_count", "completed_loan_count", "defaulted_loan_count",
            "total_outstanding_debt", "on_time_payment_ratio", "missed_payment_count",
            "late_payment_count", "max_days_overdue", "transaction_frequency",
            "income_frequency", "balance_stability",
        )
        features = []
        for name in names:
            value = Decimal(str(values.get(name, 0)))
            feature, _ = CreditFeature.objects.update_or_create(
                profile=profile, name=name, defaults={"value": value},
            )
            features.append(feature)
        return features


class AIReputationService:
    def calculate(self, assessment: Any, features: dict[str, Any]) -> AIReputationResult:
        result = _post_json(os.environ.get("AI_ENGINE_URL", ""), {
            "assessment_reference": assessment.assessment_reference, "features": features,
        })
        required = ("reputation", "score", "model_version")
        if any(key not in result for key in required):
            raise ExternalServiceUnavailable("AI engine returned an incomplete response.")
        return AIReputationResult.objects.update_or_create(
            assessment=assessment,
            defaults={
                "reputation": result["reputation"], "score": result["score"],
                "risk_level": result.get("risk_level", ""),
                "behavior_summary": result.get("behavior_summary", ""),
                "model_version": result["model_version"], "raw_result": result,
            },
        )[0]


class BlockchainScoreService:
    def calculate(self, assessment: Any, features: dict[str, Any]) -> SmartContractResult:
        result = _post_json(os.environ.get("BLOCKCHAIN_RPC_URL", ""), {
            "method": "calculateScore", "contract_address": os.environ.get("SMART_CONTRACT_ADDRESS", ""),
            "assessment_reference": assessment.assessment_reference, "features": features,
        })
        if "credit_score" not in result or "ruleset_version" not in result:
            raise ExternalServiceUnavailable("Smart contract service returned an incomplete response.")
        smart_result = SmartContractResult.objects.update_or_create(
            assessment=assessment,
            defaults={
                "credit_score": result["credit_score"], "ruleset_version": result["ruleset_version"],
                "contract_address": os.environ.get("SMART_CONTRACT_ADDRESS", ""),
                "raw_result": result,
            },
        )[0]
        if result.get("transaction_hash"):
            BlockchainTransaction.objects.update_or_create(
                transaction_hash=result["transaction_hash"],
                defaults={
                    "assessment": assessment, "network": os.environ.get("BLOCKCHAIN_NETWORK", ""),
                    "block_number": result.get("block_number"), "status": result.get("status", "PENDING"),
                    "verification_data": result,
                },
            )
            assessment.blockchain_transaction_hash = result["transaction_hash"]
            assessment.blockchain_block_number = result.get("block_number")
            assessment.save(update_fields=("blockchain_transaction_hash", "blockchain_block_number", "updated_at"))
        return smart_result


class BlockchainVerificationService:
    def verify(self, assessment: Any) -> BlockchainTransaction:
        transaction_hash = assessment.blockchain_transaction_hash
        if not transaction_hash:
            raise ExternalServiceUnavailable("Blockchain transaction is unavailable for verification.")
        rpc_url = os.environ.get("BLOCKCHAIN_RPC_URL")
        if not rpc_url:
            tx = assessment.blockchain_transactions.order_by("-created_at").first()
            if tx:
                return tx
            raise ExternalServiceUnavailable("Blockchain verification service is unavailable: URL is not configured.")
        result = _post_json(rpc_url, {"method": "verify", "transaction_hash": transaction_hash})
        if "status" not in result:
            raise ExternalServiceUnavailable("Blockchain service returned an incomplete response.")
        return BlockchainTransaction.objects.update_or_create(
            transaction_hash=transaction_hash,
            defaults={
                "assessment": assessment, "network": os.environ.get("BLOCKCHAIN_NETWORK", ""),
                "block_number": result.get("block_number"), "status": result["status"],
                "verification_data": result,
            },
        )[0]
