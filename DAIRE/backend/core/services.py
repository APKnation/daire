from dataclasses import asdict, dataclass
import json
import os
import uuid
from datetime import date
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from typing import Any
import joblib
import pandas as pd
from django.conf import settings
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


def external_request_timeout() -> int:
    """Maximum wait for a lender or scoring HTTP response."""
    try:
        return max(1, int(os.environ.get("DAIRE_EXTERNAL_TIMEOUT", "30")))
    except (TypeError, ValueError):
        return 30


def lender_request_timeout() -> int:
    """Short maximum wait for a lender data pull.

    Lender pulls are fan-out requests, so one offline lender should not make
    the whole assessment wait as long as a scoring service call.
    """
    try:
        return max(1, int(os.environ.get("DAIRE_LENDER_TIMEOUT", "8")))
    except (TypeError, ValueError):
        return 8


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    if not url:
        raise ExternalServiceUnavailable("External scoring service is unavailable: URL is not configured.")
    try:
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        request = Request(url, data=json.dumps(payload).encode(), headers=request_headers)
        with urlopen(request, timeout=external_request_timeout()) as response:
            result = json.loads(response.read().decode())
    except HTTPError as exc:
        # Downstream answered with an error status (e.g. the blockchain bridge
        # reporting ON_CHAIN_EXECUTION_FAILED): surface its message instead of
        # a generic "unavailable" so the UI shows what actually broke.
        try:
            body = exc.read().decode()[:300]
        except Exception:
            body = ""
        detail = body
        try:
            data = json.loads(body or "{}")
            detail = data.get("message") or data.get("error") or body
        except ValueError:
            pass
        raise ExternalServiceUnavailable(
            f"External service error HTTP {exc.code}: {detail or exc.reason}".strip()[:300]
        ) from exc
    except (OSError, ValueError, URLError) as exc:
        raise ExternalServiceUnavailable(
            f"Could not reach {url} — the service may be offline or unreachable from this host."
        ) from exc
    if not isinstance(result, dict):
        raise ExternalServiceUnavailable("External scoring service returned an invalid response.")
    return result


def api_keys_required() -> bool:
    """Whether inter-system calls must present API keys.

    All DAIRE subsystems (lender, AI, blockchain) run on one trusted network.
    API keys are opt-in hardening: set REQUIRE_API_KEYS=true in the
    environment to enforce them; with the default (false) every endpoint
    accepts plain, keyless JSON — same network, no credentials.
    """
    return os.environ.get("REQUIRE_API_KEYS", "false").strip().lower() in ("1", "true", "yes", "on")


def blockchain_rpc_headers() -> dict[str, str]:
    """Headers for the blockchain scoring gateway.

    The bridge authenticates callers with its own credential: whenever
    BLOCKCHAIN_API_KEY is configured it is always sent — including in the
    keyless trusted-network mode, which only removes keys on DAIRE-internal
    routes (lender pushes, result broadcasts), never for external services
    that demand their own auth.
    """
    api_key = os.environ.get("BLOCKCHAIN_API_KEY", "")
    return {"X-API-Key": api_key} if api_key else {}


# Fixed path every lender subsystem exposes for result broadcasts from Central.
# Lenders register only their base URL; Central appends this path.
LENDER_BROADCAST_PATH = "/api/daire/central/receive/"


def lender_broadcast_url(api_base_url: str) -> str:
    """The lender receive endpoint: {registered base URL}{LENDER_BROADCAST_PATH}.

    A base URL that already ends with the receive path is accepted as-is so a
    lender configured with the full endpoint still works.
    """
    base = (api_base_url or "").rstrip("/")
    if base.endswith(LENDER_BROADCAST_PATH.rstrip("/")):
        return base + "/"
    return f"{base}{LENDER_BROADCAST_PATH}"


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    if not url:
        raise ExternalServiceUnavailable("External data service is unavailable: URL is not configured.")
    try:
        request_headers = {"Accept": "application/json", **(headers or {})}
        with urlopen(Request(url, headers=request_headers), timeout=lender_request_timeout()) as response:
            result = json.loads(response.read().decode())
    except (OSError, ValueError, URLError) as exc:
        raise ExternalServiceUnavailable(
            f"Could not reach {url} — the service may be offline or unreachable from this host."
        ) from exc
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


# ---------------------------------------------------------------------------
# Lender payload whitelist — the exact contract of LENDER_SUBSYSTEM_README.md.
# Anything outside this format is IGNORED: stripped before merge and recorded
# in the receiving account's `ignored_fields` audit list. Never merged, never
# scored.
# ---------------------------------------------------------------------------
LENDER_CONTRACT_TOP_LEVEL = {
    # identity
    "borrower_reference", "customer_id", "nida_number", "age", "gender", "employment_status", "income",
    # business / account summary
    "business_information", "account_information", "account_reference", "account_name",
    # financial aggregates
    "transaction_frequency", "income_frequency", "savings", "balance_stability",
    "cash_flow_patterns", "account_activity",
    # rows
    "transactions", "balance_history", "loans",
    # provenance
    "verification", "source_metadata",
    # documented lightweight aggregates (§11.4 — alternative to rows)
    "transaction_count", "transaction_total_amount", "transaction_currency",
    "income_count", "income_total_amount", "transaction_period_start",
    "transaction_period_end", "transaction_summary",
}

