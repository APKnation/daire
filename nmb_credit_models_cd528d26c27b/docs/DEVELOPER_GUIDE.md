# Developer guide — NMB credit model bundle

## Purpose and permitted use

This guide is for developers integrating the frozen educational PD, scorecard, LGD, EAD
and expected-loss models into a local test application. The models were trained on public
US LendingClub loans issued from 2007 to 2014, not on NMB customers or Tanzanian banking
data.

Permitted use is limited to authorised internal education, software integration and
simulation. The outputs must not approve, decline, price or limit credit and must not be
used for provisioning, capital, regulatory reporting or customer communication. Read
`docs/MODEL_CARD.md` before integrating the bundle.

There is no approved external redistribution licence. Do not publish the wheel, model
files, JSON scorecard, container or archive to a public package index, repository or model
registry until the owner has approved licensing, branding, data-terms and security review.

## Release layout

The build command is:

~~~bash
make bundle
~~~

It produces three deliverables in `dist/`:

~~~text
nmb_credit_models_<model-version>/
nmb_credit_models_<model-version>.zip
nmb_credit_models_<model-version>.zip.sha256
~~~

Inside the directory or ZIP:

| Path | Purpose |
|---|---|
| `README.md` | Short route selector and safety boundary |
| `CHECKSUMS.sha256` | SHA-256 for every file inside the release |
| `docs/MODEL_CARD.md` | Performance, limitations, monitoring and use decision |
| `docs/VERSIONS.json` | Model component hashes, build platform and direct library versions |
| `portable/pd_scorecard.json` | Language-neutral PD binning, coefficients and score scaling |
| `portable/score_pd.py` | Dependency-free reference scorer |
| `portable/parity_report.json` | Held-out parity evidence for both portable PD models |
| `python/nmb_credit-*.whl` | Runtime library |
| `python/artifacts/` | Frozen PD, LGD and EAD artifacts and manifests |
| `python/config/config.yaml` | Feature lists and artifact paths used by the loader |
| `python/requirements-lock.txt` | Tested Python dependency snapshot |
| `python/example_python.py` | One complete PD–LGD–EAD–EL example |

The model version is derived from the hashes of the five governed model components. The
Python package version and model version are different identifiers: `0.1.0` identifies
the library API, while a value such as `cd528d26c27b` identifies the exact model set.
Record both in application logs.

## Verify a received release first

Do not load a pickle before checking the handoff. From the directory containing the ZIP:

~~~bash
sha256sum --check nmb_credit_models_<model-version>.zip.sha256
unzip nmb_credit_models_<model-version>.zip
cd nmb_credit_models_<model-version>
sha256sum --check CHECKSUMS.sha256
~~~

On PowerShell, calculate the archive digest with:

~~~powershell
Get-FileHash .\nmb_credit_models_<model-version>.zip -Algorithm SHA256
~~~

Compare the archive digest with the sender through a trusted channel. The checksum file
detects accidental corruption; because it is not digitally signed, receiving both files
from the same untrusted source does not establish authenticity.

Never load `.pkl` files obtained from an untrusted or public location. Unpickling can
execute code. The portable JSON route avoids pickle for PD-only integration.

## Choose an integration route

| Requirement | Recommended route |
|---|---|
| PD and 300–850 score in Python with no third-party packages | Portable route |
| PD and score in Java, C#, JavaScript or SQL | Port the portable JSON contract and parity-test it |
| Full PD, LGD, EAD and expected loss in Python | Python wheel and frozen artifacts |
| Browser, mobile or non-Python application | Separate `nmb_credit_score` HTTP API |

The ZIP does not include third-party dependency wheels. The Python route therefore needs
access to an approved Python package index. For an offline deployment, the receiving team
must create and govern a separate wheelhouse for Python 3.12 and the target operating
system.

## Route A: portable PD and score

This route uses only `portable/pd_scorecard.json`. The supplied Python implementation is
a readable contract and needs only Python's standard library.

~~~bash
cd portable
python3 score_pd.py
~~~

~~~python
from score_pd import Scorecard

card = Scorecard.load("pd_scorecard.json")
result = card.score(
    {
        "term_months": 36,
        "annual_inc": 62_000,
        "dti": 16.05,
        "purpose": "debt_consolidation",
        "verification_status": "Verified",
        "inq_last_6mths": 1,
        "total_rev_hi_lim": 22_100,
    },
    model="application_only",
)

print(result["probability_of_default"])
print(result["credit_score"])
print(result["contributions"])
~~~

`application_only` is the preferred educational model. It excludes lender grade and
interest rate. `historical_offer` additionally requires `int_rate`; despite its name, the
frozen primary model does not use `grade`. Interest rate reflects the historical lender's
pricing decision and can make performance appear stronger.

### Portable input contract

