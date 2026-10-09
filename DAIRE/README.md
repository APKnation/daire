# DAIRE Central System

DAIRE is a central credit-data orchestration system. It receives or pulls
borrower data from registered lender systems, combines the data by borrower
reference, builds a normalized credit profile, sends only approved fields to AI
and blockchain services, stores the results, and broadcasts the exact result
back to each lender linked to that borrower.

DAIRE is not itself a lender and it does not replace a lender's core banking
system. It is the trusted coordination and assessment layer between lenders,
the AI engine, and the blockchain gateway.

## Main capabilities

- Register lenders and their API base URLs.
- Receive lender data through push or pull it from all eligible lenders.
- Match every record using the canonical `borrower_reference`.
- Merge accounts, loans, repayments, transactions, and borrower attributes.
- Keep lender-specific sources and record conflicts between lenders.
- Generate a normalized credit profile and reusable scoring features.
- Run a trained local Random Forest model or call an external AI engine.
- Convert central features into five bounded dimensions for blockchain scoring.
- Store assessment, AI, blockchain, transaction, and audit records.
- Broadcast each borrower’s exact assessment result to the borrower’s linked lenders.
- Provide a Django REST API and Angular operations console.

## Architecture

```text
Lender systems
     │
     │ push / pull JSON for one borrower_reference
     ▼
DAIRE Central API
     │  validate, normalize, merge, audit
     ▼
Borrower + accounts + loans + repayments + financial profile
     │
     ├── 11 normalized credit features ──► AI engine / local Random Forest
     │                                      reputation and default probability
     │
     └── 5 bounded dimensions ───────────► Blockchain gateway / smart contract
                                            credit score and transaction hash
     │
     ▼
Exact assessment result broadcast to every lender linked to that borrower
```

One assessment belongs to one borrower. If borrower `1001` is assessed, the
AI result, blockchain result, and broadcast all use borrower `1001` and the
same `assessment_reference`. Results from another borrower cannot be mixed into
that assessment.

## Technology

- Backend: Python, Django 5.2, Django REST Framework, PostgreSQL.
- Authentication: Django session login for the console. Inter-system API-key
  enforcement is optional and controlled by `REQUIRE_API_KEYS`.
- Frontend: Angular, TypeScript, Tailwind-style utility classes.
- Local AI: scikit-learn `Pipeline` containing preprocessing and
  `RandomForestClassifier`.
- Model storage: `backend/new_credit_risk_model.joblib`.
- Blockchain integration: HTTP JSON gateway or smart-contract service.
- API documentation: drf-spectacular at `/api/docs/` and `/api/schema/`.

## Project layout

```text
DAIRE/
├── backend/
│   ├── config/                 Django settings and URLs
│   ├── core/
│   │   ├── models.py           Database models
│   │   ├── serializers.py      API response and request serializers
│   │   ├── services.py         Merge, feature, AI and blockchain logic
│   │   ├── views.py            REST endpoints and orchestration
│   │   ├── tests.py            Backend tests
│   │   └── management/         Seed-data command
│   ├── new_credit_risk_model.joblib
│   ├── requirements.txt
│   └── manage.py
├── frontend/                   Angular operations console
├── AI_DATA_CONTRACT.md         AI request/response contract
├── LENDER_SUBSYSTEM_README.md  Lender integration contract
├── docker-compose.yml          Local PostgreSQL service
└── credit_risk_dataset.csv     Training dataset used by the model
```

## Local installation

### 1. Start PostgreSQL

```bash
cd DAIRE
docker compose up -d postgres
```

The compose file exposes PostgreSQL on host port `5433` and uses database,
user, and password `daire` for local development.

### 2. Configure the backend

```bash
cd backend
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
```

`DATABASE_URL` must point to PostgreSQL. The application does not use SQLite as
its configured production database.

### 3. Optional demo data

```bash
python manage.py seed_data
```

The command creates demo lenders, borrowers, accounts, loans, repayments,
profiles, assessments, and mock lender URLs.

