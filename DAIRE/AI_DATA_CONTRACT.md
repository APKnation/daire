# AI Data Contract (JSON In / JSON Out)

Nyaraka hii inaonyesha **JSON ambayo AI engine anapokea** kutoka DAIRE Central System, na **JSON ambayo Central System anarudishiwa** na AI baada ya kazi (scoring) kuisha.

- Huduma inayotuma: `AIReputationService` (`backend/core/services.py`)
- Endpoint inayoanzisha kazi: `POST /api/assessments/{assessment_reference}/ai-reputation/`
- URL ya AI engine ya nje: `AI_ENGINE_URL` (env variable; ikitajwa, section 1–2 hapa chini
  inaelezea request/response ya engine hiyo. **Isipotajwa, Central inatumia trained
  RandomForest model ya ndani** (`backend/new_credit_risk_model.joblib`,
  `model_version: credit-risk-joblib-v1`) — angalia **section 7** kwa ramani ya schema.)
- Kila exchange inarekodiwa katika `DataExchange` (system=`AI`, direction=`PUSH`, operation=`calculate_reputation`)

---

## 1. JSON ambayo AI ANAPOKEA (Request)

Muundo kamili unaotumwa kwenda `AI_ENGINE_URL` ni `POST` yenye JSON object moja:

```json
{
  "assessment_reference": "ASSESS-TZ-2025-0001",
  "features": {
    "active_loan_count": 2,
    "completed_loan_count": 3,
    "defaulted_loan_count": 0,
    "total_outstanding_debt": 320000.0,
    "on_time_payment_ratio": 0.94,
    "missed_payment_count": 1,
    "late_payment_count": 2,
    "max_days_overdue": 12,
    "transaction_frequency": 240,
    "income_frequency": 24,
    "balance_stability": 0.82
  }
}
```

### Ufafanuzi wa fields

| Field | Aina | Required | Maana |
|---|---|---:|---|
| `assessment_reference` | string | Ndiyo | Kitambulisho cha assessment inayofanyiwa scoring. |
| `features` | object | Ndiyo | Orodha ya vipimo (features) vilivyoandaliwa kutoka `CreditProfile`. |

### Fields ndani ya `features`

Thamani hizi zinatoka kwenye `CreditFeature` za borrower (zinazotengenezwa na `FeatureGenerationService`):

| Field | Aina | Maana |
|---|---|---|
| `active_loan_count` | int | Idadi ya mikopo iliyo bado hai (ACTIVE/CURRENT/OPEN). |
| `completed_loan_count` | int | Idadi ya mikopo iliyolipwa kikamilifu. |
| `defaulted_loan_count` | int | Idadi ya mikopo iliyoanguka (DEFAULTED). |
| `total_outstanding_debt` | float | Jumla ya deni lisilolipwa (outstanding balances). |
| `on_time_payment_ratio` | float 0–1 | Uwiano wa malipo yaliyofanyika kwa wakati (`ON_TIME / total`). |
| `missed_payment_count` | int | Idadi ya malipo yaliyokosekana kabisa (`MISSED`). |
| `late_payment_count` | int | Idadi ya malipo yaliyochelewa (`LATE`). |
| `max_days_overdue` | int | Siku nyingi zaidi za kuchelewa kwenye repayment yoyote. |
| `transaction_frequency` | int | Idadi ya transactions katika kipindi cha ripoti. |
| `income_frequency` | int | Idadi ya transactions za aina `INCOME`. |
| `balance_stability` | float | Uthabiti wa saldo (0–1 au 0–100). |

### Kanuni ya routing policy (uchujaji wa fields)

Kabla ya kutumwa, `features` inachujuwa na **DataRoutingPolicy iliyo active** (`ai_fields`). Kwa policy ya default (`DEFAULT-CREDIT-ROUTING`, v1.0.0) fields zote 11 zina faila, hivyo mfano hapo juu ni kamili. Ikiwa policy ina `ai_fields` ndogo zaidi, AI atapokea subset tu ya fields hizo — `assessment_reference` haichujwi.

Kumbuka: `score_inputs` ya assessment huhifadhi features kamili zilizotumwa, hivyo kila scoring inafuatilika (auditable).


## 2. JSON ambayo AI ANARUDISHA (Response)

Baada ya kazi kuisha, AI lazima arudishe **JSON object** (HTTP 200) yenye fields hizi:

```json
{
  "reputation": "EXCELLENT",
  "score": 0.9450,
  "risk_level": "LOW",
  "behavior_summary": "Borrower shows consistent on-time repayments across 5 loans with stable monthly income.",
  "model_version": "ai-reputation-v1.2.0"
}
```

| Field | Aina | Required | Maana |
|---|---|---:|---|
| `reputation` | string | Ndiyo | Daraja la umaarufu, mf. `EXCELLENT`, `GOOD`, `MODERATE`, `HIGH_RISK`. |
| `score` | number | Ndiyo | Alama ya umaarufu (0–1 kwenye seed data; huhifadhiwa kama Decimal 7,4). |
| `model_version` | string | Ndiyo | Toleo la model iliyotumika — lazima liwepo kwa ajili ya audit. |
| `risk_level` | string | Hapana | Kiwango cha hatari, mf. `LOW`, `MEDIUM`, `HIGH`. |
| `behavior_summary` | string | Hapana | Maelezo mafupi ya tabia ya kifedha ya borrower. |

Fields zozote nyingine zitakazorudishwa huhifadhiwa kama zilivyo kwenye `raw_result` (JSONField) — haziharibiwi.

### Masharti ya uhalali (validation)

- Response lazima iwe JSON **object** — sio array, sio string.
- Lazima iwe na fields tatu: `reputation`, `score`, `model_version`.
- Ikiwa lolote kati ya hayo linakosekana → `ExternalServiceUnavailable("AI engine returned an incomplete response.")` na caller anapata HTTP `503`.

---

## 3. JSON ambayo Central System INARUDISHA kwa caller (mf. frontend)

Baada ya kuhifadhi matokeo, endpoint ya `POST /api/assessments/{ref}/ai-reputation/` inarudisha `AIReputationResult` (serializer = fields zote za model):

```json
{
  "id": 1,
  "assessment": 5,
  "reputation": "EXCELLENT",
  "score": "0.9450",
  "risk_level": "LOW",
  "behavior_summary": "Borrower shows consistent on-time repayments across 5 loans with stable monthly income.",
  "model_version": "ai-reputation-v1.2.0",
  "raw_result": {
    "reputation": "EXCELLENT",
    "score": 0.945,
    "risk_level": "LOW",
    "behavior_summary": "Borrower shows consistent on-time repayments across 5 loans with stable monthly income.",
    "model_version": "ai-reputation-v1.2.0"
  },
  "created_at": "2026-09-16T10:30:00Z",
  "updated_at": "2026-09-16T10:30:00Z"
}
```

Angalizo: `score` inahifadhiwa kama `Decimal(max_digits=7, decimal_places=4)`, hivyo DRF inaia translate kuwa **string** (mf. `"0.9450"`) kwenye response — si number.

Kwa kuongezea, `Assessment` yenyewe inasasishwa (fields hizi zinapatikana kupitia `GET /api/assessments/`):

```json
{
  "assessment_reference": "ASSESS-TZ-2025-0001",
  "reputation": "EXCELLENT",
  "reputation_score": "0.9450",
  "risk_level": "LOW",
  "behavior_summary": "Borrower shows consistent on-time repayments...",
  "model_version": "ai-reputation-v1.2.0",
  "score_inputs": {
    "active_loan_count": 2,
    "completed_loan_count": 3,
    "defaulted_loan_count": 0,
    "total_outstanding_debt": 320000.0,
    "on_time_payment_ratio": 0.94,
    "missed_payment_count": 1,
    "late_payment_count": 2,
    "max_days_overdue": 12,
    "transaction_frequency": 240,
    "income_frequency": 24,
    "balance_stability": 0.82
  },
  "score_explanation": [
    {
      "dimension": "AI",
      "name": "AI reputation",
      "value": "0.9450",
      "reason": "Borrower shows consistent on-time repayments..."
    }
  ]
}
```

Kusoma matokeo yaliyohifadhiwa bila ku-calculate upya: `GET /api/assessments/{ref}/ai-result/` — inarudisha JSON ile ile ya section 3 (bila kufanya exchange mpya ya PUSH; operation ni `read_reputation_result`, direction `PULL`).

---

## 4. Hitilafu (Error responses)