LENDER_TRANSACTION_FIELDS = {
    "transaction_id", "account_reference", "transaction_date", "value_date", "type",
    "category", "description", "amount", "currency", "direction", "balance_after",
    "counterparty", "status",
}

LENDER_BALANCE_FIELDS = {"date", "account_reference", "closing_balance", "currency"}

LENDER_LOAN_FIELDS = {
    "loan_id", "loan_reference", "account_reference", "loan_amount", "loan_date",
    "loan_duration_months", "interest_rate", "outstanding_balance", "credit_limit",
    "status", "default_status", "repayments",
}

LENDER_REPAYMENT_FIELDS = {
    "repayment_id", "repayment_amount", "repayment_date", "due_date", "days_overdue",
    "missed_payments", "late_payments", "default_status", "status",
}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _strict_decimal(value: Any) -> Decimal | None:
    """Decimal or None — unlike _coerce_decimal, never invents a default."""
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None


def _filter_record(record: Any, allowed: set[str], label: str, ignored: list[str]) -> dict[str, Any] | None:
    """Keep only whitelisted keys of a dict row; report anything dropped."""
    if not isinstance(record, dict):
        ignored.append(f"{label} (not an object)")
        return None
    clean: dict[str, Any] = {}
    for key, value in record.items():
        if key in allowed:
            clean[key] = value
        else:
            ignored.append(f"{label}.{key}")
    return clean


def validate_and_filter_lender_payload(payload: Any) -> tuple[dict[str, Any], list[str]]:
    """Enforce the lender JSON contract: return (clean_payload, ignored_fields).

    Every field not in the contract is removed (and reported). Values with the
    wrong type (e.g. age="old", income="abc", transactions rows without a
    transaction_id) are dropped too — a value out of format is as unusable as
    a field out of format.
    """
    ignored: list[str] = []
    if not isinstance(payload, dict):
        raise ValidationError("Lender payload must be a JSON object matching the DAIRE contract.")

    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if key in LENDER_CONTRACT_TOP_LEVEL:
            clean[key] = value
        else:
            ignored.append(key)

    # --- typed scalars: keep only contract-valid values ---------------------
    age = clean.get("age")
    if "age" in clean and not (_is_number(age) and 0 <= float(age) <= 150):
        del clean["age"]
        ignored.append("age (invalid value)")
    for field in ("income", "savings"):
        value = clean.get(field)
        if field in clean and value is not None:
            coerced = _strict_decimal(value)
            if coerced is None or coerced < 0:
                del clean[field]
                ignored.append(f"{field} (invalid value)")
    stability = clean.get("balance_stability")
    if "balance_stability" in clean and stability is not None and (
        not _is_number(stability) or not 0 <= float(stability) <= 1
    ):
        del clean["balance_stability"]
        ignored.append("balance_stability (invalid value)")
    for field in ("transaction_frequency", "income_frequency"):
        value = clean.get(field)
        if field in clean and value is not None:
            try:
                if int(value) < 0:
                    raise ValueError
            except (TypeError, ValueError):
                del clean[field]
                ignored.append(f"{field} (invalid value)")
    for field in ("borrower_reference", "customer_id", "account_reference", "account_name", "gender", "employment_status"):
        value = clean.get(field)
        if field in clean and value is not None and not isinstance(value, str):
            if _is_number(value):
                clean[field] = str(value)
            else:
                del clean[field]
                ignored.append(f"{field} (invalid type)")
    for field in ("business_information", "account_information", "cash_flow_patterns",
                  "account_activity", "verification", "source_metadata", "transaction_summary"):
        if field in clean and clean[field] is not None and not isinstance(clean[field], dict):
            del clean[field]
            ignored.append(f"{field} (not an object)")

    # --- row arrays: whitelist keys, drop rows lacking required identity ----
    transactions = clean.get("transactions")
    if transactions is not None:
        kept_rows = []
        if isinstance(transactions, list):
            for index, row in enumerate(transactions):
                filtered = _filter_record(row, LENDER_TRANSACTION_FIELDS, f"transactions[{index}]", ignored)
                if filtered is None:
                    continue
                if not filtered.get("transaction_id") or _strict_decimal(filtered.get("amount")) is None:
                    ignored.append(f"transactions[{index}] (missing transaction_id or amount)")
                    continue
                kept_rows.append(filtered)
        else:
            ignored.append("transactions (not a list)")
        clean["transactions"] = kept_rows

    balances = clean.get("balance_history")
    if balances is not None:
        kept_rows = []
        if isinstance(balances, list):
            for index, row in enumerate(balances):
                filtered = _filter_record(row, LENDER_BALANCE_FIELDS, f"balance_history[{index}]", ignored)
                if filtered is None:
                    continue
                if not filtered.get("date") or _strict_decimal(filtered.get("closing_balance")) is None:
                    ignored.append(f"balance_history[{index}] (missing date or closing_balance)")
                    continue
                kept_rows.append(filtered)
        else:
            ignored.append("balance_history (not a list)")
        clean["balance_history"] = kept_rows

    loans = clean.get("loans")
    if loans is not None:
        kept_loans = []
        if isinstance(loans, list):
            for index, loan in enumerate(loans):
                filtered = _filter_record(loan, LENDER_LOAN_FIELDS, f"loans[{index}]", ignored)
                if filtered is None:
                    continue
                if not (filtered.get("loan_id") or filtered.get("loan_reference")):
                    ignored.append(f"loans[{index}] (missing loan_id)")
                    continue
                repayments = filtered.get("repayments")
                kept_repayments = []
                if repayments is not None:
                    if isinstance(repayments, list):
                        for r_index, repayment in enumerate(repayments):
                            r_filtered = _filter_record(
                                repayment, LENDER_REPAYMENT_FIELDS, f"loans[{index}].repayments[{r_index}]", ignored)
                            if r_filtered is None:
                                continue
                            if _strict_decimal(r_filtered.get("repayment_amount")) is None:
                                ignored.append(f"loans[{index}].repayments[{r_index}] (missing repayment_amount)")
                                continue
                            kept_repayments.append(r_filtered)
                    else:
                        ignored.append(f"loans[{index}].repayments (not a list)")
                filtered["repayments"] = kept_repayments
                kept_loans.append(filtered)
        else:
            ignored.append("loans (not a list)")
        clean["loans"] = kept_loans

    return clean, ignored


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


