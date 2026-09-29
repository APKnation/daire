# DAIRE Dual-Model Scoring — Input & Output Examples

Three realistic borrower profiles are shown end-to-end: what data enters the system, what each model computes, and what the combined result means for an underwriter.

---

## Inputs: Borrower Data Fields

These fields are collected from lender subsystems and stored on the central borrower record.

| Field | Source | Borrower A — *Amina Hassan* | Borrower B — *John Mwangi* | Borrower C — *Grace Osei* |
|---|---|---|---|---|
| **person_age** | `Borrower.age` | 34 | 52 | 26 |
| **person_income** (TZS/yr) | `Borrower.income` | 18,000,000 | 6,400,000 | 3,200,000 |
| **loan_amnt** (TZS) | Representative active loan | 4,500,000 | 2,800,000 | 1,200,000 |
| **loan_int_rate** (%) | Loan `interest_rate` | 12.5 | 18.0 | 22.0 |
| **loan_percent_income** | loan_amnt ÷ income | 0.25 | 0.44 | 0.375 |
| **cb_person_default_on_file** | Any defaulted loan/repayment | N | N | Y |
| **cb_person_cred_hist_length** (yrs) | First → last transaction date | 8.2 | 3.5 | 1.1 |
| **annual_inc** (NMB input) | Same as person_income | 18,000,000 | 6,400,000 | 3,200,000 |
| **dti** (% of income) | monthly_repayment / monthly_income | 14.3% | 38.7% | 52.1% |
| **term_months** | Loan `loan_duration_months` | 36 | 24 | 12 |
| **verification_status** | NIDA present → Verified | Verified | Source Verified | Not Verified |
| **inq_last_6mths** | Account count − 1 (capped at 4) | 1 | 2 | 0 |

> [!NOTE]
> Fields like `person_home_ownership`, `person_emp_length`, `loan_intent`, `loan_grade` are **not collected** by DAIRE. The ML model's pipeline median-imputes them automatically — this was a deliberate training-time design choice.

---

## Model 1: Scikit-Learn RandomForest (ML)

Trained on `credit_risk_dataset.csv`. Outputs a probability vector over `[0=Healthy, 1=Default]`.

| Metric | Amina Hassan | John Mwangi | Grace Osei |
|---|---|---|---|
| **ML Default Probability** | 8.2% | 34.6% | 63.1% |
| **ML Prediction** | Healthy (0) | Healthy (0) | Default (1) |
| **ML Confidence** | 91.8% | 65.4% | 63.1% |

---

## Model 2: NMB Banking Scorecard (WoE/Logistic)

Frozen WoE logistic scorecard calibrated on the 300–850 bureau scale. Uses 8 inputs.

| Metric | Amina Hassan | John Mwangi | Grace Osei |
|---|---|---|---|
| **NMB Log-Odds** | −2.71 | −0.58 | +0.94 |
| **NMB Default Probability** | 6.2% | 35.9% | 71.9% |
| **NMB Credit Score (300–850)** | 791 | 544 | 388 |
| **Top Strength** | Low DTI (14.3%) | Source Verified | — |
| **Top Risk Factor** | — | High DTI (38.7%) | No verified identity + prior default |

---

## Ensemble Consensus (50% ML + 50% NMB)

| Metric | Amina Hassan | John Mwangi | Grace Osei |
|---|---|---|---|
| **Blended PD (ensemble)** | 7.2% | 35.3% | 67.5% |
| **Model Spread** | 2.0% | 1.3% | 8.8% |
| **Concordance** | ✅ HIGH_AGREEMENT | ✅ HIGH_AGREEMENT | ⚠️ MODERATE_AGREEMENT |
| **Agreement %** | 98.0% | 98.7% | 91.2% |

---

## Output: Full Scoring Result

| Output Field | Amina Hassan | John Mwangi | Grace Osei |
|---|---|---|---|
| **Credit Grade** | **A** | **C** | **D** |
| **Credit Tier** | Prime (Tier 1) | Subprime (Tier 3) | Deep Subprime (Tier 4) |
| **Reputation** | EXCELLENT | MODERATE | HIGH_RISK |
| **Risk Level** | LOW | MEDIUM | HIGH |
| **Score (0–1)** | 0.928 | 0.647 | 0.325 |
| **Underwriting Decision** | ✅ APPROVED | ⚠️ MANUAL_REVIEW | 🚫 DECLINED |
| **Decision Label** | Approved for Standard Terms | Refer to Credit Committee | Declined — Exceeds Risk Appetite |

