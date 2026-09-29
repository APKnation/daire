# NMB credit models — shared bundle

Frozen probability-of-default, loss-given-default, exposure-at-default and expected-loss
models, packaged for a controlled developer handoff.

**Read `docs/MODEL_CARD.md` before using these models.** They are an educational
demonstration built on public US LendingClub loans from 2007-2014. They are not
calibrated to NMB customers and must not be used to approve, decline or price loans, or
for accounting or regulatory purposes. They produce a risk estimate, never a decision.

## Which route do you need?

| You want | Use | Needs |
|---|---|---|
| Probability of default and a 300-850 score | `portable/` | Standard-library Python, or port the JSON contract |
| The full chain including LGD, EAD and expected loss | `python/` | Python 3.12 and package-index access |
| To call the models over HTTP from another application | the separate API service | `nmb_credit_score` checkout and Docker |

Start with [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md). It defines the input
and output contracts, installation choices, batch scoring, integrity checks, error
handling, deployment boundary and release-upgrade procedure.

### 1. Portable scorecard — no dependencies

`portable/pd_scorecard.json` holds the bin edges, the weight of evidence for each bin,
the model coefficients and the score scaling. `portable/score_pd.py` is a reference
implementation in about 80 lines of standard-library Python; porting it to Java, C#,
JavaScript or SQL is straightforward.

```bash
cd portable && python score_pd.py
```

```python
from score_pd import Scorecard

card = Scorecard.load("pd_scorecard.json")
result = card.score({
    "term_months": 36, "annual_inc": 62000, "dti": 16.05,
    "purpose": "debt_consolidation", "verification_status": "Verified",
    "inq_last_6mths": 1, "total_rev_hi_lim": 22100,
})
result["probability_of_default"]   # 0.1693
result["credit_score"]             # 582.3
result["contributions"]            # per-feature evidence and effect
```

Two models are included. `application_only` excludes lender grade and interest rate and
is the preferred educational demonstration. `historical_offer` uses the lender's
interest rate, which is an output of the lender's own pricing decision, so it can flatter
the model. Neither result is approved for communication to or decisions about borrowers.

`portable/parity_report.json` records the check that this export reproduces the frozen
models on all 46,159 held-out loans, to within 1e-12.

### 2. Python package — the full chain

```bash
cd python
python -m venv .venv
.venv/bin/python -m pip install nmb_credit-0.1.0-py3-none-any.whl
.venv/bin/python example_python.py
```

This normal installation downloads dependencies. For the exact dependency snapshot used
to verify this release, follow the reproducible-install instructions in the developer
guide. Third-party dependency wheels are not included, so this is not an offline bundle.

`load_expected_loss_engine` verifies the SHA-256 hash of every artifact against its
manifest and refuses to load anything that is not in its frozen state.

The model files are Python pickles, so they are bound to the pinned library versions in
the wheel's metadata. Loading a pickle executes code inside it: only load these files
from a copy you trust, and check them against `CHECKSUMS.sha256` first.

```bash
cd /path/to/this/bundle          # the paths are relative to the bundle root
sha256sum --check CHECKSUMS.sha256
```

### 3. HTTP API — any language

The separate service in the `nmb_credit_score` project loads this same bundle and exposes
`POST /api/v1/score`, returning PD, score, zone, LGD, EAD, expected loss and plain
explanations, plus `/api/v1/model` for the version and limitations. Point it at this
bundle's `python/` folder:

```bash
NMB_MODEL_PROJECT_ROOT=/path/to/this/bundle/python  make dev-api
```

## What is in here

```
portable/   pd_scorecard.json, score_pd.py, parity_report.json
python/     wheel, artifacts/, config/, requirements-lock.txt, example_python.py
docs/       MODEL_CARD.md, DEVELOPER_GUIDE.md, VERSIONS.json
CHECKSUMS.sha256
```

`docs/VERSIONS.json` records the model version, the hash of every component and the
direct model-library versions and build platform. `python/requirements-lock.txt` records
the complete installed dependency closure in the environment used to verify the bundle.

## Distribution boundary

This repository has no approved open-source or external redistribution licence. The
bundle is therefore for authorised internal educational evaluation only. Do not publish
it to PyPI, GitHub, a public model registry or a public container registry until the
owner has approved a licence, branding, data-terms and security review.

## Rules that travel with the models

- Estimates only: no approve, decline, price or limit output, and no automated decision.
- The model card's limitations must reach anyone who sees a number these models produce.
- Do not redistribute the training data: it is not in this bundle and is restricted.
- Report the model version (`docs/VERSIONS.json`) with any result you keep.
- Compare the ZIP digest through a trusted channel; an unsigned checksum sent beside a
  file detects transfer errors but does not prove who produced the file.