### 4. Run the backend

```bash
python manage.py runserver 0.0.0.0:8000
```

Useful backend URLs:

| URL | Purpose |
|---|---|
| `http://localhost:8000/admin/` | Django administration |
| `http://localhost:8000/health/` | Database health check |
| `http://localhost:8000/api/docs/` | Swagger API documentation |
| `http://localhost:8000/api/schema/` | OpenAPI schema |

### 5. Run the frontend

```bash
cd frontend
npm install
npm start -- --port 4200
```

Open `http://localhost:4200`. The Angular development proxy forwards `/api`
requests to the backend.

## Environment variables

Copy `backend/.env.example` to `backend/.env` and set values for the current
environment.

| Variable | Meaning |
|---|---|
| `SECRET_KEY` | Django secret key. Use a strong private value outside development. |
| `DEBUG` | Django debug mode. Keep `False` in production. |
| `ALLOWED_HOSTS` | Comma-separated allowed backend hosts. |
| `DATABASE_URL` | PostgreSQL connection URL. |
| `REQUIRE_API_KEYS` | If `true`, lender receive and broadcast routes enforce API keys. |
| `DAIRE_EXTERNAL_TIMEOUT` | Timeout in seconds for AI, blockchain, and other external scoring calls. Default `30`. |
| `DAIRE_LENDER_TIMEOUT` | Timeout in seconds for each lender pull. Default `8`. Lender pulls run concurrently. |
| `AI_ENGINE_URL` | Optional external AI endpoint. Empty means use the local trained model. |
| `AI_ENGINE_API_KEY` | Optional credential for an external AI service. |
| `BLOCKCHAIN_RPC_URL` | Blockchain scoring gateway endpoint. Required for live blockchain scoring. |
| `BLOCKCHAIN_API_KEY` | Credential sent to the blockchain gateway as `X-API-Key`. |
| `BLOCKCHAIN_NETWORK` | Network name stored with blockchain transactions. |
| `SMART_CONTRACT_ADDRESS` | Contract address sent to the blockchain gateway. |
| `CSRF_TRUSTED_ORIGINS` | Frontend origins allowed to make browser requests. |

## Borrower and lender identity

### Lender identity

Every lender must be registered in Central before it can participate in a pull
or receive a broadcast. A lender has:

- `lender_id`: stable machine identity, unique in Central.
- `institution_name`: display name.
- `institution_type`: bank, mobile money, microfinance, or another category.
- `api_base_url`: lender data endpoint base URL (broadcasts go to `{api_base_url}/api/daire/central/receive/`).
- `lookup_path`: path appended to `api_base_url` for borrower pulls (default `borrowers`; override per lender, e.g. `api/daire/borrowers/` for the live NMB/CRDB subsystem on `172.17.16.70:8002`).
- `api_status`: `CONNECTED`, `DEGRADED`, or `DISCONNECTED`.

Central pulls only lenders marked `CONNECTED` or `DEGRADED`. `DISCONNECTED`
lenders are skipped so an offline system does not delay an assessment.

### Borrower identity

`borrower_reference` is the single cross-system identity used to match data.
All lender systems must send the same reference for the same borrower. A lender
must not use its institution name as a replacement for the reference.

Example:

```json
{
  "borrower_reference": "1001"
}
```

When a lender sends data for borrower `1001`, Central merges it only into
borrower `1001`. It never creates one assessment containing several borrowers.

## Data flow

### One-click assessment flow

The console's **Perform assessment** action executes this sequence:

1. Pull borrower data concurrently from all connected or degraded lenders.
2. Validate that each response belongs to the requested `borrower_reference`.
3. Merge every successful lender response into that borrower.
4. Create a new `assessment_reference` for that borrower.
5. Send the normalized AI feature set to the AI service.
6. Send the blockchain dimensions to the blockchain service.
7. Display both returned results for that borrower.
8. Wait for the operator to click **Broadcast**.
9. Broadcast that exact assessment result to every linked lender.

