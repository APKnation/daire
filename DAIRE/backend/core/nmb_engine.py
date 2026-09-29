"""
NMB Credit Scorecard Engine for DAIRE Central System.

Integrates the frozen NMB credit models (Weight of Evidence / WoE and Logistic
Scorecard calibrated on the 300-850 bureau scale).
"""

from __future__ import annotations

import json
import math
import os
from bisect import bisect_right
from pathlib import Path
from typing import Any

from django.conf import settings

MISSING = (None, "")
NMB_SCORECARD_FILENAME = "pd_scorecard.json"
NMB_BUNDLE_PATH = Path("/data/APKnation/credit/nmb_credit_models_cd528d26c27b/portable/pd_scorecard.json")

_scorecard_cache: dict[str, Any] = {"card": None, "failed": False}


class NMBScorecard:
    def __init__(self, spec: dict):
        self.spec = spec
        self.version = spec.get("model_version", "nmb-scorecard-v1")
        self.features = spec["features"]
        self.models = spec["models"]
        self.scaling = spec["score_scaling"]

    @classmethod
    def load(cls, path: str | Path) -> NMBScorecard:
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def weight_of_evidence(self, feature: str, value: Any) -> float:
        """Training evidence: positive is safer, negative is riskier."""
        spec = self.features.get(feature)
        if not spec:
            return 0.0
        if value in MISSING or (isinstance(value, float) and math.isnan(value)):
            return float(spec.get("missing_woe", 0.0))
        if spec["type"] == "categorical":
            str_val = str(value).strip()
            cats = spec.get("categories", {})
            if str_val in cats:
                return float(cats[str_val])
            # Case-insensitive or fallback
            for cat_key, cat_val in cats.items():
                if cat_key.lower() == str_val.lower():
                    return float(cat_val)
            if "other" in cats:
                return float(cats["other"])
            return float(spec.get("missing_woe", 0.0))
        try:
            num_val = float(value)
            idx = bisect_right(spec["splits"], num_val)
            return float(spec["bin_woe"][idx])
        except (ValueError, TypeError, IndexError):
            return float(spec.get("missing_woe", 0.0))

    def score(self, application: dict[str, Any], model: str = "application_only") -> dict[str, Any]:
        """Return the probability of default, the 300-850 score, and reason codes."""
        if model not in self.models:
            model = "application_only"
        definition = self.models[model]
        log_odds = definition["intercept"]
        contributions: dict[str, dict[str, Any]] = {}
        strengths: list[dict[str, Any]] = []
        risk_factors: list[dict[str, Any]] = []

        for feature, coefficient in definition["coefficients"].items():
            val = application.get(feature)
            woe = self.weight_of_evidence(feature, val)
            contribution = coefficient * woe
            # In WoE, positive woe is safer. When coefficient is negative:
            # log_odds contribution < 0 reduces default probability (safer).
            factor_info = {
                "feature": feature,
                "value": val,
                "woe": round(woe, 4),
                "log_odds_contribution": round(contribution, 4),
                "is_positive": woe > 0.05,
                "is_risk": woe < -0.05,
            }
            contributions[feature] = factor_info
            if woe > 0.05:
                strengths.append(factor_info)
            elif woe < -0.05:
                risk_factors.append(factor_info)

            log_odds += contribution

        # Sort strengths by positive safety effect and risks by severity
        strengths.sort(key=lambda x: x["woe"], reverse=True)
        risk_factors.sort(key=lambda x: x["woe"])

        probability = 1.0 / (1.0 + math.exp(-log_odds))
        credit_score = self.score_from_probability(probability)

        return {
            "model": model,
            "version": self.version,
            "probability_of_default": round(probability, 4),
            "in_100": round(probability * 100),
            "log_odds": round(log_odds, 4),
            "credit_score": round(credit_score, 1),
            "contributions": contributions,
            "top_strengths": strengths[:3],
            "top_risk_factors": risk_factors[:3],
        }

    def score_from_probability(self, probability: float) -> float:
        """Map a probability onto the 300-850 bureau scale; higher means lower risk."""
        clamped_prob = min(max(probability, 0.0001), 0.9999)
        log_odds = math.log(clamped_prob / (1.0 - clamped_prob))
        scaling = self.scaling
        score = scaling["offset"] - scaling["factor"] * log_odds
        return min(max(score, scaling["min_score"]), scaling["max_score"])


def get_nmb_scorecard() -> NMBScorecard | None:
    """Load the NMB scorecard from backend or bundle root, caching the instance."""
    if _scorecard_cache["card"] is not None:
        return _scorecard_cache["card"]
    if _scorecard_cache["failed"]:
        return None

    base_dir = str(settings.BASE_DIR) if getattr(settings, "configured", False) and hasattr(settings, "BASE_DIR") else ""
    paths_to_try = [
        os.path.join(base_dir, NMB_SCORECARD_FILENAME) if base_dir else "",
        str(NMB_BUNDLE_PATH),
        os.path.join(os.path.dirname(__file__), "..", NMB_SCORECARD_FILENAME),
    ]

    for p in paths_to_try:
        if p and os.path.exists(p):
            try:
                card = NMBScorecard.load(p)
                _scorecard_cache["card"] = card
                return card
            except Exception:
                continue

    _scorecard_cache["failed"] = True
    return None
