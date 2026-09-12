# DAIRE Central System

The first increment provides the Django/DRF central integration layer. It keeps lender data behind consent checks and normalizes it before later AI reputation and smart-contract scoring integrations.

## Run locally

```bash
cd backend
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

JWT tokens are available at `POST /api/auth/token/`. Use `Bearer <access-token>` for API calls. OpenAPI documentation is at `/api/docs/`.

Create a lender, borrower, and active consent, then request normalized credit data:

```json
POST /api/integrations/request-credit-data/
{
  "lender_id": "LENDER-001",
  "borrower_reference": "BRW-001",
  "consent_reference": "CONSENT-001"
}
```

The lender adapter is intentionally isolated in `core/services.py`; replace `MockLenderAdapter` with a lender-specific adapter without changing the API or orchestration contract. The AI and blockchain services are not implemented in this increment, so no central code calculates a final credit score.

## Unified borrower data

Vendor systems can submit normalized borrower data to `POST /api/borrowers/ingest/`:

```json
{
  "lender_id": "LDR-NMB-02",
  "borrower_reference": "BRW-TZ-1001",
  "account_reference": "NMB-ACCOUNT-001",
  "payload": {
    "customer_id": "CUST-001",
    "age": 29,
    "employment_status": "EMPLOYED",
    "income": 1200000,
    "transaction_frequency": 12,
    "income_frequency": 4,
    "savings": 250000,
    "loans": [{
      "loan_id": "NMB-LOAN-1",
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
        "default_status": "CLEAR"
      }]
    }]
  }
}
```

Submit the same canonical `borrower_reference` for NMB, CRDB, M-Pesa, Mixx by Yas, or a microfinance institution. The system keeps each lender/account/loan source and recalculates the borrower-level totals. Search the merged view with `GET /api/borrowers/search/?lender_name=NMB&account_reference=NMB-ACCOUNT-001`.

## Data routing and synchronization

Manage the active field policy through `/api/routing-policies/`. It has separate `ai_fields` and `blockchain_fields`; only those fields are sent by the scoring actions. Every exchange is visible through read-only `/api/data-exchanges/`.

- CRUD central records: `/api/borrowers/`, `/api/borrower-accounts/`, `/api/borrower-loans/`, `/api/repayments/`, `/api/borrower-financial-profiles/`, `/api/credit-profiles/`, `/api/features/`
- Pull lender data: `POST /api/lenders/{id}/pull-borrower-data/`
- Push central data to a lender: `POST /api/lenders/{id}/push-borrower-data/`
- Push to AI: `POST /api/assessments/{reference}/ai-reputation/`; read the stored AI result with `GET /api/assessments/{reference}/ai-result/`
- Push to blockchain: `POST /api/assessments/{reference}/blockchain-score/`; pull verification with `GET /api/assessments/{reference}/verify/`

## Frontend

The Angular operations console is in `frontend/`. Start the Django API first, then:

```bash
cd frontend
npm install
npm start -- --port 4200
```

Open `http://localhost:4200`. The development proxy forwards `/api` requests to Django on port 8000 by default. Choose any backend and frontend ports when starting the services:

```bash
# Terminal 1
cd backend
python manage.py runserver 0.0.0.0:9000

# Terminal 2
cd frontend
BACKEND_PORT=9000 npm start -- --port 4300
```

Create a Django superuser and use those credentials on the login screen.
