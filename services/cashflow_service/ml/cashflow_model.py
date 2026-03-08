"""Service-side ML wrapper for cash-flow prediction.

Loads the Ridge seasonal models from ml-pipeline/saved_models/ and provides
predict_monthly() which produces (inflow, outflow) estimates for a given
month with optional profile-level personalisation.

The service uses this when: os.getenv("CASHFLOW_ML_ENABLED", "false") == "true"

If unavailable or failing, returns None → caller falls back to the existing
`generate_projections()` heuristic.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import joblib
import numpy as np

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).parents[3] / "ml-pipeline" / "saved_models"

_model_inflow  = None
_model_outflow = None


def _ensure_loaded() -> bool:
    global _model_inflow, _model_outflow
    if _model_inflow is not None:
        return True

    in_path  = _MODEL_DIR / "cashflow_inflow_model.joblib"
    out_path = _MODEL_DIR / "cashflow_outflow_model.joblib"

    if not in_path.exists() or not out_path.exists():
        logger.warning("Cashflow ML models not found at %s — falling back to heuristic", _MODEL_DIR)
        return False

    try:
        _model_inflow  = joblib.load(in_path)
        _model_outflow = joblib.load(out_path)
        logger.info("Cashflow ML models loaded (Ridge-seasonal) from %s", _MODEL_DIR)
        return True
    except Exception as exc:
        logger.error("Failed to load cashflow models: %s", exc)
        return False


def is_available() -> bool:
    return _ensure_loaded()


def _make_feature_vector(month: int, has_irrigation: bool) -> np.ndarray:
    """Build [month_sin, month_cos, is_kharif, is_rabi, is_zaid, has_irrigation]."""
    return np.array([[
        math.sin(2 * math.pi * month / 12),
        math.cos(2 * math.pi * month / 12),
        int(month in (6, 7, 8, 9, 10)),   # Kharif
        int(month in (11, 12, 1, 2, 3)),   # Rabi
        int(month in (4, 5)),              # Zaid
        int(has_irrigation),
    ]], dtype=np.float32)


def predict_monthly(
    month: int,
    year: int,
    has_irrigation: bool,
    weather_adjustment: float = 1.0,
    market_adjustment: float = 1.0,
    profile_avg_inflow: float | None = None,
    profile_avg_outflow: float | None = None,
) -> dict | None:
    """Return ML-predicted inflow/outflow for one calendar month.

    Blending strategy
    -----------------
    When profile_avg_inflow is provided the model is used to compute a
    seasonal *ratio* relative to a neutral reference month, which is then
    applied to the profile's own known average — keeping the correct scale
    while improving the seasonal shape from population data.

    Parameters
    ----------
    month               : calendar month 1–12
    year                : calendar year
    has_irrigation      : irrigation flag
    weather_adjustment  : multiplier applied to inflow  (<1 = drought)
    market_adjustment   : multiplier applied to inflow  (<1 = price drop)
    profile_avg_inflow  : borrower's historical average monthly inflow (INR)
    profile_avg_outflow : borrower's historical average monthly outflow (INR)

    Returns
    -------
    dict | None  with keys predicted_inflow, predicted_outflow, model_version
    """
    if not _ensure_loaded():
        return None

    try:
        fv = _make_feature_vector(month, has_irrigation)

        raw_inflow  = float(_model_inflow.predict(fv)[0])
        raw_outflow = float(_model_outflow.predict(fv)[0])

        # "neutral" month reference: month=12 (cos≈1, sin≈0, Rabi=1)
        neutral_fv        = _make_feature_vector(12, has_irrigation)
        pop_neutral_in    = float(_model_inflow.predict(neutral_fv)[0])
        pop_neutral_out   = float(_model_outflow.predict(neutral_fv)[0])

        if profile_avg_inflow and profile_avg_inflow > 0 and pop_neutral_in > 0:
            # Apply population seasonal ratio to profile-level average
            pred_inflow = profile_avg_inflow * (raw_inflow / pop_neutral_in)
        else:
            pred_inflow = raw_inflow

        if profile_avg_outflow and profile_avg_outflow > 0 and pop_neutral_out > 0:
            pred_outflow = profile_avg_outflow * (raw_outflow / pop_neutral_out)
        else:
            pred_outflow = raw_outflow

        # External adjustments (weather and market)
        pred_inflow *= weather_adjustment * market_adjustment

        return {
            "month":             month,
            "year":              year,
            "predicted_inflow":  max(0.0, round(pred_inflow, 2)),
            "predicted_outflow": max(0.0, round(pred_outflow, 2)),
            "model_version":     "ridge-seasonal-v1",
        }

    except Exception as exc:
        logger.error("Cashflow ML prediction failed for month=%s: %s", month, exc)
        return None


def predict_horizon(
    start_month: int,
    start_year: int,
    horizon_months: int,
    has_irrigation: bool,
    weather_adjustment: float = 1.0,
    market_adjustment: float = 1.0,
    profile_avg_inflow: float | None = None,
    profile_avg_outflow: float | None = None,
) -> list[dict] | None:
    """Predict a full horizon of monthly cash flows.

    Returns a list of dicts (same order as the horizon), or None if unavailable.
    """
    if not _ensure_loaded():
        return None

    results = []
    for i in range(horizon_months):
        m = ((start_month - 1 + i) % 12) + 1
        y = start_year + (start_month - 1 + i) // 12
        pred = predict_monthly(
            m, y, has_irrigation,
            weather_adjustment, market_adjustment,
            profile_avg_inflow, profile_avg_outflow,
        )
        if pred is None:
            return None
        results.append(pred)

    return results