AI and blockchain calls are sequential because both update the same assessment
and local development databases can otherwise race while writing it.

### Push from lender to Central

```http
POST /api/lender-data/receive/
Content-Type: application/json
```

The request can contain a wrapper:

```json
{
  "lender_id": "LDR-NMB-02",
  "borrower_reference": "1001",
  "payload": {
    "customer_id": "001",
    "age": 29,
    "employment_status": "EMPLOYED",
    "income": 1200000,
    "account_reference": "3001",
    "loans": []
  }
}
```

Central also accepts compatible flat lender payloads. The lender ID may be
resolved from the request body, nested lender object, accepted headers, or a
registered API key, but sending the registered `lender_id` in the JSON body is
recommended.

### Pull from all lenders

```http
POST /api/borrowers/pull-from-all-lenders/
Content-Type: application/json
```

```json
{
  "borrower_reference": "1001"
}
```

Each eligible lender is called concurrently. A slow lender fails independently
after `DAIRE_LENDER_TIMEOUT`; successful lenders can still be merged and used
for the assessment.

## Data model

### `Lender`

Stores the registered institution, connection state, API URL, and credentials.
Inbound API keys are stored as hashes. The outbound broadcast key is retained
only because the lender must validate the exact credential Central sends.

### `Borrower`

Stores the central borrower identity and common attributes such as age, gender,
employment status, income, customer ID, business information, and conflict
records.

### `BorrowerAccount`

Stores the relationship between one borrower and one lender. The uniqueness
rule is borrower + lender + account reference.

### `BorrowerLoan`

Stores lender-owned loan records including amount, date, duration, interest
rate, outstanding balance, and status. A loan is unique by borrower + lender +
loan ID.

### `RepaymentRecord`

Stores repayment amount and dates, days overdue, missed payments, late
payments, and default status.

### `BorrowerFinancialProfile`

Stores central aggregates derived from all linked accounts and loans:
transaction frequency, income frequency, savings, active loans, total debt,
monthly repayment, previous loans, debt-to-income ratio, and activity metadata.

### `CreditProfile` and `CreditFeature`

`CreditProfile` is the normalized scoring input for one borrower. Its
`profile_data` contains the 11 central scoring features. `CreditFeature` stores
the same values as named, auditable numeric records.

### `Assessment`

Stores one scoring run for one borrower. It contains the assessment reference,
AI reputation result, blockchain credit score, model/ruleset versions,
transaction identifiers, score inputs, and explanations.

### `AIReputationResult`

Stores the AI reputation, probability-derived score, risk level, model version,
behavior summary, and raw AI response.

### `SmartContractResult` and `BlockchainTransaction`

Store the blockchain score, ruleset version, contract address, transaction hash,
network, block number, status, and gateway response.

### `DataRoutingPolicy`

Controls which normalized fields may leave Central. It has separate field lists
for lenders, AI, and blockchain. This prevents raw lender data from being sent
to a destination that does not need it.

### `DataExchange`

Audits every inter-system operation. It records system, direction, operation,
status, borrower, lender, assessment, policy, fields sent, payload, response,
and error message.

## AI model

### Which algorithm is used?

The local model is a supervised binary classification pipeline using:

```text
Median imputation + StandardScaler for numeric columns
Constant "missing" imputation + OneHotEncoder for categorical columns
RandomForestClassifier(n_estimators=100, random_state=42)
```

The model predicts `loan_status`:

- `0`: healthy loan / not classified as high risk.
- `1`: high-risk loan / default class.

The saved model is `backend/new_credit_risk_model.joblib`. The runtime model
version is `credit-risk-joblib-v1`.

The old `SKLEARN-Credit_Risk_Prediction-Supervised_ML/README.md` describes an
earlier Logistic Regression exercise. That description is historical and does
not describe the model currently loaded by DAIRE. The authoritative current
training code is:

```text
SKLEARN-Credit_Risk_Prediction-Supervised_ML/Credit_Risk/train_new_model.py
```