| Field | Type | Unit or allowed form | Required by |
|---|---|---|---|
| `verification_status` | string | `Verified`, `Source Verified`, `Not Verified` | both |
| `purpose` | string | exact training category in the JSON | both |
| `term_months` | integer | months; fitted values are 36 or 60 | both |
| `annual_inc` | number | annual income, same currency unit as development data | both |
| `dti` | number | percentage points: `16.05` means 16.05%, not `0.1605` | both |
| `inq_last_6mths` | number | count | both |
| `total_rev_hi_lim` | number or null | revolving credit limit | both |
| `int_rate` | number | percentage points: `13.65` means 13.65% | `historical_offer` only |

Missing keys raise `KeyError`. A categorical value absent from the fitted scorecard raises
`UnknownCategory`; do not silently map it to another category. Null values use the fitted
missing bin where one exists. Validate numeric types, plausible ranges and currency before
calling the scorer.

The result contains:

| Key | Meaning |
|---|---|
| `model` | `application_only` or `historical_offer` |
| `probability_of_default` | eventual non-repayment probability on the model's selected population |
| `in_100` | rounded communication aid, not a separate estimate |
| `log_odds` | logistic-model output before conversion to probability |
| `credit_score` | exact 300–850 transform; higher is lower estimated risk |
| `contributions` | per-feature value, WoE and log-odds contribution |

When porting the JSON contract to another language, compare a representative set of rows
with `score_pd.py`, covering every bin, nulls, boundary values and unknown categories.
The release builder already verifies the supplied Python implementation on all 46,159
held-out rows; your port needs its own parity evidence.

## Route B: full Python scoring stack

Use Python 3.12. A normal online installation lets the wheel install its exactly pinned
direct dependencies:

~~~bash
cd python
python3.12 -m venv .venv
.venv/bin/python -m pip install nmb_credit-0.1.0-py3-none-any.whl
.venv/bin/python example_python.py
~~~

For the exact transitive dependency versions present when the release was verified:

~~~bash
cd python
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --no-deps nmb_credit-0.1.0-py3-none-any.whl
.venv/bin/python -m pip check
.venv/bin/python example_python.py
~~~

On Windows, replace `.venv/bin/python` with `.venv\Scripts\python.exe`.

Load the engine once at process start, keep it immutable, and reuse it for scoring:

~~~python
from pathlib import Path

import pandas as pd

from nmb_credit.config import load_config
from nmb_credit.models.expected_loss import load_expected_loss_engine, score_expected_loss

bundle_python = Path("/absolute/path/to/bundle/python")
config = load_config(bundle_python / "config" / "config.yaml")
engine = load_expected_loss_engine(config)  # verifies governed artifact hashes

applications = pd.DataFrame(
    [
        {
            "funded_amnt": 12_000.0,
            "term_months": 36,
            "int_rate": 13.65,
            "installment": 408.09,
            "purpose": "debt_consolidation",
            "grade": "B",
            "initial_list_status": "f",
            "annual_inc": 62_000.0,
            "dti": 16.05,
            "home_ownership": "MORTGAGE",
            "emp_length_years": 6.0,
            "verification_status": "Verified",
            "addr_state": "CA",
            "credit_history_months": 168.0,
            "inq_last_6mths": 1.0,
            "delinq_2yrs": 0.0,
            "total_rev_hi_lim": 22_100.0,
            "open_acc": 11.0,
            "total_acc": 24.0,
            "pub_rec": 0.0,
            "acc_now_delinq": 0.0,
            "mths_since_last_delinq": None,
            "mths_since_last_record": None,
        }
    ]
)

result = score_expected_loss(engine, applications, config)
print(result.to_dict(orient="records"))
~~~

The complete runnable version is `python/example_python.py`.

### Full-stack input contract

All rows need the following canonical fields. Use `None`/`NaN` only where the source
genuinely has no value; do not replace missing credit history with zero.

| Group | Fields | Unit or representation |
|---|---|---|
| Facility | `funded_amnt`, `installment` | nominal amount per loan and scheduled payment amount |
| Terms | `term_months`, `int_rate` | months; percentage points |
| Offer descriptors | `grade`, `initial_list_status`, `purpose` | exact source categories |
| Affordability | `annual_inc`, `dti` | annual amount; percentage points |
| Borrower | `home_ownership`, `emp_length_years`, `verification_status`, `addr_state` | exact source categories; years |
| Credit record | `credit_history_months`, `inq_last_6mths`, `delinq_2yrs`, `open_acc`, `total_acc`, `pub_rec`, `acc_now_delinq` | months or counts |
| History and limits | `total_rev_hi_lim`, `mths_since_last_delinq`, `mths_since_last_record` | nominal limit or months; null allowed |

