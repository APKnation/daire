# DAIRE — API Endpoints & Complete JSON Data Formats

**Project:** DAIRE — Decentralized AI Reputation Engine
**Scope:** Every JSON payload that flows between the Lender Systems, the Central System (Credit Information Hub), the AI scoring model, and the Blockchain (DaireCreditScore.sol).
**Conventions:** percentages are **basis points** (`9750` = 97.50%), borrower identity is a `bytes32 borrowerRef = keccak256(identityHash + "|" + salt)`, risk scores are **300–850**, dimensions are **0–100**.

---

## 0. System map — who calls what

```
[LENDER SYSTEM] ──POST /api/lender-data/receive/──▶ [CENTRAL SYSTEM (Hub)]
                                                        │
                            ┌───────────────────────────┼───────────────────────────────┐
                            ▼                           ▼                               ▼
                  [AI SCORING MODEL]          [DAIRE MIDDLEWARE]                [POSTGRESQL]
                  PD / score / LGD / EAD      Express REST API                  raw data, mapping
                            │                           │
                            │            POST /api/v1/score/submit          POST /api/v1/score/submit-calculated
                            │                           │                               │
                            └──────────▶ [SMART CONTRACT DaireCreditScore.sol] ◀──────────┘
                                                        │
                                       events: ScoreCalculated / ScoreRecorded /
                                               DimensionsRecorded / InsufficientEvidence
                                                        │
                                                        ▼
                                     [CENTRAL BROADCAST to lender / consumers]
```

Base URLs:

| Service | Base URL (dev) | Code |
|---|---|---|
| Central System (Django Hub) | `http://127.0.0.1:8000` | receives lender data, feature builder — **PostgreSQL `daire` @ `127.0.0.1:5433`** |
| DAIRE Middleware (this repo) | `http://localhost:5000` | `daire-middleware/index.js` |
| AI model service (portable scorecard) | `python score_pd.py` / wheel service | `nmb_credit_models.../portable/score_pd.py` |
| Sepolia chain | chainId `11155111` | `contracts/DaireCreditScore.sol` |

> **Lender network (2026-09-30): NMB + CRDB ONLY.** Registered lenders are `LDR-NMB-02` (NMB Bank Microfinance) and `LDR-CRDB-01` (CRDB Bank Plc). Pushes from any other `lender_id` are rejected (`404 Lender '<id>' is not registered`), and mock endpoints `/api/mock-lender/<OTHER>/…` return 404 as well. Retired lenders are removed with `python manage.py prune_lenders --yes`.

---

## 1. LENDER → CENTRAL SYSTEM (sending data in)

**Endpoint:** `POST {CENTRAL_URL}/api/lender-data/receive/`
**Auth:** keyless by default (`REQUIRE_API_KEYS=false`); when enabled send `Authorization: Bearer <lender_api_key>`
**Content-Type:** `application/json`
**Source:** `daire-middleware/send-lender-data.sh`

### 1.1 Request body (wrapped format — preferred)

```json
{
  "lender_id": "LDR-DEMO-FLOW",
  "borrower_reference": "1001",
  "account_reference": "8834010",
  "nida_number": "19551015157027220748",
  "payload": {
    "id": 1001,
    "borrower_reference": "1001",
    "customer_id": "001",
    "name": "Nia",
    "age": 29,
    "gender": "FEMALE",
    "income": 980000,
    "transaction_frequency": 30,
    "income_frequency": 2,
    "savings": 250000,
    "balance_stability": 0.72,
    "account_reference": "ACC-001",
    "account_name": "Nia account"
  }
}
```

### 1.2 Column definition

| Column | Type | Required | Description |
|---|---|---|---|
| `lender_id` | string | ✅ | Exact lender id registered in Central (e.g. `LDR-DEMO-FLOW`) |
| `borrower_reference` | string | ✅ | Central's unique borrower id (or lender's local id to link) |
| `account_reference` | string | ✅ | Account number; falls back to `borrower_reference` if absent |
| `nida_number` | string | ⬜ | Optional national id — global unique customer key |
| `payload` | object | ✅ | Full lender contract payload (fields below) |
| `payload.id` | integer | ⬜ | Lender's internal row id |
| `payload.name` | string | ⬜ | Borrower name — **never leaves PostgreSQL** |
| `payload.age` | integer | ⬜ | Years |
| `payload.gender` | enum | ⬜ | `FEMALE` \| `MALE` \| `OTHER` |
| `payload.income` | integer | ⬜ | Monthly income in TZS |
| `payload.transaction_frequency` | integer | ⬜ | Transactions per month |
| `payload.income_frequency` | integer | ⬜ | Paydays per month |
| `payload.savings` | integer | ⬜ | Savings balance in TZS |
| `payload.balance_stability` | float 0–1 | ⬜ | 0.72 = balance varies ±72% band; converted to bps upstream |
| `payload.account_reference` | string | ⬜ | Lender account number |
| `payload.account_name` | string | ⬜ | Account label |