def _record_borrower_conflicts(borrower: Borrower, lender: Lender, payload: dict[str, Any]) -> None:
    """Keep source differences visible while retaining the latest normalized value."""
    comparable_fields = ("customer_id", "age", "gender", "employment_status", "income", "nida_number")
    conflicts = list(borrower.data_conflicts or [])
    for field in comparable_fields:
        existing = getattr(borrower, field)
        incoming = payload.get(field)
        if existing in (None, "") or incoming in (None, ""):
            continue
        if str(existing) == str(incoming):
            continue
        conflict = {
            "field": field,
            "source_lender": lender.institution_name,
            "existing_value": str(existing),
            "incoming_value": str(incoming),
            "resolution": "LATEST_SOURCE_WINS",
            "detected_at": timezone.now().isoformat(),
        }
        conflicts = [item for item in conflicts if not (
            item.get("field") == field and item.get("source_lender") == lender.institution_name
        )]
        conflicts.append(conflict)
    borrower.data_conflicts = conflicts[-100:]
    borrower.save(update_fields=("data_conflicts", "updated_at"))


def _coerce_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_transactions(payload: dict[str, Any]) -> dict[str, Any]:
    """Count + totals for the reporting period without requiring every row.

    Lenders SHOULD send the lightweight summary instead of thousands of
    ``transactions`` rows. Accepted shapes (top-level wins over nested)::

        {"transaction_count": 240, "transaction_total_amount": 18400000,
         "transaction_currency": "TZS", "income_count": 24,
         "income_total_amount": 14400000,
         "transaction_period_start": "2024-02-01", "transaction_period_end": "2025-01-31"}
        {"transaction_summary": {"count": 240, "total_amount": 18400000, ...}}

    When a ``transactions`` array IS sent it remains the source of truth and
    the summary is derived from it (array wins over any stated aggregates).
    Falls back to the legacy ``transaction_frequency`` count when nothing else
    is provided.
    """
    nested = payload.get("transaction_summary")
    nested = nested if isinstance(nested, dict) else {}
    pick = lambda *names: next(
        (payload.get(name) for name in names if payload.get(name) not in (None, "")),
        next((nested.get(name) for name in names if nested.get(name) not in (None, "")), None),
    )
    rows = payload.get("transactions")
    summary: dict[str, Any] = {
        "count": None,
        "total_amount": _coerce_float(pick("transaction_total_amount", "total_amount")),
        "currency": pick("transaction_currency", "currency"),
        "income_count": None,
        "income_total_amount": _coerce_float(pick("income_total_amount")),
        "period_start": pick("transaction_period_start", "period_start"),
        "period_end": pick("transaction_period_end", "period_end"),
    }
    if isinstance(rows, list) and rows:
        total, income_total, income_count = 0.0, 0.0, 0
        for item in rows:
            if not isinstance(item, dict):
                continue
            amount = _coerce_float(item.get("amount")) or 0.0
            total += amount
            if str(item.get("type") or "").upper() == "INCOME":
                income_count += 1
                income_total += amount
        summary.update(count=len(rows), total_amount=round(total, 4),
                       income_count=income_count, income_total_amount=round(income_total, 4))
    else:
        count = pick("transaction_count", "count")
        try:
            count = int(count) if count is not None else None
        except (TypeError, ValueError):
            count = None
        if count is None:
            try:
                count = int(payload.get("transaction_frequency") or 0) or None
            except (TypeError, ValueError):
                count = None
        income_count = pick("income_count")
        try:
            income_count = int(income_count) if income_count is not None else None
        except (TypeError, ValueError):
            income_count = None
        if income_count is None:
            try:
                income_count = int(payload.get("income_frequency") or 0) or None
            except (TypeError, ValueError):
                income_count = None
        summary.update(count=count, income_count=income_count)
    return summary