| Hali | Response kwa caller |
|---|---|
| `AI_ENGINE_URL` imesetiwa lakini AI haipatikani / timeout | `503` na `{"detail": "External scoring service is unavailable."}` |
| Engine ya nje / blockchain bridge inajibu na HTTP error (mf. bridge `500 ON_CHAIN_EXECUTION_FAILED`) | `503` na ujumbe wa downstream, mf. `{"detail": "External service error HTTP 500: ON_CHAIN_EXECUTION_FAILED ..."}` |
| AI wa nje anarudisha JSON isiyokuwa object au inakosa `reputation`/`score`/`model_version` | `503` na `{"detail": "AI engine returned an incomplete response."}` |
| Hakuna `CreditProfile` / features kwa borrower **na** `AI_ENGINE_URL` imesetiwa | Profile ina-synthesized kiotomatiki kutoka kwenye merged lender data (`source_version: lender-push-v1`) kabla ya scoring — hakuna `503`. |
| Hakuna `CreditProfile` na hakuna `AI_ENGINE_URL` | Vivyo hivyo: trained model ina-score kutoka kwenye borrower record; `model_inputs` kamili ziko kwenye `raw_result`. |

Katika kila hali, `DataExchange` inarekodiwa kwa `status=FAILED` na `error_message`.

---

## 5. Muhtasari wa mzunguko (flow)

```
Frontend / Admin
      |
      | POST /api/assessments/{ref}/ai-reputation/
      v
DAIRE Central System
      |  (inakusanya features kutoka CreditProfile + routing policy ai_fields)
      |  POST AI_ENGINE_URL
      v
AI Engine
      |  request:  { assessment_reference, features }
      |  response: { reputation, score, risk_level?, behavior_summary?, model_version }
      v
DAIRE Central System
      |  (inahifadhi AIReputationResult + kusasisha Assessment + DataExchange log)
      v
Frontend / Admin  <--- JSON ya section 3
```

---

## 6. Ramani ya API — API zipi zinatumika kwenye kila mfumo

Sehemu hii inaorodhesha **kila API** inayotumika kwenye mfumo wa Lenders, AI, na Blockchain, ili mwelekeo wa data uwe wazi.

### 6.1 Lender Subsystem (DAIRE Central ↔ Lender Subsystems)

#### API za nje (Central System inazipigia lender moja kwa moja)

**Usafiri (transport):** mifumo yote ya DAIRE (lender, AI, blockchain) iko kwenye
**network moja ya kuaminika**, hivyo calls kati ya mifumo ni HTTP JSON **bila API
key** kwa chaguo-msingi. `REQUIRE_API_KEYS=true` (hiari) inarudisha kulazimisha
`X-API-Key` / bearer token.

| API | Mwelekeo | Matumizi |
|---|---|---|
| `GET {api_base_url}/borrowers?borrower_reference={ref}` | Central → Lender | Kuvuta data ya borrower kutoka kwenye lender. Inatumwa pamoja na header `Accept: application/json` (bila key kwa chaguo-msingi). |
| `POST {api_base_url}` | Central → Lender | Kutuma data iliyonormalizwa kwenda kwa lender (push). |

#### API za ndani za Central System zinazoendesha mtiririko wa lender

| API (Central) | Mwelekeo | Body / Query |
|---|---|---|
| `POST /api/lenders/{id}/pull-borrower-data/` | Admin → Central → Lender moja | `{ "borrower_reference": "BRW-TZ-1001" }` |
| `POST /api/borrowers/pull-from-all-lenders/` | Admin → Central → Lender zote | `{ "borrower_reference": "BRW-TZ-1001" }` — caller hachagui lender; Central inavuta kutoka kwa wote na ku-merge. |
| `POST /api/lenders/{id}/push-borrower-data/` | Central → Lender | `{ "borrower_reference": "...", "payload?": {...}, "target_url?": "..." }` — bila `payload`, Central inatuma `borrower_routing_payload`. |
| `POST /api/borrowers/ingest/` | Lender → Central | `{ "lender_id": "NMB-001", "borrower_reference": "...", "payload": {...} }` — lender anayetuma data yake mwenyewe. |
| `POST /api/borrowers/{id}/broadcast-result/` | Central → Lender zote zilizounganishwa | `{ "result_type": "CREDIT_RESULT", "payload": {...} }` — kusambaza matokeo ya AI/blockchain kwa wateja. |
| `POST /api/lenders/` na `PATCH /api/lenders/{id}/` | Admin → Central | Usajili/usasishaji wa lender (`lender_id`, `institution_name`, `api_base_url`, `api_status`, `authentication_method`). |
| `GET /api/borrowers/search/?lender_name=&account_reference=&borrower_reference=` | Frontend → Central | Kutafuta borrower kwa kigezo chochote. |

Data inayopatikana kutoka kwa lender inafuata JSON contract ya `LENDER_SUBSYSTEM_README.md` (borrower + transactions + loans + repayments + verification + source_metadata).

