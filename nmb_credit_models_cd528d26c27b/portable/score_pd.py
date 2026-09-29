"""Score a loan application against the frozen NMB credit scorecard.

Uses only the Python standard library: no pandas, no scikit-learn, no pickle. Every
number comes from pd_scorecard.json, which is exported from the frozen models and
checked against them on all 46,159 held-out loans (see parity_report.json).

    from score_pd import Scorecard
    card = Scorecard.load("pd_scorecard.json")
    result = card.score({
        "term_months": 36, "int_rate": 13.65, "annual_inc": 62000, "dti": 16.05,
        "purpose": "debt_consolidation", "verification_status": "Verified",
        "inq_last_6mths": 1, "total_rev_hi_lim": 22100, "grade": "B",
    })
    result["probability_of_default"], result["credit_score"]

The same logic ports to Java, C#, JavaScript or SQL in a few dozen lines: find the bin,
look up its weight, add up coefficient x weight, then convert.
"""

from __future__ import annotations

import json
import math
from bisect import bisect_right
from pathlib import Path

MISSING = (None, "")


class UnknownCategory(ValueError):
    """The value was never seen in training, so the model has no evidence for it."""


class Scorecard:
    def __init__(self, spec: dict):
        self.spec = spec
        self.features = spec["features"]
        self.models = spec["models"]
        self.scaling = spec["score_scaling"]

    @classmethod
    def load(cls, path: str | Path) -> Scorecard:
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    # -- one feature -------------------------------------------------------------
    def weight_of_evidence(self, feature: str, value) -> float:
        """The training evidence for this value: positive is safer, negative is riskier."""
        spec = self.features[feature]
        if value in MISSING or (isinstance(value, float) and math.isnan(value)):
            return spec["missing_woe"]
        if spec["type"] == "categorical":
            try:
                return spec["categories"][str(value)]
            except KeyError:
                raise UnknownCategory(
                    f"{feature}={value!r} was not seen in training; "
                    f"known values: {sorted(spec['categories'])}"
                ) from None
        return spec["bin_woe"][bisect_right(spec["splits"], float(value))]

    # -- one application ---------------------------------------------------------
    def score(self, application: dict, model: str = "application_only") -> dict:
        """Return the probability of not being repaid, the 300-850 score and the reasons."""
        if model not in self.models:
            raise ValueError(f"Unknown model {model!r}; available: {sorted(self.models)}")
        definition = self.models[model]
        log_odds = definition["intercept"]
        contributions = {}
        for feature, coefficient in definition["coefficients"].items():
            if feature not in application:
                raise KeyError(f"Application is missing required feature: {feature}")
            woe = self.weight_of_evidence(feature, application[feature])
            contribution = coefficient * woe
            contributions[feature] = {"value": application[feature], "woe": woe,
                                      "log_odds_contribution": contribution}
            log_odds += contribution

        probability = 1.0 / (1.0 + math.exp(-log_odds))
        return {
            "model": model,
            "probability_of_default": probability,
            "in_100": round(probability * 100),
            "log_odds": log_odds,
            "credit_score": self.score_from_probability(probability),
            "contributions": contributions,
        }

    def score_from_probability(self, probability: float) -> float:
        """Map a probability onto the 300-850 scale; higher means lower risk."""
        log_odds = math.log(probability / (1.0 - probability))
        scaling = self.scaling
        score = scaling["offset"] - scaling["factor"] * log_odds
        return min(max(score, scaling["min_score"]), scaling["max_score"])


if __name__ == "__main__":
    card = Scorecard.load(Path(__file__).with_name("pd_scorecard.json"))
    example = {
        "term_months": 36, "int_rate": 13.65, "annual_inc": 62000, "dti": 16.05,
        "purpose": "debt_consolidation", "verification_status": "Verified",
        "inq_last_6mths": 1, "total_rev_hi_lim": 22100, "grade": "B",
    }
    for name in card.models:
        out = card.score(example, model=name)
        print(f"{name:18s} PD {out['probability_of_default']:.4%}  "
              f"({out['in_100']} in 100)  score {out['credit_score']:.1f}")