### How was the model trained?

1. Load `credit_risk_dataset.csv` with pandas.
2. Separate `loan_status` as the target `y`.
3. Use all other listed columns as input `X`.
4. Split data into 80% training and 20% testing data.
5. Use `random_state=42` and `stratify=y` so the class ratio is preserved.
6. Impute missing numeric values with the median.
7. Standardize numeric values with `StandardScaler`.
8. Impute missing categorical values with `missing`.
9. One-hot encode categorical values with unknown-value handling enabled.
10. Train 100 Random Forest trees.
11. Evaluate with accuracy and a classification report.
12. Save the complete preprocessing-plus-model pipeline with joblib.

The training script prints the actual accuracy, precision, recall, F1-score,
and support for the current dataset when it runs. Metrics should not be copied
from the legacy README because they may not represent the current dataset or
model artifact.

### Exact training columns

The dataset contains these columns:

| Column | Role | Meaning |
|---|---|---|
| `person_age` | Feature | Borrower age. |
| `person_income` | Feature | Borrower income. |
| `person_home_ownership` | Feature | Home ownership category. |
| `person_emp_length` | Feature | Employment length. |
| `loan_intent` | Feature | Stated purpose of the loan. |
| `loan_grade` | Feature | Loan grade/risk band. |
| `loan_amnt` | Feature | Loan amount. |
| `loan_int_rate` | Feature | Loan interest rate. |
| `loan_percent_income` | Feature | Loan amount divided by income. |
| `cb_person_default_on_file` | Feature | Historical default flag, `Y` or `N`. |
| `cb_person_cred_hist_length` | Feature | Credit history length in years. |
| `loan_status` | Target | `0` healthy, `1` high risk/default. |

### How Central maps borrower data to the model

When `AI_ENGINE_URL` is empty, DAIRE builds one model row from the selected
borrower:

| Model column | Central source |
|---|---|
| `person_age` | `Borrower.age` |
| `person_income` | `Borrower.income` |
| `person_home_ownership` | Not currently collected; sent as missing and imputed. |
| `person_emp_length` | Not currently collected; sent as missing and median-imputed. |
| `loan_intent` | Not currently collected; sent as missing and imputed. |
| `loan_grade` | Not currently collected; sent as missing and imputed. |
| `loan_amnt` | Largest active/current/open loan, or largest loan if none is active. |
| `loan_int_rate` | Interest rate from that representative loan. |
| `loan_percent_income` | Representative loan amount divided by borrower income. |
| `cb_person_default_on_file` | `Y` if a defaulted loan or repayment exists, otherwise `N`. |
| `cb_person_cred_hist_length` | Years between the earliest and latest account activity dates. |

The model returns `P(class 1)` as `default_probability`. DAIRE calculates the
AI reputation score as:

```text
reputation_score = 1 - default_probability
```

The labels are mapped as follows:

| Reputation score | Reputation | Risk |
|---:|---|---|
| `>= 0.85` | `EXCELLENT` | `LOW` |
| `>= 0.70` | `GOOD` | `LOW` |
| `>= 0.55` | `MODERATE` | `MEDIUM` |
| `< 0.55` | `HIGH_RISK` | `HIGH` |

### External AI option

If `AI_ENGINE_URL` is configured, Central sends the normalized 11-feature AI
payload to that endpoint instead of running the local joblib model. The external
engine must return at least:

```json
{
  "reputation": "GOOD",
  "score": 0.82,
  "risk_level": "LOW",
  "behavior_summary": "...",
  "model_version": "external-model-v1"
}
```

The response must include `reputation`, `score`, and `model_version`. Central
stores the complete response in `AIReputationResult.raw_result`.

### Local fallback

If no external AI URL is configured, Central first uses the trained Random
Forest. If the model file cannot be loaded, the code has a deterministic local
formula fallback (`daire-local-fallback-v1`) based on repayment, stability,
completed loans, defaults, and missed payments. This fallback is for continuity
in development and is not the trained model.