def merge_vendor_borrower_data(*, lender: Lender, borrower_reference: str, payload: dict[str, Any], account_reference: str | None = None):
    # Contract enforcement: only fields in the DAIRE lender format survive.
    # Anything outside the format is dropped here and reported for audit.
    payload, ignored_fields = validate_and_filter_lender_payload(payload)
    returned_reference = str(payload.get("borrower_reference") or borrower_reference).strip()
    if returned_reference != borrower_reference:
        raise ValidationError("Lender data borrower_reference does not match the requested borrower.")
    borrower, _ = Borrower.objects.get_or_create(borrower_reference=borrower_reference)
    _record_borrower_conflicts(borrower, lender, payload)
    # Materialize the canonical reference. NIDA is the lender's global unique
    # customer identifier, so prefer linking on it when the lender sent one;
    # fall back to the central borrower_reference otherwise. This keeps two
    # lenders sharing a customer_id from merging into two records.
    nida_number = str(payload.get("nida_number") or "").strip()
    if nida_number:
        # Unique on nida_number: no two central borrowers may hold the same
        # national id. If a borrower already holds this NIDA under a different
        # reference, re-point it to that borrower (never create a dup).
        existing = Borrower.objects.filter(nida_number=nida_number).first()
        if existing:
            borrower = existing
        else:
            borrower, _ = Borrower.objects.get_or_create(
                borrower_reference=borrower_reference, defaults={"nida_number": nida_number}
            )
    else:
        borrower, _ = Borrower.objects.get_or_create(borrower_reference=borrower_reference)
    # Always materialise nida_number onto the borrower when the lender sent
    # one, so the persisted record carries the lender's global customer id
    # even when re-merging an existing borrower that was found by reference.
    if nida_number:
        borrower.nida_number = nida_number
    _record_borrower_conflicts(borrower, lender, payload)
    # --- IDs are plain numbers (001, 002, 003 …). Lenders may send them as
    # JSON numbers or strings — normalize to string so 2 and "2" merge into one
    # record instead of creating duplicates.
    customer_id = payload.get("customer_id")
    borrower.customer_id = (
        str(customer_id) if customer_id not in (None, "")
        else (borrower.customer_id or borrower_reference)
    )
    borrower.age = payload.get("age") or borrower.age
    borrower.gender = payload.get("gender") or borrower.gender
    borrower.employment_status = payload.get("employment_status") or borrower.employment_status
    borrower.income = _coerce_decimal(payload.get("income")) if payload.get("income") is not None else borrower.income
    borrower.business_information = payload.get("business_information") or borrower.business_information or {}
    borrower.account_information = payload.get("account_information") or borrower.account_information or {}
    borrower.save(update_fields=(
        "customer_id", "age", "gender", "employment_status", "income",
        "business_information", "account_information", "nida_number", "updated_at",
    ))

    account_key = account_reference or payload.get("account_reference") or payload.get("account_number") or borrower.customer_id
    account_key = str(account_key) if account_key not in (None, "") else ""
    tx_summary = summarize_transactions(payload)
    borrower_account, _ = BorrowerAccount.objects.update_or_create(
        borrower=borrower,
        lender=lender,
        account_reference=account_key,
        defaults={
            "account_name": payload.get("account_name") or lender.institution_name,
            "customer_id": borrower.customer_id,
            "metadata": {
                "transaction_frequency": payload.get("transaction_frequency") or tx_summary["count"] or 0,
                "income_frequency": payload.get("income_frequency") or tx_summary["income_count"] or 0,
                "savings": payload.get("savings", 0),
                "balance_stability": payload.get("balance_stability", 0),
                "cash_flow_patterns": payload.get("cash_flow_patterns", {}),
                "account_activity": payload.get("account_activity", {}),
                # Lightweight aggregates (preferred over raw rows, §11.4).
                "transaction_count": tx_summary["count"],
                "transaction_total_amount": tx_summary["total_amount"],
                "transaction_currency": tx_summary["currency"],
                "income_total_amount": tx_summary["income_total_amount"],
                "transaction_summary": tx_summary,
                # Full lender contract (LENDER_SUBSYSTEM_README.md) — kept for
                # audit/re-scoring without re-pulling. Loans/repayments are also
                # normalized into their own tables below.
                "transactions": payload.get("transactions", []),
                "balance_history": payload.get("balance_history", []),
                "verification": payload.get("verification", {}),
                "source_metadata": payload.get("source_metadata", {}),
                # Contract enforcement (LENDER_SUBSYSTEM_README.md): fields sent
                # outside the DAIRE format were dropped before merge. Kept here
                # so lenders can see exactly what Central ignored and why.
                "ignored_fields": ignored_fields,
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


LENDER_PUSH_PROFILE_VERSION = "lender-push-v1"


def _synthesize_profile_data(borrower: Borrower) -> dict[str, Any]:
    """Derive the 11 normalized credit features from merged lender records."""
    financial = refresh_borrower_financial_profile(borrower)
    loans = list(BorrowerLoan.objects.filter(borrower=borrower))
    defaulted_statuses = {"DEFAULTED", "WRITTEN_OFF"}
    active_statuses = {"ACTIVE", "CURRENT", "OPEN"}
    defaulted = sum(1 for loan in loans if (loan.status or "") in defaulted_statuses)
    active = sum(1 for loan in loans if (loan.status or "") in active_statuses)
    completed = max(0, len(loans) - active - defaulted)
    repayments = list(RepaymentRecord.objects.filter(borrower=borrower))
    missed = sum(int(record.missed_payments or 0) for record in repayments)
    late = sum(int(record.late_payments or 0) for record in repayments)
    max_overdue = max([int(record.days_overdue or 0) for record in repayments], default=0)
    on_time = sum(
        1 for record in repayments
        if int(record.days_overdue or 0) == 0
        and int(record.missed_payments or 0) == 0
        and int(record.late_payments or 0) == 0
    )
    balance_stability = 0.0
    try:
        stabilities = []
        for account in borrower.accounts.all():
            try:
                stabilities.append(float((account.metadata or {}).get("balance_stability", 0)))
            except (TypeError, ValueError):
                continue
        balance_stability = max(stabilities) if stabilities else 0.0
    except Exception:
        pass
    return {
        "active_loan_count": active,
        "completed_loan_count": completed,
        "defaulted_loan_count": defaulted,
        "total_outstanding_debt": float(financial.total_outstanding_debt) if financial else 0.0,
        "on_time_payment_ratio": round(on_time / len(repayments), 4) if repayments else 1.0,
        "missed_payment_count": missed,
        "late_payment_count": late,
        "max_days_overdue": max_overdue,
        "transaction_frequency": financial.transaction_frequency if financial else 0,
        "income_frequency": financial.income_frequency if financial else 0,
        "balance_stability": balance_stability,
    }


def ensure_credit_profile(borrower: Borrower) -> CreditProfile:
    """Return the latest CreditProfile, synthesizing one from lender data.

    Consent-flow profiles carry an integration_request and are left untouched.
    Lender-push borrowers get a rebuilt ``lender-push-v1`` profile on every
    call so scoring always sees the latest merged data.
    """
    profile = CreditProfile.objects.filter(borrower=borrower).order_by("-created_at").first()
    if profile is not None and profile.source_version == LENDER_PUSH_PROFILE_VERSION:
        profile.profile_data = _synthesize_profile_data(borrower)
        profile.save(update_fields=("profile_data", "updated_at"))
    elif profile is None:
        profile = CreditProfile.objects.create(
            borrower=borrower,
            profile_data=_synthesize_profile_data(borrower),
            source_version=LENDER_PUSH_PROFILE_VERSION,
        )
    FeatureGenerationService().generate(profile)
    return profile


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


def explain_score(*, dimensions: dict[str, int], features: dict[str, Any], borrower: Borrower) -> list[dict[str, Any]]:
    """Return human-readable, bounded reasons behind the five score dimensions."""
    source_count = borrower.accounts.values("lender_id").distinct().count()
    return [
        {"dimension": "D1", "name": "Repayment history", "value": dimensions["D1"],
         "reason": f"Payment timeliness, missed payments and maximum overdue days; on-time ratio is {features.get('on_time_payment_ratio', 0)}."},
        {"dimension": "D2", "name": "Financial activity", "value": dimensions["D2"],
         "reason": f"Transaction frequency is {features.get('transaction_frequency', 0)} and income frequency is {features.get('income_frequency', 0)}."},
        {"dimension": "D3", "name": "Debt and loan history", "value": dimensions["D3"],
         "reason": f"Outstanding debt is {features.get('total_outstanding_debt', 0)} with {features.get('defaulted_loan_count', 0)} defaulted loan(s)."},
        {"dimension": "D4", "name": "Stability trend", "value": dimensions["D4"],
         "reason": f"Balance stability is {features.get('balance_stability', 0)} and the profile includes {features.get('completed_loan_count', 0)} completed loan(s)."},
        {"dimension": "D5", "name": "Cross-lender corroboration", "value": dimensions["D5"],
         "reason": f"The profile has data from {source_count} lender source(s)."},
    ]


def _local_ai_reputation(features: dict[str, Any]) -> dict[str, Any]:
    """Deterministic on-box reputation estimate (0..1 score, 0..100 internals).

    Used when no external AI_ENGINE_URL is configured so the orchestration
    pipeline stays fully functional in development.
    """
    on_time = float(features.get("on_time_payment_ratio", 0))
    defaults = float(features.get("defaulted_loan_count", 0))
    missed = float(features.get("missed_payment_count", 0))
    stability = float(features.get("balance_stability", 0))
    if stability <= 1:
        stability *= 100
    completed = float(features.get("completed_loan_count", 0))
    dti_penalty = min(30, float(features.get("late_payment_count", 0)) * 4)

    score = (
        0.45 * on_time * 100
        + 0.20 * stability
        + 0.20 * min(100, completed * 12)
        + 0.15 * (on_time * 100 if defaults == 0 and missed == 0 else 0)
        - 0.10 * defaults * 40
        - 0.05 * missed * 15
    )
    score = max(0.0, min(1.0, score / 100 - dti_penalty / 400))
    if score >= 0.85:
        reputation, risk = "EXCELLENT", "LOW"
    elif score >= 0.70:
        reputation, risk = "GOOD", "LOW"
    elif score >= 0.55:
        reputation, risk = "MODERATE", "MEDIUM"
    else:
        reputation, risk = "HIGH_RISK", "HIGH"
    return {
        "reputation": reputation,
        "score": round(score, 4),
        "risk_level": risk,
        "behavior_summary": (
            f"On-time ratio {on_time:.0%}, {int(defaults)} default(s), "
            f"{int(missed)} missed payment(s), balance stability {stability:.0f}/100."
        ),
        "model_version": "daire-local-fallback-v1",
        "engine": "LOCAL_FALLBACK",
    }


class AIReputationService:
    """Scores a borrower with the AI reputation engine.

    Priority: external ``AI_ENGINE_URL`` when configured, otherwise the
    trained RandomForest credit-risk model (``new_credit_risk_model.joblib``)
    fed by :func:`build_credit_risk_row`. The legacy deterministic formula is
    kept only as a last resort when the model file cannot be loaded.
    """

    def calculate(self, assessment: Any, features: dict[str, Any]) -> AIReputationResult:
        engine_url = os.environ.get("AI_ENGINE_URL", "")
        if engine_url:
            result = _post_json(engine_url, {
                "assessment_reference": assessment.assessment_reference, "features": features,
            })
        else:
            try:
                model = get_credit_risk_model()
            except ExternalServiceUnavailable:
                model = None
            if model is None:
                result = _local_ai_reputation(features)
            else:
                try:
                    result = _trained_model_reputation(model, build_credit_risk_row(assessment.borrower))
                except ExternalServiceUnavailable:
                    raise
                except Exception as exc:
                    raise ExternalServiceUnavailable("Trained credit model inference failed.") from exc
        return _store_ai_result(assessment, result)


# ---------------------------------------------------------------------------
# Trained credit-risk model (local AI engine).
# ---------------------------------------------------------------------------
# Exact input schema of new_credit_risk_model.joblib (RandomForest, trained on
# credit_risk_dataset.csv). The pipeline median-imputes numerics and maps
# unseen categoricals to 'missing', so central fields we do not collect
# (home ownership, employment length, loan intent/grade) are passed as None
# and imputed exactly as the model was trained to handle.
CREDIT_RISK_MODEL_VERSION = "credit-risk-joblib-v1"
CREDIT_RISK_MODEL_FILENAME = "new_credit_risk_model.joblib"
CREDIT_RISK_MODEL_FEATURES = (
    "person_age", "person_income", "person_home_ownership", "person_emp_length",
    "loan_intent", "loan_grade", "loan_amnt", "loan_int_rate",
    "loan_percent_income", "cb_person_default_on_file", "cb_person_cred_hist_length",
)
_ACTIVE_LOAN_STATUSES = ("ACTIVE", "CURRENT", "OPEN")
_DEFAULTED_LOAN_STATUSES = ("DEFAULTED", "WRITTEN_OFF")
_DEFAULTED_REPAYMENT_STATUSES = ("DEFAULTED", "WRITE_OFF", "WRITTEN_OFF")

_model_cache: dict[str, Any] = {"model": None, "failed": False}


def get_credit_risk_model():
    """Load the trained model once and reuse it (40MB file, not per-request)."""
    if _model_cache["model"] is None and not _model_cache["failed"]:
        try:
            import warnings

            from sklearn.exceptions import InconsistentVersionWarning

            # Model was pickled under sklearn 1.9.0, runtime is 1.9.1 (patch-only
            # difference). Silence the unpickle notice; predictions unaffected.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", InconsistentVersionWarning)
                _model_cache["model"] = joblib.load(os.path.join(settings.BASE_DIR, CREDIT_RISK_MODEL_FILENAME))
        except Exception as exc:
            _model_cache["failed"] = True
            raise ExternalServiceUnavailable("Trained credit model is unavailable.") from exc
    if _model_cache["model"] is None:
        raise ExternalServiceUnavailable("Trained credit model is unavailable.")
    return _model_cache["model"]


def _representative_loan(borrower: Borrower) -> BorrowerLoan | None:
    """The loan the model scores: largest active loan, else largest loan ever."""
    loans = list(BorrowerLoan.objects.filter(borrower=borrower))
    if not loans:
        return None
    pool = [loan for loan in loans if (loan.status or "") in _ACTIVE_LOAN_STATUSES] or loans
    return max(pool, key=lambda loan: float(loan.loan_amount or 0))


def _credit_history_years(borrower: Borrower) -> float | None:
    """Years between first and last transaction seen across lender accounts."""
    best: float | None = None
    try:
        accounts = borrower.accounts.all()
    except Exception:
        return None
    for account in accounts:
        try:
            activity = (account.metadata or {}).get("account_activity") or {}
            first = _coerce_date(activity.get("first_transaction_date"))
            last = _coerce_date(activity.get("last_transaction_date")) or timezone.now().date()
            if first is None or last is None or last < first:
                continue
            years = (last - first).days / 365.25
            if best is None or years > best:
                best = years
        except Exception:
            continue
    return round(best, 2) if best is not None else None


def build_credit_risk_row(borrower: Borrower) -> dict[str, Any]:
    """Map unified central borrower data onto the trained model's 11 columns.

    | Model column              | Central source                                          |
    |---------------------------|---------------------------------------------------------|
    | person_age                | Borrower.age                                            |
    | person_income             | Borrower.income                                         |
    | person_home_ownership     | not collected -> None (imputed 'missing')               |
    | person_emp_length         | not collected -> None (training-median imputed)         |
    | loan_intent               | not collected -> None (imputed 'missing')               |
    | loan_grade                | not collected -> None (imputed 'missing')               |
    | loan_amnt                 | representative loan amount                              |
    | loan_int_rate             | representative loan interest rate                       |
    | loan_percent_income       | loan_amnt / person_income                               |
    | cb_person_default_on_file | 'Y' if a defaulted loan/repayment exists else 'N'       |
    | cb_person_cred_hist_length| years of transaction history across accounts            |
    """
    income = getattr(borrower, "income", None)
    income_value = float(income) if income not in (None, "") else None
    loan = _representative_loan(borrower)
    loan_amount = float(loan.loan_amount) if loan is not None and loan.loan_amount else None
    loan_rate = float(loan.interest_rate) if loan is not None and loan.interest_rate else None
    percent_income = None
    if loan_amount and income_value:
        percent_income = round(loan_amount / income_value, 4)

    defaulted = BorrowerLoan.objects.filter(
        borrower=borrower, status__in=list(_DEFAULTED_LOAN_STATUSES),
    ).exists()
    if not defaulted:
        defaulted = RepaymentRecord.objects.filter(
            borrower=borrower, default_status__in=list(_DEFAULTED_REPAYMENT_STATUSES),
        ).exists()

    return {
        "person_age": getattr(borrower, "age", None),
        "person_income": income_value,
        "person_home_ownership": None,
        "person_emp_length": None,
        "loan_intent": None,
        "loan_grade": None,
        "loan_amnt": loan_amount,
        "loan_int_rate": loan_rate,
        "loan_percent_income": percent_income,
        "cb_person_default_on_file": "Y" if defaulted else "N",
        "cb_person_cred_hist_length": _credit_history_years(borrower),
    }


def _trained_model_reputation(model, row: dict[str, Any]) -> dict[str, Any]:
    """Run the trained RandomForest and map {prediction, proba} to reputation."""
    frame = pd.DataFrame([{name: row.get(name) for name in CREDIT_RISK_MODEL_FEATURES}])
    default_proba = float(model.predict_proba(frame)[0][list(model.classes_).index(1)])
    prediction = int(default_proba >= 0.5)
    score = round(1.0 - default_proba, 4)
    if score >= 0.85:
        reputation, risk = "EXCELLENT", "LOW"
    elif score >= 0.70:
        reputation, risk = "GOOD", "LOW"
    elif score >= 0.55:
        reputation, risk = "MODERATE", "MEDIUM"
    else:
        reputation, risk = "HIGH_RISK", "HIGH"
    inputs = {name: row.get(name) for name in CREDIT_RISK_MODEL_FEATURES}
    loan_part = (
        f"loan {inputs['loan_amnt']} at {inputs['loan_int_rate']}% "
        if inputs["loan_amnt"] is not None else "no recorded loan "
    )
    return {
        "reputation": reputation,
        "score": score,
        "risk_level": risk,
        "behavior_summary": (
            f"Trained-model default probability {default_proba:.0%} on {loan_part}"
            f"(income {inputs['person_income']}, prior default on file: {inputs['cb_person_default_on_file']})."
        ),
        "model_version": CREDIT_RISK_MODEL_VERSION,
        "engine": "TRAINED_MODEL",
        "prediction": prediction,
        "default_probability": round(default_proba, 4),
        "model_inputs": inputs,
    }


def _store_ai_result(assessment: Any, result: dict[str, Any]) -> AIReputationResult:
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
        result = _post_json(
            os.environ.get("BLOCKCHAIN_RPC_URL", ""),
            {
                "method": "calculateScore",
                "contract_address": os.environ.get("SMART_CONTRACT_ADDRESS", ""),
                "assessment_reference": assessment.assessment_reference,
                "schema_version": "credit-dimensions-v1",
                "dimensions": dimensions,
            },
            headers=blockchain_rpc_headers(),
        )
        # Accept both the original spec shape (flat) and the gateway shape
        # ({"success": true, "data": {"score": ..., "transactionHash": ...}}).
        data = result.get("data") if isinstance(result.get("data"), dict) else result
        raw_score = data.get("score", data.get("credit_score"))
        ruleset_version = str(data.get("version") or data.get("ruleset_version") or "")
        if raw_score is None or not ruleset_version:
            raise ExternalServiceUnavailable("Smart contract service returned an incomplete response.")
        raw_score = int(raw_score)
        # The contract's public credit scale is 350..800. Keep compatibility
        # with local development contracts that still return a 0..100 score.
        credit_score = 350 + round((raw_score / 100) * 450) if 0 <= raw_score <= 100 else raw_score
        credit_score = max(350, min(800, credit_score))
        transaction_hash = data.get("transactionHash") or data.get("transaction_hash") or ""
        block_number = data.get("blockNumber") or data.get("block_number")
        status_value = "CONFIRMED" if result.get("success") or data.get("status") == "CONFIRMED" else (data.get("status") or "PENDING")
        smart_result = SmartContractResult.objects.update_or_create(
            assessment=assessment,
            defaults={
                "credit_score": credit_score, "ruleset_version": ruleset_version,
                "contract_address": data.get("contractAddress") or os.environ.get("SMART_CONTRACT_ADDRESS", ""),
                "raw_result": {
                    **result,
                    "credit_score": credit_score,
                    "raw_credit_score": raw_score,
                    "risk_band": data.get("riskBand", ""),
                    "latency_ms": data.get("latencyMs"),
                },
            },
        )[0]
        if transaction_hash:
            BlockchainTransaction.objects.update_or_create(
                transaction_hash=transaction_hash,
                defaults={
                    "assessment": assessment, "network": os.environ.get("BLOCKCHAIN_NETWORK", ""),
                    "block_number": block_number, "status": status_value,
                    "verification_data": result,
                },
            )
            assessment.blockchain_transaction_hash = transaction_hash
            assessment.blockchain_block_number = block_number
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
        # Primary: the gateway's assessment lookup endpoint (by assessment reference).
        base = rpc_url.rsplit("/", 1)[0]
        lookup_url = f"{base}/assessment/{assessment.assessment_reference}"
        try:
            result = _get_json(lookup_url, headers=blockchain_rpc_headers())
            data = result.get("data") if isinstance(result.get("data"), dict) else result
            status_value = data.get("status") or ("CONFIRMED" if result.get("success") else "PENDING")
            block_number = data.get("blockNumber") or data.get("block_number")
            if data.get("transactionHash") and data["transactionHash"] != transaction_hash:
                status_value = "MISMATCH"
            return BlockchainTransaction.objects.update_or_create(
                transaction_hash=transaction_hash,
                defaults={
                    "assessment": assessment, "network": os.environ.get("BLOCKCHAIN_NETWORK", ""),
                    "block_number": block_number, "status": status_value,
                    "verification_data": result,
                },
            )[0]
        except ExternalServiceUnavailable:
            pass
        # Fallback: original POST verify protocol.
        result = _post_json(rpc_url, {"method": "verify", "transaction_hash": transaction_hash}, headers=blockchain_rpc_headers())
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
