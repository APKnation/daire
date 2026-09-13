from dataclasses import asdict, dataclass
import json
import os
from datetime import date
from decimal import Decimal
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from typing import Any
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import (
    AIReputationResult, BlockchainTransaction, Borrower, BorrowerAccount, BorrowerFinancialProfile,
    BorrowerLoan, Consent, CreditFeature, CreditProfile, IntegrationRequest, Lender,
    RepaymentRecord, SmartContractResult, DataExchange, DataRoutingPolicy,
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


def _get_json(url: str) -> dict[str, Any]:
    if not url:
        raise ExternalServiceUnavailable("External data service is unavailable: URL is not configured.")
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=10) as response:
            result = json.loads(response.read().decode())
    except (OSError, ValueError, URLError) as exc:
        raise ExternalServiceUnavailable("External data service is unavailable.") from exc
    if not isinstance(result, dict):
        raise ExternalServiceUnavailable("External data service returned an invalid response.")
    return result


def active_routing_policy() -> DataRoutingPolicy | None:
    return DataRoutingPolicy.objects.filter(active=True).order_by("-created_at").first()


def fields_for_destination(fields: dict[str, Any], destination: str) -> dict[str, Any]:
    policy = active_routing_policy()
    allowed = getattr(policy, f"{destination.lower()}_fields", None) if policy else None
    if not allowed:
        return fields
    return {name: value for name, value in fields.items() if name in allowed}


def borrower_routing_payload(borrower: Borrower, destination: str = "ai") -> dict[str, Any]:
    try:
        profile = borrower.financial_profile
    except BorrowerFinancialProfile.DoesNotExist:
        profile = None
    fields = {
        "borrower_reference": borrower.borrower_reference,
        "customer_id": borrower.customer_id,
        "income": str(borrower.income or 0),
        "active_loan_count": profile.active_loans if profile else 0,
        "total_outstanding_debt": str(profile.total_outstanding_debt if profile else 0),
        "monthly_repayment": str(profile.monthly_repayment if profile else 0),
        "previous_loans": profile.previous_loans if profile else 0,
        "debt_to_income_ratio": str(profile.debt_to_income_ratio if profile else 0),
        "transaction_frequency": profile.transaction_frequency if profile else 0,
        "income_frequency": profile.income_frequency if profile else 0,
        "savings": str(profile.savings if profile else 0),
    }
    return fields_for_destination(fields, destination)


def record_exchange(**kwargs) -> DataExchange:
    return DataExchange.objects.create(**kwargs)


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


def _coerce_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value in (None, "", "null"):
        return default
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return default


def _coerce_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def refresh_borrower_financial_profile(borrower: Borrower) -> BorrowerFinancialProfile:
    loans = BorrowerLoan.objects.filter(borrower=borrower)
    active_statuses = {"ACTIVE", "CURRENT", "OPEN"}
    total_outstanding = sum((loan.outstanding_balance for loan in loans), Decimal("0"))
    monthly_repayment = sum((record.repayment_amount for record in RepaymentRecord.objects.filter(borrower=borrower)), Decimal("0"))
    transaction_frequency = sum((int((account.metadata or {}).get("transaction_frequency", 0)) for account in borrower.accounts.all()), 0)
    income_frequency = sum((int((account.metadata or {}).get("income_frequency", 0)) for account in borrower.accounts.all()), 0)
    cash_flow_patterns = {
        "vendors": list(borrower.accounts.values_list("lender__institution_name", flat=True)),
        "account_count": borrower.accounts.count(),
    }
    savings = sum(( _coerce_decimal((account.metadata or {}).get("savings", 0)) for account in borrower.accounts.all()), Decimal("0"))
    account_activity = {
        "vendors": [account.lender.institution_name for account in borrower.accounts.select_related("lender")],
        "accounts": [account.account_reference or account.account_name or account.id for account in borrower.accounts.all()],
    }
    profile, _ = BorrowerFinancialProfile.objects.get_or_create(borrower=borrower)
    profile.transaction_frequency = transaction_frequency
    profile.income_frequency = income_frequency
    profile.cash_flow_patterns = cash_flow_patterns
    profile.savings = savings
    profile.account_activity = account_activity
    profile.active_loans = loans.filter(status__in=active_statuses).count()
    profile.total_outstanding_debt = total_outstanding
    profile.monthly_repayment = monthly_repayment
    profile.previous_loans = loans.exclude(status__in=active_statuses).count()
    profile.debt_to_income_ratio = Decimal("0")
    if borrower.income and borrower.income > 0:
        profile.debt_to_income_ratio = (total_outstanding / borrower.income).quantize(Decimal("0.0001"))
    profile.save()
    return profile