## Data sent to AI

The default normalized AI feature set contains 11 fields:

| Field | Meaning |
|---|---|
| `active_loan_count` | Active/current/open loans. |
| `completed_loan_count` | Loans completed successfully. |
| `defaulted_loan_count` | Defaulted or written-off loans. |
| `total_outstanding_debt` | Total balance still owed. |
| `on_time_payment_ratio` | On-time repayments divided by all repayments, from `0` to `1`. |
| `missed_payment_count` | Number of missed payments. |
| `late_payment_count` | Number of late payments. |
| `max_days_overdue` | Maximum overdue days. |
| `transaction_frequency` | Number of transactions in the reporting period. |
| `income_frequency` | Number of income transactions in the reporting period. |
| `balance_stability` | Account balance stability, represented as `0..1` or `0..100`. |

Only fields allowed by the active `DataRoutingPolicy.ai_fields` list are sent
to an external AI engine. The borrower reference and assessment reference are
used for correlation and audit. Raw transaction rows, raw repayment rows, and
unnecessary identity data should not be sent to AI.

## Data sent to blockchain

The blockchain service does not receive raw transactions, full repayment rows,
identity evidence, or the complete borrower profile. Central converts the
normalized features into five bounded dimensions:

| Dimension | Name | Main inputs |
|---|---|---|
| `D1` | Repayment history | On-time ratio, overdue days, missed payments. |
| `D2` | Financial activity | Transaction frequency, income frequency, balance stability. |
| `D3` | Debt and loan history | Defaults, completed loans, debt-to-income ratio. |
| `D4` | Stability trend | Activity regularity and default history. |
| `D5` | Cross-lender corroboration | Number of linked lender sources. |

Each dimension is bounded to `0..100`. The blockchain gateway receives:

```json
{
  "method": "calculateScore",
  "contract_address": "0x...",
  "assessment_reference": "ASM-2026-0001",
  "schema_version": "credit-dimensions-v1",
  "dimensions": {
    "D1": 92,
    "D2": 78,
    "D3": 84,
    "D4": 71,
    "D5": 60
  }
}
```

The gateway may return a `0..100` score or a final `350..800` credit score.
Central converts a `0..100` response to the public `350..800` scale and stores
the transaction hash, block number, network, ruleset version, and raw response.

## What remains in Central

Central stores the detailed borrower and lender data needed for audit and
recalculation:

- borrower identity and reference;
- lender and account relationships;
- loan and repayment records;
- transaction aggregates and permitted metadata;
- financial profile and normalized credit features;
- AI inputs and raw AI response;
- blockchain dimensions and raw gateway response;
- assessment explanations and exchange history.

The frontend does not need to display every stored field. The operations UI
uses borrower references, assessment results, and operational status while the
full records remain available to backend APIs and authorized administration.

## Core API endpoints

### Authentication and operations

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/auth/login/` | Start Django session. |
| `POST` | `/api/auth/logout/` | End session. |
| `GET` | `/api/auth/me/` | Check current session. |
| `GET` | `/api/dashboard/` | Dashboard aggregates. |
| `GET` | `/health/` | Liveness and database check. |

### Registry and data

| Method | Endpoint | Purpose |
|---|---|---|
| `GET/POST` | `/api/lenders/` | List or register lenders. |
| `GET/PATCH` | `/api/lenders/{id}/` | Read or update a lender. |
| `GET/POST` | `/api/borrowers/` | Read or create central borrower records. |
| `GET` | `/api/borrowers/search/` | Search borrowers by reference, lender, or account. |
| `POST` | `/api/lender-data/receive/` | Receive lender-pushed borrower data. |
| `POST` | `/api/borrowers/ingest/` | Ingest normalized lender data. |
| `POST` | `/api/borrowers/pull-from-all-lenders/` | Pull one borrower from eligible lenders. |
| `GET` | `/api/data-exchanges/` | Read inter-system audit records. |
| `GET/PATCH` | `/api/routing-policies/` | Read or update field routing policy. |

### Assessment and scoring

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/assessments/` | Create an assessment for one borrower. |
| `POST` | `/api/assessments/{reference}/ai-reputation/` | Run AI scoring. |
| `GET` | `/api/assessments/{reference}/ai-result/` | Read stored AI result. |
| `POST` | `/api/assessments/{reference}/blockchain-score/` | Run blockchain scoring. |
| `GET` | `/api/assessments/{reference}/verify/` | Verify blockchain transaction. |
| `POST` | `/api/borrowers/{id}/broadcast-result/` | Broadcast exact result to linked lenders. |
| `POST` | `/api/predict_credit_risk/` | Direct model prediction using raw 11-column model input. |