A **flat contract** (lender fields at top level + `lender_id`) is also accepted.

### 1.3 Response — Central acknowledges

```json
{
  "received": true,
  "lender_id": "LDR-DEMO-FLOW",
  "borrower_reference": "1001",
  "evidence_sha256": "9f2c1a…e7",
  "status": "STORED"
}
```

---

## 2. DATA TO AI — Central → AI scoring model

The Central System converts raw records into model features, scores them with the frozen scorecard (`pd_scorecard.json`), and keeps the result off-chain.

### 2.1 Request — application record (JSON sent to the model)

Same fields as `score_pd.py` / `example_python.py`. Fields the applicant cannot supply are sent as `null` — the model treats "not recorded" as its own evidenced category.

```json
{
  "model_request_id": "req_2026_09_30_000001",
  "borrower_reference": "1001",
  "model": "application_only",
  "application": {
    "funded_amnt": 12000.0,
    "term_months": 36,
    "int_rate": 13.65,
    "installment": 408.09,
    "purpose": "debt_consolidation",
    "grade": "B",
    "initial_list_status": "f",
    "annual_inc": 62000.0,
    "dti": 16.05,
    "home_ownership": "MORTGAGE",
    "emp_length_years": 6.0,
    "verification_status": "Verified",
    "addr_state": "CA",
    "credit_history_months": 168.0,
    "inq_last_6mths": 1.0,
    "delinq_2yrs": 0.0,
    "total_rev_hi_lim": 22100.0,
    "open_acc": 11.0,
    "total_acc": 24.0,
    "pub_rec": 0.0,
    "acc_now_delinq": 0.0,
    "mths_since_last_delinq": null,
    "mths_since_last_record": null
  }
}
```

### 2.2 Column definition — AI input

| Column | Type | Notes |
|---|---|---|
| `funded_amnt` | float | Loan principal |
| `term_months` | int | `36` \| `60` |
| `int_rate` | float | Percent (used by **primary** model only) |
| `installment` | float | Monthly payment |
| `purpose` | categorical | e.g. `debt_consolidation`, `home_improvement` |
| `grade` | categorical A–G | Lender's own grade — loss estimates & challenger exclusion |
| `initial_list_status` | enum | `w` \| `f` |
| `annual_inc` | float | Annual income |
| `dti` | float | Monthly debt payments as % of monthly income |
| `home_ownership` | categorical | `MORTGAGE` \| `RENT` \| `OWN` \| `ANY` … |
| `emp_length_years` | float | 0–10 |
| `verification_status` | categorical | `Verified` \| `Source Verified` \| `Not Verified` |
| `addr_state` | string | 2-letter state code |
| `credit_history_months` | float | Age of credit file |
| `inq_last_6mths` | int | Hard inquiries last 6 months |
| `delinq_2yrs` | int | Delinquencies last 2 years |
| `mths_since_last_delinq` | int\|null | `null` = never / not recorded |
| `mths_since_last_record` | int\|null | `null` = never / not recorded |
| `open_acc`, `total_acc` | int | Open / total credit lines |
| `pub_rec`, `acc_now_delinq` | int | Derogatory records |
| `total_rev_hi_lim` | float | Total revolving high credit |

### 2.3 Response — AI model output (Central receives this)

Returned by `Scorecard.score()`:

```json
{
  "model_request_id": "req_2026_09_30_000001",
  "borrower_reference": "1001",
  "model": "application_only",
  "probability_of_default": 0.1843,
  "in_100": 18,
  "log_odds": -1.4925,
  "credit_score": 641.2,
  "contributions": {
    "dti":                { "value": 16.05, "woe":  0.412, "log_odds_contribution": -0.271 },
    "purpose":            { "value": "debt_consolidation", "woe": -0.088, "log_odds_contribution":  0.058 },
    "verification_status":{ "value": "Verified", "woe":  0.301, "log_odds_contribution": -0.198 }
  }
}
```

| Column | Type | Meaning |
|---|---|---|
| `probability_of_default` | float 0–1 | PD = 1/(1+e^−log_odds). Higher = riskier |
| `in_100` | int | Rounded "in 100 borrowers like this" |
| `log_odds` | float | Intercept + Σ(coefficient × WoE) |
| `credit_score` | float 300–850 | `offset − factor × log_odds`, clamped. Higher = lower risk |
| `contributions` | object | Per-feature WoE and log-odds contribution — reason codes / adverse-action explanation |