The library contract expects already-canonical field names such as `term_months` and
`credit_history_months`. It does not accept raw LendingClub strings such as `"36 months"`
or dates such as `earliest_cr_line`. The HTTP service performs a separate request-to-model
mapping and should be preferred for interactive applications.

### Full-stack outputs

Each input row produces one output row in the same order:

| Column | Interpretation |
|---|---|
| `primary_pd` | PD including historical lender interest rate |
| `challenger_pd` | application-only PD excluding grade and interest rate |
| `exact_score`, `integer_score` | 300–850 transform of `primary_pd` |
| `expected_recovery_rate` | predicted gross nominal recovery / funded amount |
| `bounded_lgd` | `1 - expected_recovery_rate` |
| `bounded_ead_ratio` | predicted unpaid-principal ratio proxy |
| `bounded_ead_amount` | EAD proxy in the same nominal currency as `funded_amnt` |
| `formula_expected_loss` | `primary_pd × bounded_lgd × bounded_ead_amount` |
| `formula_expected_loss_rate` | formula EL / funded amount |
| `denominator_consistent_lgd` | loss amount divided by EAD proxy |
| `denominator_consistent_expected_loss` | denominator-consistent sensitivity, not an accounting result |
| `denominator_consistent_expected_loss_rate` | sensitivity / funded amount |
| `course_workout_expected_loss` | course-model comparator |
| `challenger_pd_expected_loss` | formula EL using application-only PD |

The score is based on `primary_pd`, while `challenger_pd` is the cleaner estimate of the
model's application-only contribution. Do not mix their labels in a user interface.
Amounts carry no built-in currency conversion; inputs and displayed outputs must use one
consistent currency.

### Batch scoring and failures

Pass multiple rows in one `DataFrame`; do not reload the engine per row. The loader fails
closed if a governed artifact hash or frozen-state manifest is wrong. Scoring raises
`ValueError` for missing canonical columns or outputs outside enforced bounds. Catch those
errors at the service boundary, record the model version, and return a non-success result;
never substitute a default score.

The library is a numerical scoring layer, not a production API. It does not provide
authentication, request limits, schema coercion, audit persistence, personally identifiable
information controls, service health checks or decision workflow.

## Route C: HTTP service and web application

The API and web application live in the separate `nmb_credit_score` project. From that
project, point the service at this bundle's `python/` directory:

~~~bash
NMB_MODEL_PROJECT_ROOT=/absolute/path/to/bundle/python make dev-api
~~~

Use the API for browser or non-Python clients rather than loading model artifacts in the
front end. Keep model files server-side. Consult that project's API schema and deployment
documentation for request validation, health checks and container operation.

## Integration controls

Before accepting an integration:

1. Verify the archive and all internal checksums.
2. Record package version, model version and five component hashes at service start.
3. Run the supplied portable and full-stack examples and retain their outputs.
4. Add a golden-row regression test in the consuming application.
5. Validate required fields, types, units, allowed categories and missing values before scoring.
6. Keep a stable request identifier and model version with each retained result; do not log unnecessary personal data.
7. Reject unknown or malformed input instead of silently coercing it.
8. Keep the engine and artifacts read-only and load them once per process.
9. Expose estimates separately from any human policy decision; never convert zones into automatic approval rules.
10. Monitor input drift, missingness, output drift, errors and latency. Outcome validation requires mature outcomes.

## Upgrading to another release

Treat a model-version change as a controlled change, even if the wheel version is the
same. Keep the previous ZIP for rollback, verify the new checksums, compare `VERSIONS.json`
and the model card, rerun golden-row and parity tests, then deploy to a non-production
environment first. Do not overwrite artifacts inside an existing versioned directory.

Changes to field definitions, preprocessing, coefficients, binning, library versions or
the score scale require regression review. A successful import alone is not evidence that
two releases are behaviourally equivalent.

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `Config not found` | Wrong bundle root | Load `python/config/config.yaml` by absolute path |
| `Frozen component hash mismatch` | Damaged or mixed artifacts | Stop; verify checksums and obtain a clean release |
| Import or unpickle error | Wrong Python/library environment | Use Python 3.12 and the supplied lock snapshot |
| Missing canonical columns | Raw or incomplete application schema | Map and validate fields before scoring |
| `UnknownCategory` in portable scorer | Category absent in training | Reject or route for review; do not invent a mapping |
| Different PD after a language port | Boundary, missing-bin or logistic conversion mismatch | Compare every bin and boundary against `score_pd.py` |
| Installation attempts internet access | Dependencies are not bundled | Use an approved package index or build a governed wheelhouse |

For methodological questions, start with `docs/MODEL_CARD.md`. For a code defect, provide
the bundle model version, package version, Python version, operating system, failing input
with sensitive fields removed, exception text and a minimal reproduction.
