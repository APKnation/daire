"""Score one application with the frozen models, from Python.

    python -m venv .venv
    .venv/bin/pip install nmb_credit-0.1.0-py3-none-any.whl
    .venv/bin/python example_python.py

This route gives the whole chain: probability of default, credit score, loss given
default, exposure at default and expected loss. The models are loaded once and every
artifact's SHA-256 hash is verified against its manifest before anything is scored.

For probability of default alone, portable/score_pd.py needs no dependencies at all.
"""

from pathlib import Path

import pandas as pd

from nmb_credit.config import load_config
from nmb_credit.models.expected_loss import load_expected_loss_engine, score_expected_loss

HERE = Path(__file__).resolve().parent

# One application. Fields the applicant cannot supply are left as None: the models
# treat "not recorded" as its own evidenced category rather than guessing a value.
application = pd.DataFrame([{
    # the loan
    "funded_amnt": 12000.0,
    "term_months": 36,
    "int_rate": 13.65,
    "installment": 408.09,
    "purpose": "debt_consolidation",
    "grade": "B",                     # the lender's own risk grade, used for loss estimates
    "initial_list_status": "f",
    # the borrower
    "annual_inc": 62000.0,
    "dti": 16.05,                     # monthly debt payments as % of monthly income
    "home_ownership": "MORTGAGE",
    "emp_length_years": 6.0,
    "verification_status": "Verified",
    "addr_state": "CA",
    # the credit record
    "credit_history_months": 168.0,
    "inq_last_6mths": 1.0,
    "delinq_2yrs": 0.0,
    "total_rev_hi_lim": 22100.0,
    "open_acc": 11.0,
    "total_acc": 24.0,
    "pub_rec": 0.0,
    "acc_now_delinq": 0.0,
    "mths_since_last_delinq": None,
    "mths_since_last_record": None,
}])

config = load_config(HERE / "config" / "config.yaml")
engine = load_expected_loss_engine(config)
scored = score_expected_loss(engine, application, config)

headline = [
    "challenger_pd",          # application-only: excludes grade and interest rate
    "primary_pd",             # includes the lender's interest rate
    "exact_score",            # 300-850, higher is lower risk
    "bounded_lgd",            # share of exposure lost if the loan is not repaid
    "bounded_ead_ratio",
    "bounded_ead_amount",
    "formula_expected_loss",
    "denominator_consistent_expected_loss",
]
for column in headline:
    print(f"{column:38s} {scored[column].iloc[0]:,.6f}")