Optional loss module (wheel route) additionally returns: `bounded_lgd`, `bounded_ead_ratio`, `bounded_ead_amount`, `formula_expected_loss`, `denominator_consistent_expected_loss`.

---

## 3. MIDDLEWARE ENDPOINTS — Central → DAIRE Middleware → Blockchain

**Base URL:** `http://localhost:5000` (middleware, `daire-middleware/index.js`)

### 3.1 `POST /api/v1/score/submit` — on-chain calculation (Njia ya 1)

Central sends derived features → contract computes D1–D5 + score inside the EVM.

**Request**

```json
{
  "identityHash": "NIDA-19950812-12345-00001",
  "salt": "DAIRE_TANZA_SALT_2026",
  "features": {
    "historyMonths": 24,
    "behaviourEventCount": 30,
    "repaymentRecordCount": 15,
    "verifiedSourceCount": 2,
    "onTimeRatioBps": 9800,
    "maxDaysLate": 0,
    "missedCount": 0,
    "onTimeStreak": 15,
    "activeMonthsBps": 10000,
    "regularMonthsBps": 9000,
    "balanceStabilityBps": 8500,
    "defaultCount": 0,
    "completedCount": 2,
    "utilizationBps": 4000,
    "activeLenderCount": 1,
    "trendBps": 500,
    "volatilityBps": 1000,
    "monthsSinceAdverse": 65535,
    "distinctSourceCount": 2,
    "meanCorroborationX100": 250,
    "openConflictCount": 0
  }
}
```

**Feature column definition** (order matters for the Solidity tuple)

| # | Column | Solidity type | Range / unit | Dimension |
|---|---|---|---|---|
| 1 | `historyMonths` | uint16 | ≥ 6 (gate) | D5 |
| 2 | `behaviourEventCount` | uint16 | ≥ 8 (gate) | gates |
| 3 | `repaymentRecordCount` | uint16 | ≥ 1 (gate) | gates |
| 4 | `verifiedSourceCount` | uint8 | ≥ 1 (gate), ≤ `distinctSourceCount` | D5 |
| 5 | `onTimeRatioBps` | uint16 | 0–10000 | D1 |
| 6 | `maxDaysLate` | uint16 | days | D1 |
| 7 | `missedCount` | uint16 | count | D1 |
| 8 | `onTimeStreak` | uint16 | months; ≥ 12 gives +5 | D1 |
| 9 | `activeMonthsBps` | uint16 | 0–10000 | D2 |
| 10 | `regularMonthsBps` | uint16 | 0–10000 | D2 |
| 11 | `balanceStabilityBps` | uint16 | 0–10000 | D2 |
| 12 | `defaultCount` | uint16 | count (36-month window) | D3 |
| 13 | `completedCount` | uint16 | count | D3 |
| 14 | `utilizationBps` | uint16 | 0–10000 (3000–7000 = good) | D3 |
| 15 | `activeLenderCount` | uint8 | count | D3 |
| 16 | `trendBps` | int16 | −10000…+10000, positive = improving | D4 |
| 17 | `volatilityBps` | uint16 | 0–10000, higher = worse | D4 |
| 18 | `monthsSinceAdverse` | uint16 | months; `65535` = NEVER | D4 |
| 19 | `distinctSourceCount` | uint8 | independent sources | D5 |
| 20 | `meanCorroborationX100` | uint16 | 250 = 2.50, peak 300 | D5 |
| 21 | `openConflictCount` | uint8 | unresolved conflicts | D5 |

**Response 200** (from `seed_data.txt`)

```json
{
  "success": true,
  "status": "SCORED_SUCCESSFULLY",
  "calculation": "ON_CHAIN",
  "transactionHash": "0x535c5f1094c0635449b7a516920755538b6b0aa1c2abee322b209024c17b8a7f",
  "blockNumber": 8,
  "data": {
    "borrowerRef": "0x3bcdaf773c0ccf4e276e6cf4e00604dca63beef1d7819bacca63575fe97ad275",
    "score": 780,
    "riskBand": "VERY_GOOD",
    "version": 7,
    "assessedAt": 1789479752,
    "dimensions": {
      "d1_paymentReliability": 100,
      "d2_financialStability": 92,
      "d3_debtManagement": 100,
      "d4_behaviouralConsistency": 59,
      "d5_trustEvidence": 81
    }
  }
}
```

**Response 422 — insufficient evidence (BR-10 gates failed)**

```json
{
  "success": false,
  "status": "INSUFFICIENT_EVIDENCE",
  "borrowerRef": "0x3bcd…d275",
  "missingMask": 1,
  "message": "INSUFFICIENT_EVIDENCE: historia<6mwezi"
}
```

