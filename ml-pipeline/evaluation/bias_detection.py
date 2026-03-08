"""Bias detection using SageMaker Clarify concepts.

Implements Demographic Parity Difference (DPL) and SHAP-based bias
analysis across protected attributes (land_holding_acres segments).

Quality gate: |DPL| < 0.10 for all sensitive segments.
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# Segment definitions (from ML_MODELS.md)
LAND_SEGMENTS = {
    "marginal": (0, 1.0),       # < 1 hectare
    "small": (1.0, 2.0),        # 1-2 hectares
    "medium": (2.0, 10.0),      # 2-10 hectares
    "large": (10.0, float("inf")),
}

BIAS_THRESHOLD = 0.10  # |DPL| < 10%


def compute_demographic_parity(
    predictions: np.ndarray,
    sensitive_attribute: np.ndarray,
    positive_label: int = 0,  # LOW risk = positive / favorable
) -> dict[str, dict[str, float]]:
    """Compute Demographic Parity Difference across groups.

    DPL = P(Ŷ=favorable | group=a) - P(Ŷ=favorable | group=b)
    A model is fair if |DPL| < threshold for all group pairs.
    """
    groups = np.unique(sensitive_attribute)
    base_rate = (predictions == positive_label).mean()

    group_rates: dict[str, float] = {}
    for g in groups:
        mask = sensitive_attribute == g
        if mask.sum() > 0:
            group_rates[str(g)] = float((predictions[mask] == positive_label).mean())
        else:
            group_rates[str(g)] = 0.0

    # DPL between each group and the overall base rate
    dpl_values: dict[str, float] = {}
    for g, rate in group_rates.items():
        dpl_values[g] = round(rate - base_rate, 4)

    return {
        "base_rate": round(float(base_rate), 4),
        "group_rates": group_rates,
        "dpl_values": dpl_values,
        "max_abs_dpl": round(float(max(abs(v) for v in dpl_values.values())), 4),
    }


def compute_equalised_odds(
    predictions: np.ndarray,
    labels: np.ndarray,
    sensitive_attribute: np.ndarray,
) -> dict[str, dict[str, float]]:
    """Compute equalised odds: TPR and FPR per group."""
    groups = np.unique(sensitive_attribute)
    result: dict[str, dict[str, float]] = {}

    for g in groups:
        mask = sensitive_attribute == g
        if mask.sum() == 0:
            continue

        y_true = labels[mask]
        y_pred = predictions[mask]

        for cls in np.unique(labels):
            cls_mask = y_true == cls
            if cls_mask.sum() > 0:
                acc = (y_pred[cls_mask] == cls).mean()
            else:
                acc = 0.0
            result.setdefault(str(g), {})[f"class_{cls}_recall"] = round(float(acc), 4)

    return result


def run_bias_detection(
    predictions: np.ndarray,
    labels: np.ndarray,
    land_acres: np.ndarray,
    output_dir: str,
) -> dict[str, Any]:
    """Full bias detection report.

    Segments farmers by land holding and checks DPL and equalised odds.
    """
    # Create segment labels
    segments = np.array(["unknown"] * len(land_acres), dtype=object)
    for seg_name, (lo, hi) in LAND_SEGMENTS.items():
        mask = (land_acres >= lo) & (land_acres < hi)
        segments[mask] = seg_name

    # DPL analysis
    dp_results = compute_demographic_parity(predictions, segments)

    # Equalised odds
    eo_results = compute_equalised_odds(predictions, labels, segments)

    # Quality gate
    bias_passed = dp_results["max_abs_dpl"] < BIAS_THRESHOLD

    report = {
        "sensitive_attribute": "land_holding_segment",
        "segments": list(LAND_SEGMENTS.keys()),
        "sample_sizes": {
            seg: int((segments == seg).sum()) for seg in LAND_SEGMENTS
        },
        "demographic_parity": dp_results,
        "equalised_odds": eo_results,
        "quality_gate": {
            "threshold": BIAS_THRESHOLD,
            "max_abs_dpl": dp_results["max_abs_dpl"],
            "passed": bias_passed,
        },
    }

    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "bias_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info("Bias detection: max|DPL|=%.4f, Gate=%s",
                dp_results["max_abs_dpl"], "PASSED" if bias_passed else "FAILED")

    return report


def run_shap_fairness_analysis(
    shap_values: np.ndarray,
    feature_names: list[str],
    segments: np.ndarray,
    output_dir: str,
) -> dict[str, Any]:
    """Analyse SHAP value distributions across segments for fairness."""
    report: dict[str, Any] = {"features": {}}

    for i, fname in enumerate(feature_names):
        feature_shap = shap_values[:, i] if shap_values.ndim == 2 else shap_values[:, i, :].mean(axis=1)

        segment_stats: dict[str, dict[str, float]] = {}
        for seg in np.unique(segments):
            mask = segments == seg
            if mask.sum() == 0:
                continue
            vals = feature_shap[mask]
            segment_stats[str(seg)] = {
                "mean_shap": round(float(np.mean(vals)), 6),
                "std_shap": round(float(np.std(vals)), 6),
            }

        report["features"][fname] = segment_stats

    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "shap_fairness.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    return report