## Broadcast behavior

After AI and blockchain scoring, Central creates one combined result for the
selected assessment. It finds all distinct lenders connected to that borrower
through `BorrowerAccount` and sends the same assessment-specific result to each
lender's receive endpoint:

```text
{lender.api_base_url}/api/daire/central/receive/
```

The broadcast includes the borrower reference, assessment reference, AI result,
blockchain result, and score explanation. It does not send another borrower's
result and does not use only the latest global AI/blockchain result. Each lender
must match the incoming `borrower_reference` locally before storing or showing
the result to its customer.

## Lender payload guidance

Lenders should send compact aggregates instead of thousands of transaction rows
when possible. Useful fields include:

- borrower reference and customer ID;
- age, employment status, and actual income;
- stable account reference;
- transaction count and total amount;
- income count and total amount;
- balance stability and account activity dates;
- loan ID, amount, rate, outstanding balance, and status;
- repayment amount, due date, payment date, overdue days, missed/late counts,
  and default status.

Central validates the payload, ignores unsupported fields, keeps source lender
records, and recalculates borrower aggregates after a successful merge.

## Meaning of important fields

- `income_frequency`: the number of income transactions in the selected
  reporting period. It is not the amount of income. For example, 24 means 24
  income events, possibly two per month over 12 months.
- `transaction_frequency`: the total number of transactions in the selected
  reporting period.
- `on_time_payment_ratio`: on-time repayments divided by all recorded
  repayments. When no repayment records exist, the current implementation uses
  `1.0` as the neutral starting value; production policy may choose to treat
  missing history separately.
- `debt_to_income_ratio`: total outstanding debt divided by borrower income.
- `borrower_reference`: the cross-lender customer key used for matching.
- `assessment_reference`: the unique key for one scoring run for one borrower.

## Security and privacy

- Use HTTPS between systems outside a trusted local network.
- Set `REQUIRE_API_KEYS=true` when lender or scoring systems are not fully
  isolated on a trusted network.
- Never expose API-key hashes or outbound credentials in serializers or logs.
- Send only fields required by AI and blockchain routing policies.
- Keep raw lender information in Central and send derived dimensions to
  blockchain.
- Validate that the borrower reference in a response equals the requested
  borrower reference before merging.
- Do not display or broadcast one borrower's result to another borrower.
- Use PostgreSQL backups and restrict database/admin access.

## Retraining the local model

The training source is:

```text
SKLEARN-Credit_Risk_Prediction-Supervised_ML/Credit_Risk/train_new_model.py
```

From that directory, run:

```bash
cd SKLEARN-Credit_Risk_Prediction-Supervised_ML/Credit_Risk
python train_new_model.py
```

The script reads `credit_risk_dataset.csv`, prints evaluation metrics, and
writes `new_credit_risk_model.joblib`. Copy the resulting artifact to:

```text
DAIRE/backend/new_credit_risk_model.joblib
```

Before deploying a new model, verify that:

1. The feature names and target semantics have not changed.
2. The dataset does not contain leakage from future repayment outcomes.
3. The test split and class distribution are appropriate.
4. Precision, recall, F1-score, confusion matrix, and calibration are reviewed.
5. The model version is updated in `services.py`.
6. The new artifact is tested against representative borrower records.