---

## Basel II Expected Loss Breakdown

> Formula: **EL = PD × LGD × EAD**

| Component | Amina Hassan | John Mwangi | Grace Osei |
|---|---|---|---|
| **PD** (ensemble) | 7.2% | 35.3% | 67.5% |
| **LGD** (savings-adjusted) | 39% | 51% | 52% |
| **EAD** (loan exposure) | TZS 4,500,000 | TZS 2,800,000 | TZS 1,200,000 |
| **Expected Loss (EL)** | **TZS 126,360** | **TZS 506,688** | **TZS 421,200** |

> [!TIP]
> LGD is dynamically adjusted: more savings → lower LGD (floor 35%, ceiling 65%). This means a borrower with substantial savings buffer absorbs more loss themselves, lowering the bank's exposure.

---

## Pricing & Credit Capacity

| Metric | Amina Hassan | John Mwangi | Grace Osei |
|---|---|---|---|
| **Monthly Income** | TZS 1,500,000 | TZS 533,333 | TZS 266,667 |
| **Max Safe Monthly Payment** | TZS 586,500 | TZS 6,933 | TZS (over limit) |
| **Recommended Credit Limit** | **TZS 6,750,000** | **TZS 4,200,000** | **TZS 1,000,000** |
| **Base APR** | 9.50% | 9.50% | 9.50% |
| **Risk Spread** (PD × 18%) | +1.30% | +6.35% | +12.15% |
| **Recommended APR** | **10.80%** | **15.85%** | **21.65%** |
| **Collateral Policy** | Clean unsecured — no security | 25% savings lien or co-guarantor | 100% tangible asset / cash pledge |

---

## Actionable Guidance per Borrower

### Amina Hassan — APPROVED ✅
- Maintain 6 consecutive on-time repayments to retain Grade A status.
- Eligible for pre-approved top-up at existing terms after 12 months.

### John Mwangi — MANUAL REVIEW ⚠️
- **Debt Optimization:** Reduce existing obligations to bring DTI below 20% — this would lower PD by ~6% and unlock APR of **13.35%**.
- **Repayment Discipline:** 6 months of on-time payments will elevate grade from C → B.
- **Inquiry Management:** Refrain from additional multi-lender inquiries for 90 days.

### Grace Osei — DECLINED 🚫
- **Prior Default Resolution:** Dispute or settle the adverse mark on file — minimum 12-month clean period required before re-application.
- **Debt Optimization:** DTI of 52.1% must fall below 35% before creditworthiness can be re-assessed.
- **Credit Building:** Open a supervised micro-credit product and demonstrate 12 consecutive payments.

---

## How the Score Explanation Is Stored

Each result is saved to the `AIReputationResult` database record with the following structure in `score_explanation`:

```json
[
  {
    "dimension": "DECISION",
    "name": "Underwriting: APPROVED",
    "value": "Grade A · Prime (Tier 1)",
    "reason": "Eligible for clean financing. Favorable dual-model consensus (PD 7.2%) backed by clean credit record."
  },
  {
    "dimension": "SKLEARN",
    "name": "RandomForest ML Model",
    "value": "8.2% Default Proba",
    "reason": "Scikit-learn supervised model; prediction: Healthy (confidence 91.8%)."
  },
  {
    "dimension": "NMB",
    "name": "NMB Banking Scorecard",
    "value": "Score 791/850 (6.2% PD)",
    "reason": "Frozen banking WoE scorecard (historical_offer); log-odds: -2.71."
  },
  {
    "dimension": "EXPOSURE",
    "name": "Basel II Expected Loss",
    "value": "TZS 126,360",
    "reason": "EL = PD (7.2%) × LGD (39%) × EAD (TZS 4,500,000)."
  },
  {
    "dimension": "TERMS",
    "name": "Recommended Limit & APR",
    "value": "TZS 6,750,000 @ 10.80% APR",
    "reason": "Max safe debt service: TZS 586,500/mo. Clean unsecured facility eligible; no tangible security required."
  }
]
```