### 6.2 AI Engine (DAIRE Central ↔ AI)

#### API za nje

| API | Mwelekeo | Body |
|---|---|---|
| `POST {AI_ENGINE_URL}` | Central → AI | Request na response zinaelezwa kwenye **section 1 na 2** hapo juu. |

#### API za ndani za Central System

| API | Matumizi |
|---|---|
| `POST /api/assessments/{ref}/ai-reputation/` | Kuanzisha scoring — inakusanya features, inatuma kwa AI, inahifadhi matokeo. |
| `GET /api/assessments/{ref}/ai-result/` | Kusoma matokeo yaliyohifadhiwa bila ku-calculate upya. |
| `GET /api/ai-reputation/` | Orodha ya matokeo yote ya AI (au `/api/ai-reputation-results/` — jina la zamani). |

### 6.3 Blockchain / Smart Contract (DAIRE Central ↔ Blockchain)

#### API za nje

| API | Mwelekeo | Body |
|---|---|---|
| `POST {BLOCKCHAIN_RPC_URL}` | Central → Blockchain | `{ "method": "calculateScore", "contract_address": "{SMART_CONTRACT_ADDRESS}", "assessment_reference": "...", "dimensions": { "D1": 85, "D2": 72, "D3": 90, "D4": 64, "D5": 60 }, "schema_version": "credit-dimensions-v1" }` |
| `POST {BLOCKCHAIN_RPC_URL}` | Central → Blockchain | `{ "method": "verify", "transaction_hash": "0x..." }` |

Blockchain anarudisha kwa `calculateScore`:

```json
{
  "credit_score": 78,
  "ruleset_version": "ruleset-v1.0.0",
  "transaction_hash": "0xabc123...",
  "block_number": 152300,
  "status": "PENDING"
}
```

- Contract inarudisha alama 0–100; Central inaibadilisha kuwa scale ya umma **350–800** (`350 + raw/100*450`) na kuifunga kati ya 350 na 800. Contract za dev zinazorudisha 350–800 moja kwa moja zinakubalika pia.
- Dimensions D1–D5 (zinazotokana na features ndani ya Central, **sio** data ghafi):
  - **D1** — Repayment history (on-time ratio, siku za kuchelewa, malipo yaliyokosekana)
  - **D2** — Financial activity (transaction continuity, income regularity, balance stability)
  - **D3** — Debt and loan history (defaulted/completed loans, debt-to-income)
  - **D4** — Stability trend
  - **D5** — Cross-lender corroboration (idadi ya lenders zenye data za borrower)
- Data ghafi (transactions, balances, repayments, identity) **haivuki** mpaka wa blockchain — inabaki kwenye Central System.

#### API za ndani za Central System

| API | Matumizi |
|---|---|
| `POST /api/assessments/{ref}/blockchain-score/` | Kuanzisha scoring — inatengeneza dimensions D1–D5, inatumia kwa contract, inahifadhi matokeo. |
| `GET /api/assessments/{ref}/verify/` | Kuthibitisha transaction iliyorekodiwa (inataka `blockchain_transaction_hash`; bila yake inarudisha `409`). |
| `GET /api/smart-contract/` | Orodha ya matokeo ya smart contract (au `/api/smart-contract-results/`). |
| `GET /api/blockchain/` | Orodha ya transactions za blockchain (au `/api/blockchain-transactions/`). |

### 6.4 Routing Policy — inayodhibiti fields zinazotumwa kila upande

| API | Matumizi |
|---|---|
| `GET /api/routing-policies/` | Kuona policies zote na fields zinazoruhusiwa. |
| `PUT /api/routing-policies/{id}/` | Kusasisha policy — `{ "lender_fields": [...], "ai_fields": [...], "blockchain_fields": [...], "active": true, "version": "1.0.0" }`. |

Policy inayofanya kazi (`active=true`) inachuja payload kabla ya kutumwa: `ai_fields` kwa AI (section 1), `blockchain_fields` kwa dimensions, `lender_fields` kwa data inayovutwa kutoka kwa lenders. Bila policy active, fields zote zinatumwa.

### 6.5 Mzunguko kamili wa data (mfano wa mwisho-mwisho)