`missingMask` bits: `1` history < 6 months · `2` events < 8 · `4` repayments < 1 · `8` verified sources < 1.

### 3.2 `POST /api/v1/score/submit-calculated` — off-chain calculation (Njia ya 2)

Central computes dimensions itself (via `scoreEngine.js` or the AI model) and the contract only stores. Accepts **either** `features` or pre-computed `dimensions`.

**Request A — with raw features (engine derives d1–d5)**

```json
{
  "identityHash": "NIDA-19950812-12345-00001",
  "salt": "DAIRE_TANZA_SALT_2026",
  "features": {
    "historyMonths": 24,
    "behaviourEventCount": 30,
    "repaymentRecordCount": 15,
    "verifiedSourceCount": 2,
    "onTimeRatioBps": 9800,
    "maxDaysLate": 0,
    "missedCount": 0,
    "onTimeStreak": 15,
    "activeMonthsBps": 10000,
    "regularMonthsBps": 9000,
    "balanceStabilityBps": 8500,
    "defaultCount": 0,
    "completedCount": 2,
    "utilizationBps": 4000,
    "activeLenderCount": 1,
    "trendBps": 500,
    "volatilityBps": 1000,
    "monthsSinceAdverse": 65535,
    "distinctSourceCount": 2,
    "meanCorroborationX100": 250,
    "openConflictCount": 0
  }
}
```

**Request B — with dimensions only (web app already has d1–d5)**

```json
{
  "identityHash": "NIDA-19950812-12345-00001",
  "salt": "DAIRE_TANZA_SALT_2026",
  "dimensions": {
    "d1": 85,
    "d2": 83,
    "d3": 95,
    "d4": 65,
    "d5": 65
  }
}
```

**Response 200** (from `seed_data.txt`)

```json
{
  "success": true,
  "status": "SCORE_RECORDED",
  "calculation": "OFF_CHAIN",
  "transactionHash": "0x9c669a19ffe5bf867f442135a43971431bb08e8584f685dcff4e9554cfb3167c",
  "blockNumber": 7,
  "data": {
    "borrowerRef": "0x3bcdaf773c0ccf4e276e6cf4e00604dca63beef1d7819bacca63575fe97ad275",
    "finalScore": 735,
    "riskBand": null,
    "dimensions": {
      "d1_paymentReliability": 85,
      "d2_financialStability": 83,
      "d3_debtManagement": 95,
      "d4_behaviouralConsistency": 65,
      "d5_trustEvidence": 65
    },
    "version": 6
  }
}
```

> `riskBand` is `null` unless the contract owner enabled `useSubmittedBand`.

### 3.3 `GET /api/v1/score/:borrowerRef` — read (free, no gas)

```
GET http://localhost:5000/api/v1/score/0x3bcdaf773c0ccf4e276e6cf4e00604dca63beef1d7819bacca63575fe97ad275
```

**Response 200**

```json
{
  "success": true,
  "data": {
    "borrowerRef": "0x3bcdaf773c0ccf4e276e6cf4e00604dca63beef1d7819bacca63575fe97ad275",
    "score": 780,
    "riskBand": "VERY_GOOD",
    "version": 7,
    "assessedAt": 1789479752,
    "dimensions": { "d1": 100, "d2": 92, "d3": 100, "d4": 59, "d5": 81 }
  }
}
```

**Response 404** — `{ "success": false, "message": "No credit assessment found for this reference" }`

---

## 4. DATA TO BLOCKCHAIN — exact on-chain payload

### 4.1 `submitFeatures(borrowerRef, Features f)` — the Solidity tuple

Called by the middleware (Hub wallet) with `borrowerRef = keccak256(identityHash + "|" + salt)`. The features tuple, in strict ABI order:

```solidity
tuple(uint16 historyMonths,
      uint16 behaviourEventCount,
      uint16 repaymentRecordCount,
      uint8  verifiedSourceCount,
      uint16 onTimeRatioBps,
      uint16 maxDaysLate,
      uint16 missedCount,
      uint16 onTimeStreak,
      uint16 activeMonthsBps,
      uint16 regularMonthsBps,
      uint16 balanceStabilityBps,
      uint16 defaultCount,
      uint16 completedCount,
      uint16 utilizationBps,
      uint8  activeLenderCount,
      int16  trendBps,
      uint16 volatilityBps,
      uint16 monthsSinceAdverse,
      uint8  distinctSourceCount,
      uint16 meanCorroborationX100,
      uint8  openConflictCount)
```

Validation enforced by `_validate()`: all `*Bps` ≤ 10000; `trendBps` within ±10000; `verifiedSourceCount ≤ distinctSourceCount`. Violations revert.

### 4.2 `submitCalculatedScore(borrowerRef, finalScore, d1..d5)`

