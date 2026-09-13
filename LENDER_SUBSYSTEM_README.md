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
CENTRAL_API_KEY=replace-me
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

DAIRE Central System calls the lender subsystem using:

```http
GET /borrowers?borrower_reference=BRW-TZ-1001
Authorization: Bearer <central-system-token>
Accept: application/json
```

The exact URL is configured in the lender registry as `api_base_url`.

### Successful response

Return HTTP `200` with one JSON object matching the contract below.

```json
{
  "borrower_reference": "BRW-TZ-1001",
  "customer_id": "NMB-CUST-0001",
  "age": 29,
  "gender": "MALE",
  "employment_status": "EMPLOYED",
  "income": 1200000.0000,
  "business_information": {
    "business_name": "Amina Foods",
    "business_type": "RETAIL",
    "registration_number": "BRELA-12345",
    "business_start_date": "2020-05-01"
  },
  "account_information": {
    "account_count": 2,
    "currency": "TZS",
    "customer_since": "2020-01-15"
  },
  "account_reference": "NMB-ACC-0001",
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
      "transaction_id": "TX-0001",
      "account_reference": "NMB-ACC-0001",
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
      "account_reference": "NMB-ACC-0001",
      "closing_balance": 850000.0000,
      "currency": "TZS"
    }
  ],
  "loans": [
    {
      "loan_id": "NMB-LOAN-0001",
      "loan_reference": "NMB-LOAN-0001",
      "account_reference": "NMB-ACC-0001",
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
          "repayment_id": "NMB-REPAY-0001",
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
  "transaction_id": "unique-lender-transaction-id",
  "account_reference": "account-id",
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
  "borrower_reference": "BRW-TZ-1001"
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
  "borrower_reference": "BRW-TZ-1001",
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
- The endpoint has authentication, rate limiting, and audit logging.
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