```
 1. Admin anasajili lender        POST /api/lenders/
 2. Lender anatuma data yake      POST /api/borrowers/ingest/
    AU Central inavuta yenyewe     POST /api/borrowers/pull-from-all-lenders/
                                        |  GET {lender}/borrowers?borrower_reference=...
                                        v
 3. Central inanormalizwa + merge  (Borrower, Accounts, Loans, Repayments, FinancialProfile)
 4. Frontend inaomba assessment    POST /api/assessments/  (kupitia admin) au assessment iliyopo
 5. AI scoring                     POST /api/assessments/{ref}/ai-reputation/
                                        |  POST AI_ENGINE_URL  { assessment_reference, features }
                                        v
                                   { reputation, score, risk_level, behavior_summary, model_version }
 6. Blockchain scoring             POST /api/assessments/{ref}/blockchain-score/
                                        |  POST BLOCKCHAIN_RPC_URL  { method: calculateScore, dimensions D1-D5 }
                                        v
                                   { credit_score, ruleset_version, transaction_hash }
 7. Uthibitisho                    GET /api/assessments/{ref}/verify/
                                        |  POST BLOCKCHAIN_RPC_URL  { method: verify, transaction_hash }
 8. Kusambaza matokeo              POST /api/borrowers/{id}/broadcast-result/  → lender zote
```

### 6.6 Environment variables zinazotawala API za nje

| Env var | Inatumika na |
|---|---|
| `REQUIRE_API_KEYS` | Mifumo yote. `false` (chaguo-msingi): calls kati ya mifumo ni keyless — network moja ya kuaminika. `true`: `X-API-Key`/bearer inatakiwa kwenye kila call ya mifumo. |
| `AI_ENGINE_URL` | Endpoint ya AI engine ya nje (section 6.2). **Bila yake, Central inatumia trained model ya ndani (section 7), sio `503`.** |
| `BLOCKCHAIN_RPC_URL` | Endpoint ya RPC ya blockchain (section 6.3) — bila yake, `verify` inarudi kwenye transaction ya ndani. |
| `SMART_CONTRACT_ADDRESS` | Anwani ya contract inayotumwa kwenye `calculateScore`. |
| `BLOCKCHAIN_NETWORK` | Jina la network linalohifadhiwa kwenye `BlockchainTransaction`. |

---

## 7. Trained model ya ndani (bila `AI_ENGINE_URL`)

`AIReputationService` inapakia `backend/new_credit_risk_model.joblib` **mara moja**
(`services.get_credit_risk_model`, cached) — RandomForest (trees 100, classes 0/1,
`predict_proba` inapatikana). Kila `POST .../ai-reputation/` inajenga safu moja ya
columns 11 za model kutoka kwenye borrower record (`services.build_credit_risk_row`):

| Model column | Central source |
|---|---|
| `person_age` | `Borrower.age` |
| `person_income` | `Borrower.income` |
| `person_home_ownership` | haikusanywi → `None` (pipeline inajaza `'missing'`) |
| `person_emp_length` | haikusanywi → `None` (pipeline inajaza median ya training = 4.0) |
| `loan_intent` | haikusanywi → `None` (pipeline inajaza `'missing'`) |
| `loan_grade` | haikusanywi → `None` (pipeline inajaza `'missing'`) |
| `loan_amnt` | mkopo mkubwa zaidi ulio ACTIVE (au mkubwa zaidi kuwahi kuwepo) |
| `loan_int_rate` | riba ya mkopo huo huo |
| `loan_percent_income` | `loan_amnt / person_income` |
| `cb_person_default_on_file` | `'Y'` ikiwa kuna loan/repayment yenye status ya default, vinginevyo `'N'` |
| `cb_person_cred_hist_length` | miaka kati ya transaction ya kwanza na ya mwisho kwenye accounts |

Matokeo: `default_proba = P(class 1)`, `score = round(1 - default_proba, 4)`,
bands kama zamani (`≥0.85 EXCELLENT`, `≥0.70 GOOD`, `≥0.55 MODERATE`, else `HIGH_RISK`),
`model_version: credit-risk-joblib-v1`, `raw_result.engine: TRAINED_MODEL` na
`raw_result.model_inputs` (columns 11 halisi zilizotumwa — ukaguzi kamili).

Kumbuka: fields 4 zisizokusanywa (`home_ownership`, `emp_length`, `intent`, `grade`)
huvuta score kuelekea wastani. Kadri Central itakavyoanza kuzikusanya (hasa
`cb_person_cred_hist_length` kutoka kwenye transaction dates — tayari ina ramani),
ndivyo reputation itakavyozidi kutofautisha. Formula ya zamani ya local fallback
(`_local_ai_reputation`) inabaki tu iwapo faili la model halipatikani.