```solidity
submitCalculatedScore(bytes32 borrowerRef, uint16 finalScore, uint8 d1, uint8 d2, uint8 d3, uint8 d4, uint8 d5)
```

Requires `300 ≤ finalScore ≤ 850`, each dimension ≤ 100. Reverts with `"DAIRE: score nje ya 300-850"` otherwise.

### 4.3 What the contract stores (Assessment struct)

```json
{
  "score": 780,
  "d1": 100, "d2": 92, "d3": 100, "d4": 59, "d5": 81,
  "band": 4,
  "assessedAt": 1789479752,
  "version": 7,
  "submittedBy": "0xaa5dbA90D8D0279B4a350193AF53d358D26bfFef"
}
```

Stored in `_current[borrowerRef]` and appended to `_history[borrowerRef][]` — never overwritten, never deleted.

### 4.4 Contract events (broadcast source)

| Event | Emitted when | Indexed | Fields |
|---|---|---|---|
| `ScoreCalculated` | `submitFeatures` success | `borrowerRef`, `hub` | `score, band, version, assessedAt` |
| `ScoreRecorded` | `submitCalculatedScore` success | `borrowerRef`, `hub` | `finalScore, band, version, recordedAt` |
| `DimensionsRecorded` | every write | — | `borrowerRef, version, d1..d5` |
| `InsufficientEvidence` | gates failed | `borrowerRef`, `hub` | `missingMask` |
| `HubAuthorized` | owner adds/removes hub | `hub` | `allowed` |

Risk band enum: `0 NONE, 1 POOR, 2 FAIR, 3 GOOD, 4 VERY_GOOD, 5 EXCEPTIONAL` (FICO cut-offs: <580, <670, <740, <800, else; dimension < 40 caps band at FAIR).

---

## 5. CENTRAL BROADCAST — result format the Central System receives/sends out

Two channels:

### 5.1 Channel A — event push (middleware listener → registered webhooks)

The middleware listens to contract events (HTTP polling — works on local node and Sepolia) and **pushes** a normalized JSON to every webhook registered via `POST /api/v1/webhooks` (see §8). **This is the standard broadcast envelope all consumers receive:**

```json
{
  "broadcast_id": "bcst_0189f3c2-7a51-7d2e-9c44-da2c5f11e9a3",
  "event": "SCORE_CALCULATED",
  "channel": "blockchain_event",
  "chain": {
    "chainId": 11155111,
    "contractAddress": "0x6f57098c3b5d0120cc4f1337974e7c14be9c44b0",
    "transactionHash": "0x535c5f1094c0635449b7a516920755538b6b0aa1c2abee322b209024c17b8a7f",
    "blockNumber": 8
  },
  "payload": {
    "borrowerRef": "0x3bcdaf773c0ccf4e276e6cf4e00604dca63beef1d7819bacca63575fe97ad275",
    "hub": "0xaa5dbA90D8D0279B4a350193AF53d358D26bfFef",
    "calculation": "ON_CHAIN",
    "score": 780,
    "finalScore": 780,
    "riskBand": "VERY_GOOD",
    "version": 7,
    "assessedAt": 1789479752,
    "dimensions": {
      "d1_paymentReliability": 100,
      "d2_financialStability": 92,
      "d3_debtManagement": 100,
      "d4_behaviouralConsistency": 59,
      "d5_trustEvidence": 81
    }
  },
  "broadcastAt": "2026-09-30T09:41:52Z"
}
```

**Broadcast column definition**

| Column | Type | Description |
|---|---|---|
| `broadcast_id` | UUIDv7 | Unique id of this broadcast, safe for idempotent consumers |
| `event` | enum | `SCORE_CALCULATED` \| `SCORE_RECORDED` \| `INSUFFICIENT_EVIDENCE` \| `HUB_AUTHORIZED` |
| `channel` | enum | `blockchain_event` \| `api_response` |
| `chain.chainId` | int | `11155111` Sepolia / `31337` Hardhat |
| `chain.contractAddress` | address | DaireCreditScore deployment |
| `chain.transactionHash` | hash | Write tx (null on reads) |
| `chain.blockNumber` | int | Confirmation block |
| `payload.borrowerRef` | bytes32 hex | keccak256 identity ref — only on-chain identity |
| `payload.hub` | address | Authorized hub that submitted |
| `payload.calculation` | enum | `ON_CHAIN` \| `OFF_CHAIN` |
| `payload.score` / `finalScore` | int 300–850 | Same value; both names kept for compatibility |
| `payload.riskBand` | enum | `POOR`/`FAIR`/`GOOD`/`VERY_GOOD`/`EXCEPTIONAL`/`NONE` |
| `payload.version` | int | Assessment version per borrowerRef (history counter) |
| `payload.assessedAt` | unix int | Block timestamp (seconds) |
| `payload.dimensions.*` | int 0–100 | `d1_paymentReliability`, `d2_financialStability`, `d3_debtManagement`, `d4_behaviouralConsistency`, `d5_trustEvidence` |
| `broadcastAt` | ISO-8601 UTC | When Central forwarded the event |

