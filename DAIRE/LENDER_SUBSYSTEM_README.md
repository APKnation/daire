# DAIRE Lender Subsystem Template

This document is a build prompt and integration contract for **one lender subsystem** that connects to DAIRE Central System.

Build one lender implementation from this specification first. After it is working, duplicate the project for another institution and change only the institution configuration, branding, credentials, and internal data adapters.

Recommended first implementation name: `DAIRE NMB Lender Subsystem`.

The same implementation can later be duplicated as:

- `DAIRE CRDB Lender Subsystem`
- `DAIRE MPESA Lender Subsystem`
- `DAIRE MIXX Lender Subsystem`
- `DAIRE MICROFINANCE Lender Subsystem`

## 1. Purpose

The lender subsystem owns the lender's private customer, account, transaction, loan, repayment, and consent data. It must expose a secure API that DAIRE Central System can call using one unique borrower reference.

The lender subsystem must:

1. Find a customer by the unique borrower reference.
2. Return all data that the lender is legally allowed to share.
3. Return an empty/not-found response when the customer does not exist.
4. Never return another customer's data.
5. Use the exact normalized JSON contract in this document.
6. Support audit logging for every data pull.

DAIRE Central System aggregates data from all lender subsystems. The lender subsystem must not calculate the final cross-lender credit score.

## 2. Configuration

Each duplicated lender subsystem must have its own configuration:

```env
LENDER_ID=NMB-001
INSTITUTION_NAME=NMB Bank
INSTITUTION_TYPE=COMMERCIAL_BANK
CENTRAL_SYSTEM_URL=https://central.example.com
# Keyless by default: all subsystems run on one trusted network. Set true
# only if a subsystem is exposed beyond that network.
REQUIRE_API_KEYS=false
DATABASE_URL=postgresql://user:password@localhost:5432/lender_db
```

The lender must be registered in DAIRE Central System with:

```json
{
  "lender_id": "NMB-001",
  "institution_name": "NMB Bank",
  "institution_type": "COMMERCIAL_BANK",
  "api_base_url": "https://nmb-subsystem.example.com",
  "api_status": "CONNECTED",
  "authentication_method": "API_KEY"
}
```

Never commit API keys, passwords, private keys, or customer data to source control.

## 3. Required lender endpoint

**Transport model (applies to every endpoint in this document):** all DAIRE
subsystems — lender, AI engine, blockchain bridge — run on the **same trusted
network**, so inter-system calls are plain HTTP JSON **without API keys** by
default. When `REQUIRE_API_KEYS=true` is set (opt-in hardening for deployments
that expose a subsystem beyond that network), callers must additionally send
`X-API-Key: <key>`; lenders registered without a key stay accepted.

DAIRE Central System calls the lender subsystem using:

```http
GET /borrowers?borrower_reference=1001
Accept: application/json
```

With `REQUIRE_API_KEYS=true` the call instead includes
`Authorization: Bearer <central-system-token>` (or `X-API-Key` for pushes).

The exact URL is configured in the lender registry as `api_base_url`.

### Successful response

Return HTTP `200` with one JSON object matching the contract below.