def merge_vendor_borrower_data(*, lender: Lender, borrower_reference: str, payload: dict[str, Any], account_reference: str | None = None):
    borrower, _ = Borrower.objects.get_or_create(borrower_reference=borrower_reference)
    borrower.customer_id = payload.get("customer_id") or borrower.customer_id or borrower_reference
    borrower.age = payload.get("age") or borrower.age
    borrower.gender = payload.get("gender") or borrower.gender
    borrower.employment_status = payload.get("employment_status") or borrower.employment_status
    borrower.income = _coerce_decimal(payload.get("income")) if payload.get("income") is not None else borrower.income
    borrower.business_information = payload.get("business_information") or borrower.business_information or {}
    borrower.account_information = payload.get("account_information") or borrower.account_information or {}
    borrower.save(update_fields=(
        "customer_id", "age", "gender", "employment_status", "income",
        "business_information", "account_information", "updated_at",
    ))

    account_key = account_reference or payload.get("account_reference") or payload.get("account_number") or borrower.customer_id
    borrower_account, _ = BorrowerAccount.objects.update_or_create(
        borrower=borrower,
        lender=lender,
        account_reference=account_key,
        defaults={
            "account_name": payload.get("account_name") or lender.institution_name,
            "customer_id": borrower.customer_id,
            "metadata": {
                "transaction_frequency": payload.get("transaction_frequency", 0),
                "income_frequency": payload.get("income_frequency", 0),
                "savings": payload.get("savings", 0),
                "cash_flow_patterns": payload.get("cash_flow_patterns", {}),
                "account_activity": payload.get("account_activity", {}),
            },
        },
    )

    for loan_payload in payload.get("loans", []):
        loan_id = str(loan_payload.get("loan_id") or loan_payload.get("loan_reference") or f"{borrower_reference}-{len(payload.get('loans', []))}")
        loan, _ = BorrowerLoan.objects.update_or_create(
            borrower=borrower,
            lender=lender,
            loan_id=loan_id,
            defaults={
                "source_account": borrower_account,
                "loan_amount": _coerce_decimal(loan_payload.get("loan_amount", 0)),
                "loan_date": _coerce_date(loan_payload.get("loan_date")),
                "loan_duration_months": int(loan_payload.get("loan_duration_months") or loan_payload.get("loan_duration") or 0),
                "interest_rate": _coerce_decimal(loan_payload.get("interest_rate", loan_payload.get("interest", 0))),
                "outstanding_balance": _coerce_decimal(loan_payload.get("outstanding_balance", loan_payload.get("outstanding_amount", 0))),
                "status": loan_payload.get("status") or "ACTIVE",
            },
        )

        for repayment_payload in loan_payload.get("repayments", []):
            repay_date = _coerce_date(repayment_payload.get("repayment_date")) or _coerce_date(repayment_payload.get("date"))
            RepaymentRecord.objects.update_or_create(
                borrower=borrower,
                lender=lender,
                loan=loan,
                repayment_date=repay_date or timezone.now().date(),
                defaults={
                    "repayment_amount": _coerce_decimal(repayment_payload.get("repayment_amount", 0)),
                    "due_date": _coerce_date(repayment_payload.get("due_date")),
                    "days_overdue": int(repayment_payload.get("days_overdue") or 0),
                    "missed_payments": int(repayment_payload.get("missed_payments") or 0),
                    "late_payments": int(repayment_payload.get("late_payments") or 0),
                    "default_status": repayment_payload.get("default_status") or "",
                },
            )

    return refresh_borrower_financial_profile(borrower)