**Insufficient-evidence broadcast**

```json
{
  "broadcast_id": "bcst_0189f3c2-7a51-7d2e-9c44-da2c5f11e9a4",
  "event": "INSUFFICIENT_EVIDENCE",
  "channel": "blockchain_event",
  "chain": {
    "chainId": 11155111,
    "contractAddress": "0x6f57098c3b5d0120cc4f1337974e7c14be9c44b0",
    "transactionHash": null,
    "blockNumber": null
  },
  "payload": {
    "borrowerRef": "0x3bcdaf773c0ccf4e276e6cf4e00604dca63beef1d7819bacca63575fe97ad275",
    "hub": "0xaa5dbA90D8D0279B4a350193AF53d358D26bfFef",
    "missingMask": 3,
    "missingExplanation": "INSUFFICIENT_EVIDENCE: historia<6mwezi, matukio<8"
  },
  "broadcastAt": "2026-09-30T09:43:10Z"
}
```

### 5.1.1 Unified borrower payload — `loan_applications` field

Central merges lenders on **`nida_number`**: pushes from NMB and CRDB carrying the same NIDA resolve to ONE central borrower even when their `borrower_reference` values differ (`NMB-CUST-1` + `CRDB-CUST-77` = one person). Loans, repayments, accounts and applications from both lenders attach to that single record, and ONE assessment scores the merged profile.

The unified borrower object returned by `GET /api/borrowers/search/` (and used by the frontend borrower detail view) includes every loan the borrower is APPLYING for across all merged lenders:

```json
{
  "borrower_reference": "NMB-C1",
  "nida_number": "199508121234500009",
  "source_lenders": ["NMB Bank", "CRDB Bank"],
  "financial_profile": { "...": "merged aggregates" },
  "accounts": [ "..." ],
  "loans": [ "..." ],
  "loan_applications": [
    {
      "id": 1,
      "application_reference": "APP-NMB-1",
      "lender": 1,
      "lender_name": "NMB Bank",
      "applied_amount": "500000.0000",
      "currency": "TZS",
      "purpose": "WORKING_CAPITAL",
      "term_months": 12,
      "interest_rate": "12.5000",
      "status": "APPROVED",
      "assessment_reference": "ASM-2026-0001",
      "created_at": "2026-09-30T11:32:05.171549Z"
    },
    {
      "id": 2,
      "application_reference": "APP-CRDB-1",
      "lender_name": "CRDB Bank",
      "applied_amount": "300000.0000",
      "status": "SUBMITTED",
      "assessment_reference": null,
      "...": "..."
    }
  ]
}
```

**`loan_applications[]` columns**

| Column | Type | Description |
|---|---|---|
| `id` | int | Row id — use for the decision endpoint |
| `application_reference` | string | Lender's stable application id |
| `lender` / `lender_name` | int / string | Reporting lender (`null` when Central-recorded) |
| `applied_amount` | decimal string | The REAL amount the borrower applied for (exposure scored) |
| `currency` | string | Default `TZS` |
| `purpose` / `term_months` / `interest_rate` | | Application terms |
| `status` | enum | `SUBMITTED` → `ASSESSED` → `APPROVED` / `DECLINED` |
| `assessment_reference` | string\|null | Assessment that scored/decided this application |
| `created_at` | ISO-8601 | When the push arrived |

Decisions are recorded with `POST /api/loan-applications/{id}/decision/` (`{"decision": "APPROVED" | "DECLINED" | "ASSESSED", "assessment_reference?": "ASM-...", "reason?": "..."}`) — the assessment must belong to the same borrower, otherwise the latest borrower assessment is linked automatically.

### 5.1.2 Loan application decision — `POST /api/loan-applications/{id}/decision/`

Records the underwriting verdict on an application and links the deciding assessment:

```json
{
  "decision": "APPROVED",
  "assessment_reference": "ASM-2026-0001",
  "reason": "clean history"
}
```

| Field | Required | Notes |
|---|---|---|
| `decision` | ✅ | `APPROVED` \| `DECLINED` \| `ASSESSED` |
| `assessment_reference` | ⬜ | Must belong to the same borrower — otherwise **400**. Omitted → the borrower's latest assessment is linked automatically |
| `reason` | ⬜ | Audit note, stored in the Django admin log |

