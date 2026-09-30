# DAIRE Central System — Database Documentation

**Project:** DAIRE — Decentralized AI Reputation Engine
**Database:** PostgreSQL 16 (owner `daire`), defined by Django models in `DAIRE/backend/core/models.py`
**Role:** The Central System (Credit Information Hub) database is the **system of record** — it holds all raw, identifying borrower data. The blockchain holds **none** of it (see §5).

Every `core_*` table inherits `created_at` + `updated_at` timestamps.

---

## 1. Entity map (how the tables relate)

```
Lender ──┬──< BorrowerAccount >──┐
         ├──< BorrowerLoan ──────┤
         ├──< RepaymentRecord    │
         ├──< Consent >──────────┤
         ├──< IntegrationRequest>┤
         │                       ▼
         │                   Borrower ──1:1── BorrowerFinancialProfile
         │                       │
         │                       ├──< CreditProfile ──< CreditFeature
         │                       │
         │                       └──< Assessment ──1:1── AIReputationResult
         │                                 │    ──1:1── SmartContractResult
         │                                 │    ──<    BlockchainTransaction
         │                                 └──<    DataExchange
         └──< DataExchange / DataRoutingPolicy
```

---

## 2. Parties — who participates

### `core_lender` — registered lender institutions

| Column | Type | Notes |
|---|---|---|
| `lender_id` | varchar(64), unique | Business id, e.g. `LDR-DEMO-FLOW` |
| `institution_name` | varchar(255) | Display name |
| `institution_type` | varchar(100) | Bank / MFI / mobile lender … |
| `api_base_url` | URL | Lender's endpoint for pushes |
| `api_status` | varchar(20) | `CONNECTED` \| `DEGRADED` \| `DISCONNECTED` |
| `authentication_method` | varchar(50) | Default `API_KEY` |
| `api_key_hash` | varchar(128) | **SHA-256 of inbound key only** — plaintext never stored |
| `api_key_prefix` | varchar(16) | First 12 chars, for identification in admin |
| `broadcast_api_key` | varchar(128) | Outbound key Central presents **to** the lender when pushing results (plaintext by necessity — the lender validates the exact value) |

### `core_borrower` — the person (PII zone — never leaves this database)

| Column | Type | Notes |
|---|---|---|
| `borrower_reference` | varchar(64), unique | Central's unique borrower id |
| `nida_number` | varchar(128), unique, nullable | National ID (e.g. Tanzanian NIDA). Preferred global link key across lenders |
| `name` | varchar(255) | Full name |
| `is_active` | boolean | Soft-active flag |
| `customer_id` | varchar(64) | Lender-side customer id |
| `age` | smallint | Years |
| `gender` | varchar(20) | |
| `employment_status` | varchar(50) | |
| `income` | decimal(16,4) | Income in TZS |
| `business_information` | JSON | Free-form business details from lenders |
| `account_information` | JSON | Free-form account details |
| `data_conflicts` | JSON | Conflicting values received from different lenders |

> Newest-received first (`ordering = -created_at`): the pull-receiving frontend lists borrowers in arrival order.

---

## 3. Raw borrower data — what lenders send in

### `core_borroweraccount` — accounts held at each lender
| Column | Notes |
|---|---|
| `borrower` FK → Borrower | |
| `lender` FK → Lender | unique together: (borrower, lender, account_reference) |
| `account_reference` | e.g. `8834010` |
| `account_name` | e.g. `Nia account` |
| `customer_id` | Lender-side id |
| `metadata` | JSON — anything else the lender sends |

### `core_borrowerloan` — loans per lender
| Column | Notes |
|---|---|
| `borrower`, `lender` FK | unique together: (borrower, lender, loan_id) |
| `source_account` FK → BorrowerAccount | nullable |
| `loan_id` | Lender's loan number |
| `loan_amount` | decimal(18,4) — principal |
| `loan_date` | date of origination |
| `loan_duration_months` | term |
| `interest_rate` | decimal(8,4) |
| `outstanding_balance` | current balance |
| `status` | `ACTIVE` / closed states |

### `core_repaymentrecord` — repayment history (feeds D1 on-chain)
| Column | Notes |
|---|---|
| `loan` FK → BorrowerLoan | cascade on loan delete |
| `repayment_amount` | decimal(18,4) |
| `repayment_date` | actual payment date |
| `due_date` | scheduled date |
| `days_overdue` | lateness in days (→ `maxDaysLate`) |
| `missed_payments` | count (→ `missedCount`) |
| `late_payments` | count |
| `default_status` | e.g. `DEFAULT`, `CHARGED_OFF` |