The model is a decision-support component. Its probability is not a legal or
automatic lending decision by itself. A lender should combine it with policy,
consent, affordability checks, fraud controls, and human or regulated decision
processes where required.

## Tests and validation

With backend dependencies installed:

```bash
cd backend
python manage.py test core
```

For the frontend:

```bash
cd frontend
npm run build
```

The frontend build may show a CommonJS warning for `sweetalert2`; this is an
optimization warning and does not mean the build failed.

## Related documentation

- [`AI_DATA_CONTRACT.md`](AI_DATA_CONTRACT.md): detailed AI request and response contract.
- [`LENDER_SUBSYSTEM_README.md`](LENDER_SUBSYSTEM_README.md): lender integration and broadcast contract.
- [`docs/nmb-lender-integration-guide.html`](docs/nmb-lender-integration-guide.html): browser-readable lender integration guide.
- [`backend/core/services.py`](backend/core/services.py): authoritative feature derivation, model mapping, AI, and blockchain logic.
- [`SKLEARN-Credit_Risk_Prediction-Supervised_ML/Credit_Risk/train_new_model.py`](../SKLEARN-Credit_Risk_Prediction-Supervised_ML/Credit_Risk/train_new_model.py): authoritative current training script.

## AI questions and answers

### Does AI assess several borrowers together?

No. One assessment is created for one `borrower_reference`. A lender pull may
query several lender systems, but the returned records are merged only for the
selected borrower. Every AI and blockchain request carries that assessment's
reference.

### Does AI receive raw lender data?

By default, no. Central derives normalized features and applies the active AI
routing policy. The local model receives its own 11-column model row. Raw
transactions and detailed repayment rows remain in Central.

### What does AI predict?

The trained model predicts the probability that the representative loan belongs
to class `1`, the high-risk/default class. DAIRE converts that probability to a
reputation score by subtracting it from one.

### Why are some model columns missing?

The current Central borrower schema does not collect home ownership, employment
length, loan intent, or loan grade. The trained pipeline handles those missing
values through imputation. Adding those fields to lender payloads and mapping
them in `build_credit_risk_row` would improve the information available to the
model, but the model should then be retrained and evaluated with the same
schema.

### Is the AI score the same as the blockchain score?

No. AI returns a reputation and default probability. Blockchain receives five
bounded dimensions and returns the authoritative contract credit score. Both
results belong to the same assessment but are produced by different systems.

### What is stored on blockchain?

Only the bounded dimensions and the resulting score/transaction metadata should
cross the blockchain boundary. Raw identity, raw transactions, repayment rows,
and detailed lender data remain off-chain in Central.

### Can the result for one borrower be sent to another borrower?

The Central broadcast uses the exact assessment reference and borrower
reference, then sends the result only to lenders linked to that borrower. Lender
systems must perform the same borrower-reference check before displaying it.

### What happens if one lender is offline?

Disconnected lenders are skipped. Connected and degraded lenders are queried in
parallel. A lender that exceeds `DAIRE_LENDER_TIMEOUT` fails independently, and
successful lender responses can still produce a partial assessment.

### What happens if the external AI service is unavailable?

If `AI_ENGINE_URL` is configured and unavailable, the scoring request returns an
error and the failed exchange is recorded. If no external URL is configured,
DAIRE uses the local trained Random Forest. A deterministic formula remains as
the final development fallback if the model artifact cannot be loaded.

### What happens if the blockchain service is unavailable?

The blockchain exchange is marked failed and the API returns the downstream
error. The AI result remains stored, but the assessment should not be treated as
fully completed until the blockchain step succeeds according to local policy.

### How can the model be improved?

Collect reliable values for the currently missing columns, use a representative
and consented local lending dataset, remove data leakage, evaluate the default
class using recall and calibration rather than accuracy alone, retrain the
pipeline, version the artifact, and compare it with the previous model before
deployment.