**Response 200** — `{ "status": "DECISION_RECORDED", "application": { …LoanApplicationSerializer… } }` with `status` and `assessment_reference` updated. The unified borrower payload (§5.1.1) then shows the new status, and the frontend borrower detail view renders it with the linked assessment.

### 5.2 Channel B — full result returned to the requesting lender (API response enrichment)

When the lender asked for a score through the Central System, Central joins the on-chain result with the AI result and returns one enriched object:

```json
{
  "borrower_reference": "1001",
  "borrowerRef": "0x3bcdaf773c0ccf4e276e6cf4e00604dca63beef1d7819bacca63575fe97ad275",
  "calculation": "ON_CHAIN",
  "ai": {
    "model": "application_only",
    "probability_of_default": 0.1843,
    "credit_score": 641.2
  },
  "blockchain": {
    "score": 780,
    "riskBand": "VERY_GOOD",
    "version": 7,
    "assessedAt": 1789479752,
    "dimensions": {
      "d1_paymentReliability": 100,
      "d2_financialStability": 92,
      "d3_debtManagement": 100,
      "d4_behaviouralConsistency": 59,
      "d5_trustEvidence": 81
    },
    "transactionHash": "0x535c5f1094c0635449b7a516920755538b6b0aa1c2abee322b209024c17b8a7f",
    "blockNumber": 8
  },
  "decision_hint": "APPROVE — band VERY_GOOD, PD 18.4%"
}
```

---

## 6. Error format (all middleware endpoints)

```json
{ "success": false, "error": "DAIRE: Hub haijaruhusiwa" }
```

| HTTP | Meaning |
|---|---|
| `400` | Missing `identityHash` / `salt` / `features` / `dimensions` |
| `404` | No assessment for `borrowerRef` |
| `422` | Sufficiency gates failed (`INSUFFICIENT_EVIDENCE` + `missingMask`) |
| `500` | EVM revert / RPC error — `error` carries the Solidity revert reason |

---

## 7. Quick reference — endpoint summary

| # | Method | Endpoint | Direction | Purpose |
|---|---|---|---|---|
| 1 | POST | `/api/lender-data/receive/` | Lender → Central | Push raw borrower data (+ optional `payload.loan_application`) |
| 2 | POST | AI model call (`score_pd.Scorecard.score`) | Central → AI | PD + 300–850 score + reason codes |
| 3 | POST | `/api/assessments/` | Central internal | Open assessment on MERGED data (`borrower_reference` or `nida_number`, optional `applied_loan_amount`) |
| 4 | POST | `/api/v1/score/submit` | Central → Middleware → Chain | On-chain scoring (contract computes) |
| 5 | POST | `/api/v1/score/submit-calculated` | Central → Middleware → Chain | Store off-chain computed score |
| 6 | POST | `/api/v1/score/preview` | Central / Web app → Middleware | Compute score + dimensions **without writing to chain** (zero gas) |
| 7 | GET | `/api/v1/score/:borrowerRef` | Any consumer → Middleware | Free read of current score |
| 8 | GET | `/api/borrowers/search/` | Frontend / consumers | Unified borrower incl. `loan_applications[]` (see §5.1.1) |
| 9 | POST | `/api/loan-applications/{id}/decision/` | Central analyst | APPROVED / DECLINED + assessment link (see §5.1.2) |
| 10 | POST | `/api/v1/webhooks` | Lender → Middleware | Register a webhook URL to receive score broadcasts |
| 11 | GET / DELETE | `/api/v1/webhooks/:id` | Admin → Middleware | List / remove webhook registrations |
| 12 | POST | `/api/v1/webhooks/:id/test` | Admin → Middleware | Send a signed test ping |
| 13 | Push | `POST <lender webhook url>` | Middleware → Lender | Signed broadcast on every contract event |
| 14 | DELETE | `/api/lenders/{id}/` | Admin | Cascade-deletes the lender + ALL connected rows (204, audited) |

All writes require the Hub wallet (`onlyHub`); reads and previews are permissionless and free.

---

## 8. Webhook broadcasts — Middleware pushes results to Lenders

Instead of polling, a lender registers its URL once and receives every contract result as a signed HTTP POST.

### 8.1 Registering

```bash
curl -X POST http://localhost:5000/api/v1/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://lender.example.com/daire/callback",
    "lenderId": "LDR-DEMO-FLOW",
    "events": ["SCORE_CALCULATED", "SCORE_RECORDED", "INSUFFICIENT_EVIDENCE"]
  }'
```

**Response 201**