@transaction.atomic
def create_integration_request(*, lender: Lender, borrower: Borrower, consent: Consent, actor, adapter=None):
    if consent.lender_id != lender.id or consent.borrower_id != borrower.id:
        raise ValidationError("Consent does not belong to this lender and borrower.")
    if not consent.is_valid():
        raise ValidationError("Consent is not active or has expired.")
    request = IntegrationRequest.objects.create(lender=lender, borrower=borrower, consent=consent)
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
    merge_vendor_borrower_data(
        lender=lender,
        borrower_reference=borrower.borrower_reference,
        payload={
            "customer_id": borrower.customer_id or borrower.borrower_reference,
            "account_reference": borrower.borrower_reference,
            "account_name": lender.institution_name,
            "loans": payload.get("loans", []),
            "transaction_frequency": len(payload.get("transactions", [])),
            "income_frequency": sum(1 for item in payload.get("transactions", []) if item.get("type") == "INCOME"),
            "savings": payload.get("savings", 0),
            "cash_flow_patterns": payload.get("cash_flow_patterns", {}),
            "account_activity": payload.get("account_activity", {}),
        },
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


def _score(value: float) -> int:
    """Return a deterministic integer score in the contract's 0..100 range."""
    return max(0, min(100, round(value)))


def blockchain_dimensions(*, features: dict[str, Any], borrower: Borrower) -> dict[str, int]:
    """Collapse central-system features into the five values sent on-chain.

    Raw transactions, balances, repayment rows, and identity evidence stay in
    the central system. The contract receives only these bounded dimensions.
    """
    on_time_bps = float(features.get("on_time_payment_ratio", 0)) * 10000
    max_days_late = float(features.get("max_days_overdue", 0))
    missed = float(features.get("missed_payment_count", 0))
    d1 = 100
    if on_time_bps < 9800:
        d1 = 85
    if on_time_bps < 9000:
        d1 = 70
    if on_time_bps < 8000:
        d1 = 50
    d1 -= min(20, int(max_days_late // 10) * 2)
    d1 -= min(30, int(missed * 6))

    transactions = float(features.get("transaction_frequency", 0))
    income_events = float(features.get("income_frequency", 0))
    continuity = 100 if transactions > 0 else 0
    regularity = min(100, income_events / max(transactions, 1) * 100)
    stability = float(features.get("balance_stability", 0))
    stability = stability * 100 if stability <= 1 else stability
    d2 = 0.4 * continuity + 0.3 * regularity + 0.3 * max(0, min(100, stability))

    defaults = float(features.get("defaulted_loan_count", 0))
    completed = float(features.get("completed_loan_count", 0))
    debt = float(features.get("total_outstanding_debt", 0))
    income = float(borrower.income or 0)
    debt_to_income = debt / max(income, 1)
    d3 = 100 - defaults * 35 + min(20, completed * 10)
    if debt_to_income > 0.9:
        d3 -= 25

    # No raw trend series crosses the chain boundary. This is the stable
    # activity/regularity proxy until a trend metric is explicitly generated.
    d4 = 60 + (regularity - 50) * 0.6 - min(30, defaults * 5)

    source_count = borrower.accounts.values("lender_id").distinct().count()
    source_breadth = min(60, source_count * 20)
    corroboration = 40 if source_count >= 2 else (20 if source_count == 1 else 0)
    d5 = source_breadth + corroboration
    return {f"D{i}": _score(value) for i, value in enumerate((d1, d2, d3, d4, d5), 1)}


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
    def calculate(self, assessment: Any, dimensions: dict[str, int]) -> SmartContractResult:
        result = _post_json(os.environ.get("BLOCKCHAIN_RPC_URL", ""), {
            "method": "calculateScore", "contract_address": os.environ.get("SMART_CONTRACT_ADDRESS", ""),
            "assessment_reference": assessment.assessment_reference,
            "dimensions": dimensions,
            "schema_version": "credit-dimensions-v1",
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