```json
{
  "borrower_reference": "1001",
  "customer_id": "001",
  "age": 29,
  "gender": "MALE",
  "employment_status": "EMPLOYED",
  "income": 1200000.0000,
  "business_information": {
    "business_name": "Amina Foods",
    "business_type": "RETAIL",
    "registration_number": "12345",
    "business_start_date": "2020-05-01"
  },
  "account_information": {
    "account_count": 2,
    "currency": "TZS",
    "customer_since": "2020-01-15"
  },
  "account_reference": "3001",
  "account_name": "Amina Juma",
  "transaction_frequency": 240,
  "income_frequency": 24,
  "savings": 850000.0000,
  "balance_stability": 0.82,
  "cash_flow_patterns": {
    "average_monthly_income": 1200000.0000,
    "average_monthly_expenses": 700000.0000,
    "income_months": 12,
    "active_months": 12,
    "trend_bps": 1250
  },
  "account_activity": {
    "first_transaction_date": "2024-01-03",
    "last_transaction_date": "2025-01-31",
    "active_months": 12,
    "transaction_count": 240
  },
  "transactions": [
    {
      "transaction_id": "6001",
      "account_reference": "3001",
      "transaction_date": "2025-01-05T10:30:00Z",
      "value_date": "2025-01-05",
      "type": "INCOME",
      "category": "SALARY",
      "description": "Monthly salary",
      "amount": 1200000.0000,
      "currency": "TZS",
      "direction": "CREDIT",
      "balance_after": 1500000.0000,
      "counterparty": "Employer Ltd",
      "status": "COMPLETED"
    }
  ],
  "balance_history": [
    {
      "date": "2025-01-31",
      "account_reference": "3001",
      "closing_balance": 850000.0000,
      "currency": "TZS"
    }
  ],
  "loans": [
    {
      "loan_id": "4001",
      "loan_reference": "4001",
      "account_reference": "3001",
      "loan_amount": 500000.0000,
      "loan_date": "2024-06-12",
      "loan_duration_months": 12,
      "interest_rate": 12.5000,
      "outstanding_balance": 320000.0000,
      "credit_limit": 500000.0000,
      "status": "ACTIVE",
      "default_status": "CLEAR",
      "repayments": [
        {
          "repayment_id": "5001",
          "repayment_amount": 42000.0000,
          "repayment_date": "2025-01-05",
          "due_date": "2025-01-05",
          "days_overdue": 0,
          "missed_payments": 0,
          "late_payments": 0,
          "default_status": "CLEAR",
          "status": "ON_TIME"
        }
      ]
    }
  ],
  "verification": {
    "identity_verified": true,
    "identity_provider": "NIDA",
    "identity_match_score": 1.0,
    "phone_verified": true,
    "account_owner_verified": true,
    "source_verified_at": "2025-02-01T08:00:00Z"
  },
  "source_metadata": {
    "source_system": "NMB_CORE_BANKING",
    "source_version": "2025.1",
    "data_as_of": "2025-01-31T23:59:59Z",
    "currency": "TZS",
    "records_returned": 242
  }
}
```

### Field rules

| Field | Required | Meaning |
|---|---:|---|
| `borrower_reference` | Yes | The central unique identifier requested by DAIRE. |
| `customer_id` | Yes | The lender's internal customer identifier. |
| `age` | No | Customer age in years. |
| `gender` | No | Lender's normalized value. |
| `employment_status` | No | For example `EMPLOYED`, `SELF_EMPLOYED`, `UNEMPLOYED`. |
| `income` | No | Declared or verified income in the lender's currency. |
| `business_information` | No | Structured business details; never send secrets. |
| `account_information` | No | General account summary. |
| `account_reference` | Yes when available | Stable lender account identifier. |
| `account_name` | No | Account holder name. |
| `transaction_frequency` | Yes | Count of transactions in the selected reporting period. |
| `income_frequency` | Yes | Count of income transactions in the selected period. |
| `savings` | No | Current or reporting-period savings total. |
| `balance_stability` | No | Normalized 0–1 stability value. |
| `cash_flow_patterns` | No | Aggregated cash-flow statistics. |
| `account_activity` | No | Aggregated account activity. |
| `transactions` | Recommended | Detailed transactions for central off-chain processing. |
| `balance_history` | Recommended | Daily or monthly balances for stability calculations. |
| `loans` | Yes when present | All current and historical loans for this customer. |
| `verification` | Recommended | Identity and source verification evidence. |
| `source_metadata` | Yes | Provenance, version, timestamp, and currency. |

Use JSON `null` or an empty array/object when data is unavailable. Do not invent zero values for unknown data.

## 4. Transaction contract

Every transaction should use:

```json
{
  "transaction_id": "6002",
  "account_reference": "3001",
  "transaction_date": "2025-01-05T10:30:00Z",
  "value_date": "2025-01-05",
  "type": "INCOME",
  "category": "SALARY",
  "description": "optional description",
  "amount": 1200000.0000,
  "currency": "TZS",
  "direction": "CREDIT",
  "balance_after": 1500000.0000,
  "counterparty": "optional counterparty",
  "status": "COMPLETED"
}
```

Allowed `type` values should include `INCOME`, `EXPENSE`, `TRANSFER`, `LOAN_DISBURSEMENT`, `LOAN_REPAYMENT`, `FEE`, `WITHDRAWAL`, and `DEPOSIT`.

The lender must not send PINs, passwords, card security codes, full authentication tokens, or unnecessary sensitive descriptions.

## 5. Loan and repayment contract

The central system stores these loan fields:

- `loan_id` or `loan_reference`
- `account_reference`
- `loan_amount`
- `loan_date` in `YYYY-MM-DD` format
- `loan_duration_months`
- `interest_rate`
- `outstanding_balance`
- `credit_limit` when available
- `status`: `ACTIVE`, `CURRENT`, `OPEN`, `COMPLETED`, `CLOSED`, `DEFAULTED`, or `WRITTEN_OFF`
- `default_status`
- `repayments`

Each repayment should include:

- `repayment_id`
- `repayment_amount`
- `repayment_date`
- `due_date`
- `days_overdue`
- `missed_payments`
- `late_payments`
- `default_status`
- `status`: `ON_TIME`, `LATE`, `MISSED`, or `DEFAULTED`

Dates must be ISO-formatted. Monetary values must be numeric, not formatted strings, and must include the currency in the surrounding payload.

## 6. Not-found and error behavior

If the borrower does not exist:

```http
404 Not Found
```

```json
{
  "detail": "Borrower not found",
  "borrower_reference": "1001"
}
```

For an invalid request:

```http
400 Bad Request
```

For authentication failure:

```http
401 Unauthorized
```

For a temporary lender outage:

```http
503 Service Unavailable
```

Never return a successful response containing a different customer's records.

## 7. Consent, privacy, and audit requirements

Before returning data, the lender subsystem must verify:

1. The central caller is authenticated.
2. The borrower reference exists.
3. The requested purpose is allowed.
4. Valid customer consent exists, unless a documented legal basis applies.
5. The requested data fields are permitted for that purpose.

For every request, write an audit event containing:

```json
{
  "event": "BORROWER_DATA_SHARED",
  "borrower_reference": "1001",
  "requester": "DAIRE_CENTRAL",
  "purpose": "CREDIT_ASSESSMENT",
  "fields_shared": ["loans", "repayments", "transactions"],
  "requested_at": "2025-02-01T08:00:00Z",
  "completed_at": "2025-02-01T08:00:02Z",
  "status": "COMPLETED",
  "correlation_id": "request-uuid"
}
```

Use encryption in transit, encrypted secrets, access logging, retention limits, and least-privilege service accounts.

## 8. Central-system compatibility checklist

The duplicated lender subsystem is ready when:

- `GET /borrowers?borrower_reference=...` returns the exact JSON shape above.
- A customer not found at this lender returns `404`.
- All dates are ISO formatted.
- All money values are numeric and consistently denominated.
- Every loan has a stable unique `loan_id`.
- Every repayment belongs to a loan.
- Transactions include stable unique IDs and directions.
- The response contains source timestamp and source version.
- No credentials or secret customer security data are returned.
- Duplicate requests are safe and do not create duplicate records.
- The endpoint supports optional authentication (`REQUIRE_API_KEYS=true`), rate limiting, and audit logging; trusted-network deployments run keyless by default.
- The response passes a contract/schema test.
- The lender can explain every field returned to DAIRE.

## 9. Build prompt

Use the following prompt when creating the first lender subsystem:

> Build a production-ready lender data subsystem named `DAIRE NMB Lender Subsystem`. It must expose an authenticated `GET /borrowers?borrower_reference={id}` endpoint for DAIRE Central System. Implement lender-owned models for customers, accounts, transactions, balances, loans, repayments, identity verification, consent, and data-sharing audit logs. Return the exact response contract in `LENDER_SUBSYSTEM_README.md`. Do not calculate the final cross-lender credit score. Include environment configuration, database migrations, seed data, API authentication, validation, rate limiting, audit logging, OpenAPI documentation, automated tests, Docker support, and a README explaining how to run it. Ensure a borrower lookup can only return the requested borrower, and return 404 when no match exists. Use ISO dates, numeric monetary values, stable IDs, source metadata, and TZS currency support. Keep provider-specific adapters isolated so this subsystem can later be duplicated for CRDB, M-Pesa, Mixx by Yas, or another lender by changing configuration and adapters.

## 10. Duplication guide

When duplicating this lender subsystem:

1. Copy the project.
2. Rename the application and branding.
3. Change `LENDER_ID`, institution name, and institution type.
4. Replace the internal customer/account/transaction adapters.
5. Keep the external JSON field names unchanged.
6. Keep the endpoint path unchanged.
7. Register the new `api_base_url` in DAIRE Central System.
8. Configure separate credentials and database storage.
9. Run the contract test against the new lender.
10. Verify that the same borrower lookup returns only that lender's records.

The external contract must remain stable even when the internal lender database schema differs.

## 11. Central acceptance & conflict rules (read this before pushing)

Push to `POST {CENTRAL}/api/lender-data/receive/`. **By default no key header
is needed** — all subsystems share one trusted network. Only when Central runs
with `REQUIRE_API_KEYS=true` must the push carry `X-API-Key: <key>`
(Central issues `lender_id` + key at registration; both are required then).

### 11.1 Identity matching — the single most important rule

Central merges **only on exact `borrower_reference` match**. Every lender must send
the *same* central reference for the same person. One digit off = a second borrower
record is created and the lenders never combine.

| Rule | Consequence if broken |
|---|---|
| Same `borrower_reference` at every lender | Otherwise duplicate borrowers, split history |
| Stable `account_reference` per account | Otherwise duplicate accounts on every push |
| Stable `loan_id` per loan, repayments nested under their loan | Otherwise duplicate loans; orphan repayments are still stored but unattributed |
| `payload.loans` is always a list (empty `[]` when none) | Otherwise `400 payload.loans must be a list` |
| `borrower_reference` inside `payload` equals the top-level one | Otherwise `400` mismatch rejection |

### 11.2 Types and formats Central enforces

- Dates: ISO `YYYY-MM-DD` (`loan_date`, `repayment_date`, `due_date`); datetimes with `Z`.
- Money: JSON numbers (max 4 decimals), never formatted strings; currency belongs in `source_metadata.currency`.
- Enums actually read: loan `status` ∈ `ACTIVE, CURRENT, OPEN, COMPLETED, CLOSED, DEFAULTED, WRITTEN_OFF`; repayment `default_status` marks defaults only when `DEFAULTED/WRITE_OFF/WRITTEN_OFF`; default-on-file flag `Y/N`.
- Unknown/extra fields are kept in account metadata for audit, never scored.

### 11.3 Conflicts — why the dashboard shows them

When two lenders disagree on identity fields (`customer_id`, `age`, `gender`,
`employment_status`, `income`), Central keeps **both**: the latest push wins, and the
losing value is appended to `borrower.data_conflicts` with source lender and timestamp
(`services._record_borrower_conflicts`, resolution `LATEST_SOURCE_WINS`, last 100 kept).
Financial records never conflict — loans/repayments/transactions are keyed per
lender + ID and added together.

Conflicts are *expected* (lenders genuinely hold different snapshots) and visible in
the pull response (`conflicts`) and the borrower record (`data_conflicts`). If the same
pair of lenders conflicts on every borrower, the outlier's upstream data — not Central —
needs fixing. Send `null` (not `0`/guesses) for unknown values so a guess never
overwrites a real value as "latest".

### 11.4 Lightweight pushes — aggregates instead of rows