```json
{
  "success": true,
  "webhook": {
    "id": "wh_9f8e7d6c5b4a3210",
    "url": "https://lender.example.com/daire/callback",
    "lenderId": "LDR-DEMO-FLOW",
    "events": ["SCORE_CALCULATED", "SCORE_RECORDED", "INSUFFICIENT_EVIDENCE"],
    "createdAt": "2026-09-30T09:41:52.000Z"
  },
  "secretHint": "HMAC secret: WEBHOOK_SECRET env au webhooks.secret.json (X-DAIRE-Signature: sha256=<hex>)"
}
```

Rules: `events` omitted or `[]` = **all events**; registration is persisted to `webhooks.json`; the HMAC secret comes from `WEBHOOK_SECRET` env or is auto-generated into `webhooks.secret.json` on first boot.

### 8.2 The push (what the lender receives)

When the contract emits an event, the middleware POSTs this envelope to every matching webhook:

```http
POST /daire/callback HTTP/1.1
Content-Type: application/json
X-DAIRE-Event: SCORE_CALCULATED
X-DAIRE-Delivery: 0189f3c2-7a51-7d2e-9c44-da2c5f11e9a3
X-DAIRE-Signature: sha256=6f1c2a9d…
User-Agent: DAIRE-Middleware/1.0
```

```json
{
  "delivery_id": "0189f3c2-7a51-7d2e-9c44-da2c5f11e9a3",
  "event": "SCORE_CALCULATED",
  "channel": "blockchain_event",
  "payload": {
    "borrowerRef": "0x3bcdaf773c0ccf4e276e6cf4e00604dca63beef1d7819bacca63575fe97ad275",
    "hub": "0xaa5dbA90D8D0279B4a350193AF53d358D26bfFef",
    "calculation": "ON_CHAIN",
    "score": 780,
    "finalScore": 780,
    "riskBand": "VERY_GOOD",
    "version": 7,
    "assessedAt": 1789479752
  },
  "broadcastAt": "2026-09-30T09:41:52.412Z"
}
```

For `INSUFFICIENT_EVIDENCE` the payload instead carries `missingMask` (bit 1 = history<6mo, 2 = events<8, 4 = repayments<1, 8 = verified<1) and a human-readable `missingExplanation`.

The receiver MUST respond `2xx` within 5 seconds. Retries: 4 attempts with 2s/8s/30s/120s backoff; permanent failures are logged to `webhooks.failed.json`. Verify authenticity with `X-DAIRE-Signature` = `sha256=` + HMAC-SHA256(secret, **raw** body). Use `delivery_id` for idempotency.

### 8.3 Test ping

```bash
curl -X POST http://localhost:5000/api/v1/webhooks/wh_9f8e7d6c5b4a3210/test \
  -H "Content-Type: application/json" -d '{}'
```

Sends a `TEST_PING` event (same headers, same signature) and returns `{"success":true,"httpStatus":200,…}` when the lender endpoint answered 2xx.

---

## 9. `POST /api/v1/score/preview` — score without touching the chain

Same math as `submit-calculated` (parity with contract `previewScore`) but **no transaction, no gas, nothing stored**. Accepts `features` or `dimensions`, `identityHash`/`salt` optional (borrowerRef is computed if given).

**Request (features)**

```json
{
  "identityHash": "NIDA-19950812-12345-00001",
  "salt": "DAIRE_TANZA_SALT_2026",
  "features": {
    "historyMonths": 24, "behaviourEventCount": 30, "repaymentRecordCount": 15,
    "verifiedSourceCount": 2, "onTimeRatioBps": 9800, "maxDaysLate": 0,
    "missedCount": 0, "onTimeStreak": 15, "activeMonthsBps": 10000,
    "regularMonthsBps": 9000, "balanceStabilityBps": 8500, "defaultCount": 0,
    "completedCount": 2, "utilizationBps": 4000, "activeLenderCount": 1,
    "trendBps": 500, "volatilityBps": 1000, "monthsSinceAdverse": 65535,
    "distinctSourceCount": 2, "meanCorroborationX100": 250, "openConflictCount": 0
  }
}
```

**Response 200**

```json
{
  "success": true,
  "status": "PREVIEW",
  "calculation": "OFF_CHAIN",
  "preview": true,
  "borrowerRef": "0x3bcdaf773c0ccf4e276e6cf4e00604dca63beef1d7819bacca63575fe97ad275",
  "data": {
    "finalScore": 780,
    "riskBand": "VERY_GOOD",
    "dimensions": {
      "d1_paymentReliability": 100,
      "d2_financialStability": 92,
      "d3_debtManagement": 100,
      "d4_behaviouralConsistency": 59,
      "d5_trustEvidence": 81
    }
  }
}
```

**Gate failure → 422** (with `status: "INSUFFICIENT_EVIDENCE"`, `missingMask`, `missingExplanation`). **Bad dimensions → 400** (`dimensions.d3 must be a number between 0 and 100`).
