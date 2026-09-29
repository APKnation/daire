# Consolidated Model Card, Monitoring, and Deployment Readiness

**Version:** 1.0  
**Date:** 2026-09-09  
**Model:** educational LendingClub PD–LGD–EAD–Expected Loss stack  
**Decision:** educational analysis `GO`; local simulation `CONDITIONAL GO`; public and
real NMB use `NO-GO`

**Evidence-location note:** paths listed under Evidence files refer to the governed source
project. The developer bundle carries the model card and runtime manifests, not the
notebooks or all derived evaluation tables.

## Executive conclusion

Notebooks 01–09 now demonstrate a complete, reproducible credit-risk workflow. Frozen
artifacts reproduce held-out results, every transformation is fitted on training only,
and notebook 09 applies the unchanged stack to the untouched 2015 population.

The engineering evidence is strong enough for education and continued research. It is
not evidence that the model is fit for NMB lending, pricing, limits, capital, provisioning
or impairment. The data are LendingClub accepted loans, the PD target is an eventual
resolved outcome rather than a fixed-horizon bank definition, LGD is nominal gross loss,
EAD is an unpaid-principal proxy, and no independent institutional validation exists.

## Model components and frozen evidence

| Component | Specification | Main held-out evidence | Frozen SHA-256 |
|---|---|---|---|
| PD primary | WoE logistic regression; excludes `grade`, retains `int_rate` | AUC 0.6983; Gini 0.3966; KS 0.2946; O/E 0.9991 | `05075e72…eba6ff` |
| PD challenger | Excludes both `grade` and `int_rate` | AUC 0.6681; Gini 0.3363; O/E 0.9950 | `2585f5f6…c778c` |
| PD binner | Train-only monotonic OptBinning | Nine selected characteristics | `af7a50b0…532c` |
| LGD | Two-stage recovery occurrence × bounded fractional severity | Recovery R² 0.0211; aggregate recovery O/E 0.9757 | `f5f60b12…c2c346` |
| EAD | Bounded fractional-logit unpaid-principal ratio | R² 0.201; Spearman 0.466; O/E 1.0004 | `e50d0117…c23f` |

Notebook 08 integrates these components without refitting. On 46,159 held-out PD rows,
the course-compatible expected loss is 14.10% of funding and the denominator-consistent
nominal sensitivity is 13.81%. On final-outcome-eligible rows, the latter is 97.18% of the
observed direct-loss proxy. That agreement is internal evidence on the same selected and
partly resolved population, not external or regulatory validation.

## Notebook-09 monitoring design

| Population | Rows | Definition |
|---|---:|---|
| Development baseline | 184,636 | Governed PD training membership from resolved 2007–2014 accepted loans |
| Monitoring | 421,094 | Every funded loan in the untouched 2015 file; no outcome filter |

The monitoring comparison uses fixed development quantile boundaries for continuous
outputs and the exact frozen PD bin indices for characteristics. Missing groups and bins
present in only one population retain a finite PSI contribution. The configured green
(`<0.10`), amber (`0.10–<0.25`) and red (`>=0.25`) levels are management heuristics for
this demonstration; they are not universal regulatory thresholds.

### Output PSI

| Output | Baseline mean | 2015 mean | PSI | Status |
|---|---:|---:|---:|---|
| Expected recovery rate | 5.72% | 4.71% | 0.612 | RED |
| Bounded EAD ratio | 69.66% | 74.31% | 0.343 | RED |
| Challenger PD | 19.09% | 21.47% | 0.059 | GREEN |
| Exact score | 585.39 | 594.37 | 0.029 | GREEN |
| Primary PD | 19.09% | 18.43% | 0.029 | GREEN |
| Formula EL rate | 13.18% | 13.64% | 0.018 | GREEN |
| Denominator-consistent EL rate | 12.88% | 13.44% | 0.018 | GREEN |

This is a material finding: stable PD, score and combined EL distributions coexist with
large and opposing movements in the workout components. Monitoring only the final score
or EL would miss the change in recovery and exposure composition.

### Frozen-bin characteristic stability

| Characteristic | CSI | Status | Interpretation |
|---|---:|---|---|
| `total_rev_hi_lim` | 0.624 | RED | Missing rate fell from 28.80% to 0%; definition/coverage change dominates |
| `dti` | 0.139 | AMBER | Distribution shift |
| `inq_last_6mths` | 0.108 | AMBER | Distribution shift and baseline missingness difference |
| `verification_status` | 0.101 | AMBER | Borderline amber shift |
| `int_rate` | 0.091 | GREEN | Near the project amber trigger |
| Remaining selected characteristics | 0.010–0.067 | GREEN | No project-level PSI escalation |

The result strengthens the earlier decision to retain `total_rev_hi_lim` in the immutable
evaluated primary but flag it for temporal redevelopment. Its development coefficient was
marginal (p=0.0262), its mature-vintage sign reversed, and its 2015 missingness regime
changed completely.

### Data-quality and applicability alerts

Six fields trigger a separate alert:

- `total_rev_hi_lim`, `mths_since_last_delinq`, and `mths_since_last_record`: material
  missing-rate changes;
- `int_rate`: 2.60% of 2015 values lie outside the development range;
- `addr_state`: `ND` is new relative to the governed baseline (0.114% of 2015); this
  candidate was not selected by the binner, but input monitoring still records it;
- `home_ownership`: two 2015 rows use `ANY`, a value absent from the fitted LGD/EAD
  encoder vocabularies. The encoder's all-zero fallback remains numerically operational,
  but deployment must decide whether to reject, map, or explicitly support it.