### `core_loanapplication` — the loan the borrower is APPLYING for (feeds D3 + AI `loan_amnt`)
The **new** loan being requested — distinct from `core_borrowerloan` (existing history). Lenders push it inside the data payload (`payload.loan_application`); assessments can also create one directly. The assessment scores the **merged** cross-lender history PLUS this single application.

| Column | Notes |
|---|---|
| `borrower` FK → Borrower | the unified (NIDA-linked) borrower |
| `lender` FK → Lender | nullable — Central may record an application before lender attribution |
| `application_reference` | stable id; unique per (borrower, lender, reference) |
| `applied_amount` | decimal(18,4) — **the real amount the borrower applied for** |
| `currency` | default `TZS` |
| `purpose`, `term_months`, `interest_rate` | application terms |
| `status` | `SUBMITTED` → `ASSESSED` → `APPROVED` / `DECLINED` |
| `assessment` FK → Assessment | the assessment that scored this application |
| `payload` | JSON — the lender's original application object |

The applied amount becomes `applied_loan_amount` in the scoring profile: the AI model receives it as `loan_amnt`, and the blockchain D3 dimension penalises how many months of income it represents (plus existing debt from all lenders).

**Decision lifecycle:** `POST /api/loan-applications/{id}/decision/` records `APPROVED` / `DECLINED` (or `ASSESSED`) and links the deciding `Assessment` — explicitly by `assessment_reference`, or automatically to the borrower's latest assessment. Cross-borrower assessment links are rejected; admin log keeps the audit trail. The unified borrower payload (`/api/borrowers/search/`) exposes every application with its `status` and `assessment_reference`, which the frontend borrower detail view renders with an Approve/Decline action.

### `core_borrowerfinancialprofile` — one per borrower (feeds D2/D4)
| Column | Notes |
|---|---|
| `borrower` FK | OneToOne |
| `transaction_frequency` | transactions per month |
| `income_frequency` | paydays per month |
| `cash_flow_patterns` | JSON — inflow/outflow patterns |
| `savings` | balance |
| `account_activity` | JSON |
| `active_loans`, `previous_loans` | counts |
| `total_outstanding_debt`, `monthly_repayment` | exposure |
| `debt_to_income_ratio` | decimal(9,4) |

---

## 4. Governance, pipeline & results

### `core_consent` — data-sharing permission (checked before every exchange)
| Column | Notes |
|---|---|
| `consent_id` | varchar(64), unique |
| `borrower`, `lender` FK | Who shares with whom |
| `purpose` | varchar(255) |
| `granted_at`, `expires_at` | validity window |
| `status` | `ACTIVE` \| `EXPIRED` \| `REVOKED` |

### `core_integrationrequest` — audit of every inbound data push/pull
| Column | Notes |
|---|---|
| `request_reference` | UUID, unique |
| `lender`, `borrower`, `consent` FK | context |
| `status` | `RECEIVED` \| `VALIDATED` \| `REJECTED` \| `COMPLETED` |
| `error_message` | why rejected |
| `raw_payload` | JSON — **the exact payload the lender sent** |

### `core_creditprofile` + `core_creditfeature` — normalized scoring inputs
| Table | Column | Notes |
|---|---|---|
| `core_creditprofile` | `borrower` FK | immutable snapshot |
| | `integration_request` OneToOne | provenance |
| | `profile_data` | JSON — normalized fields |
| | `source_version` | schema version |
| `core_creditfeature` | `profile` FK | unique together: (profile, name) |
| | `name`, `value` | e.g. `on_time_ratio` = 0.9750 |
| | `feature_version` | feature-set version |

### `core_assessment` — the unified score record
| Column | Notes |
|---|---|
| `assessment_reference` | varchar(64), unique |
| `borrower` FK | who was scored |
| `reputation` | varchar(30) label |
| `reputation_score` | decimal(5,4) 0–1 |
| `risk_level` | varchar(20) |
| `behavior_summary` | text |
| `credit_score` | 300–850 |
| `ruleset_version` | e.g. `DAIRE-RULES-2.0-US-RANGE` |
| `model_version` | AI model version |
| `blockchain_transaction_hash`, `blockchain_block_number` | on-chain proof |
| `verification_status` | `PENDING` → verified |
| `score_inputs` | JSON — features used |
| `score_explanation` | JSON — reason codes |

