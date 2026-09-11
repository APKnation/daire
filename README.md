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