Do **not** send thousands of `transactions` rows per push. Send counts + totals
(Central scores and stores from these; raw rows are optional audit detail):

```json
{
  "lender_id": "NMB-001",
  "borrower_reference": "1001",
  "account_reference": "3001",
  "payload": {
    "borrower_reference": "1001",
    "customer_id": "001",
    "transaction_count": 240,
    "transaction_total_amount": 18400000.0000,
    "transaction_currency": "TZS",
    "income_count": 24,
    "income_total_amount": 14400000.0000,
    "transaction_period_start": "2024-02-01",
    "transaction_period_end": "2025-01-31",
    "loans": []
  }
}
```

A nested `transaction_summary: {count, total_amount, currency, income_count,
income_total_amount, period_start, period_end}` object is accepted equivalently
(top-level keys win). Rules:

- `transaction_count` = number of transactions in the period; `transaction_total_amount`
  = signed sum of their `amount`s; `income_count` / `income_total_amount` cover `INCOME` rows only.
- If a `transactions` array **is** sent, Central derives the aggregates from it and
  the array wins over any stated numbers.
- With neither rows nor aggregates, Central falls back to the legacy
  `transaction_frequency` / `income_frequency` counts.
- The push response echoes back `transaction_count`, `transaction_total_amount`,
  `transaction_currency`, `income_count`, `income_total_amount` — assert on those
  in your contract test instead of row counts.

## 12. Result broadcast contract (DAIRE Central → Lender subsystem)

After AI and blockchain scoring complete, Central pushes the final credit result
to every lender linked to the borrower. This is what your subsystem must be able
to **receive**.

### 12.1 Request

Central sends an authenticated `POST` for each linked lender to a **fixed receive path**:

```http
POST {your api_base_url}/api/daire/central/receive/
Content-Type: application/json
```

Keyless by default (trusted network); with `REQUIRE_API_KEYS=true` the same
request additionally carries `Authorization: Bearer <central-system-token>`.

You register only your base URL (e.g. `https://nmb-subsystem.example.com`); Central
appends `/api/daire/central/receive/` automatically. To accept broadcasts, expose one
`POST` handler at `{base}/api/daire/central/receive/` that reads the JSON body below.

### 12.2 Body — the exact JSON Central sends

The wrapper identifies the borrower and carries **both scoring results in one
payload**: `results.ai` (AI reputation) and `results.blockchain` (on-chain
score), each present only when that engine has already scored the borrower —
otherwise `null`. The borrower is identified **only** by `borrower_reference` —
match it against your own customer before acting on the payload, and ignore
results for references you do not hold.

`result_type` is `"CREDIT_RESULT"`. `result` repeats the most recently generated
score (kind + timestamp tell you which) so consumers that read a single object
keep working:

```json
{
  "result_type": "CREDIT_RESULT",
  "borrower_reference": "1001",
  "assessment_reference": "ASM-2026-0005",
  "result": {
    "kind": "BLOCKCHAIN_SCORE",
    "generated_at": "2026-09-18T10:35:00Z",
    "id": 1,
    "assessment": 5,
    "credit_score": 652,
    "ruleset_version": "ruleset-v1.0.0",
    "contract_address": "0xabc123...",
    "transaction_hash": "0xabc123...",
    "block_number": 152300,
    "risk_band": "FAIR",
    "raw_result": { "...": "full on-chain response as stored by Central" },
    "created_at": "2026-09-18T10:35:00Z",
    "updated_at": "2026-09-18T10:35:00Z"
  },
  "results": {
    "ai": {
      "id": 1,
      "assessment": 5,
      "reputation": "EXCELLENT",
      "score": "0.9450",
      "risk_level": "LOW",
      "behavior_summary": "Borrower shows consistent on-time repayments across 5 loans with stable monthly income.",
      "model_version": "credit-risk-joblib-v1",
      "raw_result": {
        "reputation": "EXCELLENT",
        "score": 0.945,
        "risk_level": "LOW",
        "behavior_summary": "Borrower shows consistent on-time repayments across 5 loans with stable monthly income.",
        "model_version": "credit-risk-joblib-v1",
        "engine": "TRAINED_MODEL",
        "model_inputs": {
          "person_age": 29,
          "person_income": 1200000.0,
          "person_home_ownership": null,
          "person_emp_length": null,
          "loan_intent": null,
          "loan_grade": null,
          "loan_amnt": 500000.0,
          "loan_int_rate": 12.5,
          "loan_percent_income": 0.4167,
          "cb_person_default_on_file": "N",
          "cb_person_cred_hist_length": 5.04
        }
      },
      "created_at": "2026-09-18T10:30:00Z",
      "updated_at": "2026-09-18T10:30:00Z"
    },
    "blockchain": {
      "id": 1,
      "assessment": 5,
      "credit_score": 652,
      "ruleset_version": "ruleset-v1.0.0",
      "contract_address": "0xabc123...",
      "transaction_hash": "0xabc123...",
      "block_number": 152300,
      "risk_band": "FAIR",
      "raw_result": { "...": "full on-chain response as stored by Central" },
      "created_at": "2026-09-18T10:35:00Z",
      "updated_at": "2026-09-18T10:35:00Z"
    }
  }
}
```