### `core_aireputationresult` vs `core_smartcontractresult` — AI and chain kept separate
| Table | Stores |
|---|---|
| `core_aireputationresult` (1:1 Assessment) | AI layer only: `reputation`, `score`, `risk_level`, `behavior_summary`, `model_version`, `raw_result` JSON |
| `core_smartcontractresult` (1:1 Assessment) | Chain only: `credit_score`, `ruleset_version`, `contract_address`, `raw_result` JSON |

### `core_blockchaintransaction` — tx proofs (many per assessment)
| Column | Notes |
|---|---|
| `transaction_hash` | unique |
| `network` | e.g. `sepolia` / `localhost` |
| `block_number`, `status` | confirmation state |
| `verification_data` | JSON — receipt details |

### `core_dataroutingpolicy` + `core_dataexchange` — outbound control & audit
| Table | Column | Notes |
|---|---|---|
| `core_dataroutingpolicy` | `policy_id`, `name` | named policy |
| | `lender_fields`, `ai_fields`, `blockchain_fields` | JSON whitelists — **which fields may leave Central, per destination** |
| | `active`, `version` | |
| `core_dataexchange` | `system` | `LENDER` \| `AI` \| `BLOCKCHAIN` |
| | `direction` | `PUSH` \| `PULL` |
| | `operation`, `batch_reference` | what ran, batch id (indexed) |
| | `borrower`, `lender`, `assessment`, `policy` FK | context |
| | `status` | `STARTED` \| `COMPLETED` \| `FAILED` |
| | `fields_sent` | JSON list |
| | `payload`, `response` | JSON — full request and reply |
| | `error_message` | failure detail |

---

## 5. The storage rule — what lives where

| Data | PostgreSQL (these tables) | Blockchain |
|---|---|---|
| Name, NIDA, age, gender | ✅ `core_borrower` | ❌ never |
| Income, savings, balances | ✅ `core_borrower` / `core_borrowerfinancialprofile` | ❌ never |
| Loan amounts, dates, TZS values | ✅ `core_borrowerloan`, `core_repaymentrecord` | ❌ never |
| Applied loan amount (the new loan being requested) | ✅ `core_loanapplication` | ❌ never (only the resulting score) |
| API keys | ✅ `core_lender` (hash inbound / outbound key) | ❌ never |
| Full payloads & responses | ✅ `core_integrationrequest`, `core_dataexchange` | ❌ never |
| `borrowerRef` (keccak256 of id + salt) | ✅ the link map | ✅ only identifier on-chain |
| Derived integers (features, bps) | ✅ `core_creditfeature`, `score_inputs` | ✅ features tuple |
| Dimensions D1–D5, score 300–850, band, version | ✅ `core_assessment` | ✅ `Assessment` struct |
| Tx hash, block, network | ✅ `core_blockchaintransaction` | ✅ itself |

**Why:** on-chain data is public and immutable forever, so only non-identifying numbers go there. Because PostgreSQL holds the only `borrowerRef ↔ person` map, deleting that row after the BoT 6-year retention window makes the on-chain numbers unlinkable to any person (**cryptographic erasure**). Corrections are never deletes: a new `Assessment` version is appended, and the old one stays for audit.

---

## 6. Framework tables (not business data)

`auth_user`, `auth_group`, `auth_permission` (+ join tables), `django_admin_log`, `django_content_type`, `django_migrations`, `django_session` — Django admin/auth plumbing.

Full dump reference: `backup.sql` at the repo root (26 tables total: 17 `core_*` + 9 framework).

---

## 7. Sensitive fields worth protecting

| Field | Why | Protection today |
|---|---|---|
| `core_borrower.nida_number`, `name`, `income` | Direct identifiers / financial PII | Off-chain only; unique index on NIDA |
| `core_lender.broadcast_api_key` | Outbound credential | Plaintext by necessity (lender validates exact value) — restrict DB access |
| `core_lender.api_key_hash` | Inbound credential | SHA-256 hash only; plaintext shown once at issuance |
| `core_integrationrequest.raw_payload`, `core_dataexchange.payload` | Contains whatever lenders sent | Audit-only; follow retention rules |
