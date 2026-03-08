"""Monte Carlo scenario simulation engine.

Uses log-normal income distributions fitted per farmer segment
(from ml-pipeline/saved_models/scenario_dist_params.json) to produce
probabilistic income trajectories under stress scenarios.

No gradient training — pure parametric Monte Carlo.

The service uses this when: os.getenv("SCENARIO_ML_ENABLED", "false") == "true"

Returns None on model unavailability → caller falls back to heuristic simulate_scenario().
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).parents[3] / "ml-pipeline" / "saved_models"

_dist_params:   dict | None = None
_seasonal_muls: list[float] | None = None

# Fallback defaults (calibrated from ICRISAT data)
_DEFAULT_DIST_PARAMS = {
    "marginal": {"mu_ln": 9.80,  "sigma_ln": 0.80},
    "small":    {"mu_ln": 10.40, "sigma_ln": 0.70},
    "medium":   {"mu_ln": 11.10, "sigma_ln": 0.60},
}
_DEFAULT_SEASONAL = [0.70, 0.60, 1.30, 1.40, 0.90, 0.55, 0.50, 0.60, 0.80, 1.45, 1.55, 1.10]


def _ensure_loaded() -> bool:
    global _dist_params, _seasonal_muls

    if _dist_params is not None:
        return True

    params_path   = _MODEL_DIR / "scenario_dist_params.json"
    seasonal_path = _MODEL_DIR / "scenario_seasonal.json"

    if params_path.exists():
        with open(params_path) as f:
            _dist_params = json.load(f)
        logger.info("Scenario distribution params loaded from %s", params_path)
    else:
        logger.warning("scenario_dist_params.json not found — using hardcoded defaults")
        _dist_params = _DEFAULT_DIST_PARAMS

    if seasonal_path.exists():
        with open(seasonal_path) as f:
            data = json.load(f)
        _seasonal_muls = data.get("monthly_inflow_multipliers", _DEFAULT_SEASONAL)
    else:
        _seasonal_muls = _DEFAULT_SEASONAL

    return True


def is_available() -> bool:
    return _ensure_loaded()


def simulate(
    annual_income: float,
    land_holding_acres: float,
    weather_adjustment: float,
    market_price_change_pct: float,
    income_reduction_pct: float,
    duration_months: int,
    monthly_obligations: float,
    household_expense: float,
    start_month: int = 1,
    n_simulations: int = 1_000,
    seed: int | None = None,
) -> dict | None:
    """Run a Monte Carlo scenario simulation.

    Parameters
    ----------
    annual_income            : borrower's baseline annual income (INR)
    land_holding_acres       : used to determine farmer segment
    weather_adjustment       : income multiplier for weather shock (0.3 = severe drought)
    market_price_change_pct  : percentage change in crop prices (-30 = 30% price drop)
    income_reduction_pct     : additional income reduction percentage (0–100)
    duration_months          : how many months the shock lasts (max 12)
    monthly_obligations      : total monthly EMI obligations (INR)
    household_expense        : monthly household expenditure (INR)
    start_month              : month the shock begins (1–12)
    n_simulations            : number of Monte Carlo draws
    seed                     : random seed for reproducibility

    Returns
    -------
    dict | None
        {
          "income_p10_monthly":          list[float]  (12 values),
          "income_p50_monthly":          list[float],
          "income_p90_monthly":          list[float],
          "months_in_deficit_p50":       int,
          "months_in_deficit_p90":       int,
          "repayment_stress_ratio":      float  (monthly obligations / p10 monthly income),
          "recommended_emi_reduction_pct": int,
          "p10_annual_income_stressed":  float,
          "p50_annual_income_stressed":  float,
          "shock_factor":                float,
          "simulation_runs":             int,
          "model_version":               str,
        }
    """
    _ensure_loaded()

    try:
        rng = np.random.default_rng(seed)

        # ── Determine farmer segment ──────────────────────────────────────────
        if land_holding_acres < 2.0:
            seg = "marginal"
        elif land_holding_acres < 5.0:
            seg = "small"
        else:
            seg = "medium"

        params = _dist_params.get(seg, _DEFAULT_DIST_PARAMS["small"])  # type: ignore[union-attr]

        # Use the borrower's actual income to personalise the mean
        # while keeping population σ for distributional spread
        profile_mu_ln = math.log(max(annual_income, 1.0))
        sigma_ln      = float(params["sigma_ln"])

        # ── Draw annual income samples ────────────────────────────────────────
        sim_annual = rng.lognormal(profile_mu_ln, sigma_ln, n_simulations)

        # ── Compute composite shock factor ────────────────────────────────────
        shock_factor = (
            weather_adjustment
            * (1.0 + market_price_change_pct / 100.0)
            * (1.0 - income_reduction_pct     / 100.0)
        )
        shock_factor = float(np.clip(shock_factor, 0.05, 2.0))

        # ── Build monthly income matrix  (n_simulations × 12) ────────────────
        seasonal = np.array(_seasonal_muls)                  # shape (12,)
        avg_monthly = sim_annual / 12                        # shape (n,)
        monthly_mat = np.outer(avg_monthly, seasonal)        # shape (n, 12)

        # Apply shock to affected months
        n_affected = min(max(int(duration_months), 0), 12)
        m0 = (start_month - 1) % 12
        for i in range(n_affected):
            mi = (m0 + i) % 12
            monthly_mat[:, mi] *= shock_factor

        # Per-draw noise
        noise = rng.uniform(0.85, 1.15, (n_simulations, 12))
        monthly_mat = np.maximum(monthly_mat * noise, 0.0)

        # ── Monthly outflow (fixed deterministic overhead) ────────────────────
        total_outflow = monthly_obligations + household_expense
        net_cashflow  = monthly_mat - total_outflow          # shape (n, 12)

        # ── Statistics ───────────────────────────────────────────────────────
        p10_monthly = np.percentile(monthly_mat, 10, axis=0).tolist()
        p50_monthly = np.percentile(monthly_mat, 50, axis=0).tolist()
        p90_monthly = np.percentile(monthly_mat, 90, axis=0).tolist()

        deficit_months = np.sum(net_cashflow < 0, axis=1)  # (n,)

        stressed_annual        = sim_annual * shock_factor
        p10_annual_stressed    = float(np.percentile(stressed_annual, 10))
        p50_annual_stressed    = float(np.percentile(stressed_annual, 50))

        p10_monthly_income_avg = p10_annual_stressed / 12.0
        repayment_stress_ratio = (
            monthly_obligations / max(p10_monthly_income_avg, 1.0)
        )

        # Recommend EMI reduction if stress ratio exceeds 40%
        if repayment_stress_ratio > 0.50:
            emi_reduction_pct = int(min(50, (repayment_stress_ratio - 0.40) * 100))
        else:
            emi_reduction_pct = 0

        return {
            "income_p10_monthly":           [round(v, 2) for v in p10_monthly],
            "income_p50_monthly":           [round(v, 2) for v in p50_monthly],
            "income_p90_monthly":           [round(v, 2) for v in p90_monthly],
            "months_in_deficit_p50":        int(np.percentile(deficit_months, 50)),
            "months_in_deficit_p90":        int(np.percentile(deficit_months, 90)),
            "repayment_stress_ratio":       round(float(repayment_stress_ratio), 4),
            "recommended_emi_reduction_pct": emi_reduction_pct,
            "p10_annual_income_stressed":   round(p10_annual_stressed, 2),
            "p50_annual_income_stressed":   round(p50_annual_stressed, 2),
            "shock_factor":                 round(shock_factor, 4),
            "simulation_runs":              n_simulations,
            "model_version":                "monte-carlo-v1",
        }

    except Exception as exc:
        logger.error("Scenario MC simulation failed: %s", exc)
        return None