If only AI scoring has run, `results.blockchain` is `null` and `result.kind` is
`"AI_REPUTATION"` (and vice versa).

### 12.3 Which fields carry the borrower's data

| Field | Meaning for you |
|---|---|
| `borrower_reference` | **The key.** The customer id **as held in your own system** (from the `customer_id` you supplied when your data was pulled or pushed). Match it to your customer record — never trust any other identifier. |
| `central_borrower_reference` | The central unified reference (e.g. `1001`) — for audit/reconciliation only. |
| `lender_customer_id` | Same value as `borrower_reference` (kept for explicitness). |
| `assessment_reference` | The assessment the results belong to. |
| `result.kind` / `result.generated_at` | Which engine produced the newest score and when. |
| `results.ai.reputation` | AI reputation band: `EXCELLENT`, `GOOD`, `MODERATE`, `HIGH_RISK`. |
| `results.ai.score` | AI reputation score 0–1. Decimal serialization makes it a **string** (e.g. `"0.9450"`); parse as decimal. |
| `results.ai.risk_level` | `LOW`, `MEDIUM`, or `HIGH` (may be blank on older records). |
| `results.ai.behavior_summary` | One-paragraph explanation of the borrower's financial behavior. |
| `results.ai.model_version` | Which model produced the score (audit trail). |
| `results.blockchain.credit_score` | Blockchain score on the public 350–800 scale. |
| `results.blockchain.transaction_hash` / `.block_number` | On-chain proof; use `verify` if you need independent confirmation. |
| `results.*.raw_result` | Full stored response per engine — for your audit, not for re-decisioning. |

### 12.4 What your endpoint must do

1. Expose the `POST {base}/api/daire/central/receive/` endpoint.
2. Authenticate the caller when `REQUIRE_API_KEYS=true` (the same credential
   you validate on `GET /borrowers`); keyless otherwise.
3. Look up your customer by `borrower_reference`; return `404` if you do not hold that borrower.
4. Store or display the result for that customer only.
5. Reply `200` with any JSON acknowledgement. Central accepts anything; the dev stand-in replies:

```json
{
  "received": true,
  "lender_system": "NMB",
  "result_type": "CREDIT_RESULT",
  "score": null,
  "processed_at": "2026-09-18T10:30:02.123456+00:00"
}
```

`"score"` in your acknowledgement is read from `result.credit_score` when present.

### 12.5 Privacy rules

- Central sends **derived scores only** — never raw transactions, balances,
  repayments, or identity documents. Do not expect (or accept) them here.
- Every broadcast is logged in Central as a `DataExchange`
  (`system=LENDER`, `direction=PUSH`, `operation=broadcast_credit_result`) with
  the exact payload sent, so both sides can reconcile.
- If your subsystem holds no such borrower, still log the attempt and return `404`.