## Why no 2015 performance metrics are reported

Only 26,144 of 421,094 2015 rows (6.21%) meet the configured resolved good/bad definition:
22,984 Fully Paid and 3,160 bad. The remaining 394,950 are unresolved, including 377,553
`Current` loans. Calculating AUC, calibration or realised EL on the early-resolving
6.21% would reproduce the survivorship distortion already the project was designed to expose.

Notebook 09 therefore enforces an 80% maturity gate and refuses outcome back-testing.
PSI says the scored population changed; it does not say whether discrimination or
calibration improved or deteriorated.

## Consolidated limitations

1. **Purpose and geography:** public US LendingClub data are not representative of NMB,
   Tanzania, its customers, products, policy, currency or economic environment.
2. **Population selection:** funded loans only; rejected applicants and their outcomes
   are unavailable. PD is conditional on LendingClub's historical approval policy.
3. **PD horizon:** eventual adverse outcome among resolved accounts, not a Basel one-year
   PD or a formally staged IFRS 9 lifetime PD.
4. **Outcome maturity:** 61% of development rows come from partly resolved 2013–2014
   vintages; the integrated model under-predicts observed loss in 2014 by about 11%.
5. **Validation split:** the main 80/20 split is stratified random for course comparison,
   not an out-of-time or external validation design.
6. **Policy variables:** the primary retains LendingClub `int_rate`. The challenger is the
   more honest policy-output-free estimate and has Gini 0.336.
7. **LGD:** nominal gross recovery with no recovery timing, discounting, workout strategy,
   legal cost or downturn calibration. Individual explanatory power is weak.
8. **EAD:** unpaid funded-principal proxy for amortising term loans, not a true default-date
   exposure or revolving-facility CCF.
9. **EL:** `PD × LGD × EAD` is course-compatible, but recovery and EAD denominators differ;
   the denominator-consistent formulation remains a sensitivity, not an accounting result.
10. **Economics:** notebook-05 cut-offs are explicitly hypothetical and exclude real NMB
    funding, capital, tax, prepayment, collections, capacity and risk appetite.
11. **Fairness and explainability:** no approved protected-class assessment, proxy review,
    adverse-action process or customer-impact validation has been completed.
12. **Serving:** a local demonstration API and web application now use the reusable
    scoring contract and regression tests. Production identity, privacy, service
    monitoring, fallback, rollback and operational approval remain unimplemented.

## Governance and monitoring plan for any future institutional model

The current readiness register assigns an intended owner to each gap. Before first use, a
real model would require an approved model inventory entry, materiality tier, business and
technical owners, independent validation, documented approval authority, change control,
exception governance, rollback and retirement criteria.

Suggested monitoring layers are:

| Layer | Measures | Response |
|---|---|---|
| Every scoring batch / service window | schema, missingness, invalid/unseen categories, ranges, volume, latency, errors, model hash/version | fail closed for invalid contracts; operational alert and rollback where required |
| Regular population review | feature CSI, primary/challenger PD, score, LGD, EAD and EL PSI; approval and override mix | investigate product, policy, source-system or population changes before recalibration |
| Mature outcome review | AUC/Gini/KS, Brier/log loss, O/E, calibration slope/bands, recovery/EAD/EL error, vintage and segment stability | overlay, recalibrate, restrict or redevelop under approved thresholds |
| Periodic independent validation | conceptual soundness, data lineage, implementation reproduction, benchmarking, limitations, fairness and outcomes | independent challenge and approval/no-approval decision |

Thresholds, frequency, materiality and escalation authority must be established by the
institution for the model's actual use. They cannot be inferred from this demonstration.

## Deployment decision

| Proposed use | Decision | Conditions/reason |
|---|---|---|
| Executed educational analysis | **GO** | Frozen evidence is reproducible and limitations are visible |
| Local educational web demonstration | **CONDITIONAL GO** | Implemented and regression-tested locally; keep controlled and simulation-only |
| External/public demonstration | **NO-GO** | Security, privacy, operations and misuse controls are absent |
| NMB lending, pricing, limits, capital or impairment | **NO-GO** | Institution-specific data, definitions, validation, economics, governance and approvals are absent |

The detailed 16-control inventory is in
[`artifacts/deployment_readiness_register.csv`](../artifacts/deployment_readiness_register.csv).

## Reference and governance anchors

- Supplied course monitoring notebook for the PSI workflow, with the documented
  corrections implemented here.
- Basel Committee credit-risk principles, including ongoing measurement, monitoring,
  controls and independent assessment:
  <https://www.bis.org/committees/bcbs/basel-consolidated-guidelines/module/cri/10>
- Revised US interagency model-risk guidance, used as a lifecycle reference—not a claim
  that US rules govern this project:
  <https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm>
- Bank of Tanzania regulations and guidelines index, which must be reviewed formally for
  any Tanzania-specific implementation:
  <https://bot.go.tz/BankSupervision/Regulations>

## Evidence files

- `notebooks/09_monitoring_governance.ipynb`
- `artifacts/monitoring_component_summary.csv`
- `artifacts/monitoring_component_bins.csv`
- `artifacts/monitoring_feature_csi.csv`
- `artifacts/monitoring_feature_bins.csv`
- `artifacts/monitoring_data_quality.csv`
- `artifacts/monitoring_maturity_audit.csv`
- `artifacts/deployment_readiness_register.csv`
- `artifacts/deployment_decisions.csv`
- `artifacts/monitoring_manifest.json`
- `reports/figures/09_monitoring_governance.png`
- `agent_reviews/decisions/ADR-015-monitoring-and-deployment-readiness.md`
