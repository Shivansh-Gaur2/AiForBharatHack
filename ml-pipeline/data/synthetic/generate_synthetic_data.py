"""Synthetic training data generator — rural Indian smallholder farmer profiles.

Calibrated against:
  - ICRISAT VDSA income distributions (log-normal, μ_ln≈10.1, σ_ln≈0.8)
  - NABARD Rural Survey DTI distribution (mean 0.35, 90th pct 0.72)
  - RBI BSR default rates (marginal 12%, small 7%, medium 4%)
  - Indian crop calendar (Kharif Jun–Oct, Rabi Nov–Mar, Zaid Apr–May)

Run directly:   python ml-pipeline/data/synthetic/generate_synthetic_data.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT_DIR = Path(__file__).parent

# ─────────────────────────────────────────────────────────────────────────────
# Indian agricultural seasonal multipliers (12 months Jan–Dec)
# Kharif harvest: Oct–Nov  |  Rabi harvest: Mar–Apr  |  Lean: Jun–Jul
# ─────────────────────────────────────────────────────────────────────────────
INFLOW_SEASONAL  = [0.70, 0.60, 1.30, 1.40, 0.90, 0.55, 0.50, 0.60, 0.80, 1.45, 1.55, 1.10]
OUTFLOW_SEASONAL = [0.90, 0.80, 0.90, 0.80, 1.10, 1.20, 1.20, 1.15, 1.30, 0.90, 0.80, 0.90]


# ─────────────────────────────────────────────────────────────────────────────
# Risk training data (30 k profiles with labels)
# ─────────────────────────────────────────────────────────────────────────────
def generate_risk_data(n: int = 30_000, seed: int = 42) -> pd.DataFrame:
    """Generate tabular risk-scoring training data."""
    rng = np.random.default_rng(seed)

    segments = rng.choice(
        ["marginal", "small", "medium"],
        size=n,
        p=[0.60, 0.30, 0.10],
    )

    # (log_mean_land, log_std_land)
    land_params   = {"marginal": (np.log(1.5), 0.5), "small": (np.log(3.5), 0.6), "medium": (np.log(8.0), 0.7)}
    income_params = {"marginal": (9.8, 0.80),         "small": (10.4, 0.70),       "medium": (11.1, 0.60)}
    irrig_prob    = {"marginal": 0.20,                 "small": 0.40,               "medium": 0.65}
    default_rate  = {"marginal": 0.12,                 "small": 0.07,               "medium": 0.04}

    rows: list[dict] = []
    for i in range(n):
        seg = segments[i]

        land           = float(rng.lognormal(*land_params[seg]))
        annual_income  = float(rng.lognormal(*income_params[seg]))
        has_irrigation = bool(rng.random() < irrig_prob[seg])

        # Income volatility — higher for rainfed
        base_cv = 0.30 if has_irrigation else 0.58
        income_volatility_cv = float(abs(rng.normal(base_cv, 0.14)))
        months_below_avg     = int(rng.integers(0, 5 if has_irrigation else 8))

        # Debt metrics — marginally higher DTI for smaller farms
        dti_base         = {"marginal": 0.42, "small": 0.30, "medium": 0.20}[seg]
        debt_to_income   = float(np.clip(rng.lognormal(math.log(dti_base + 0.01), 0.50), 0.0, 2.5))
        active_loans     = int(rng.integers(1, 5 if seg == "marginal" else 4))
        credit_util      = float(np.clip(rng.beta(2, 3), 0.02, 0.99))
        total_outstanding = annual_income * debt_to_income * float(rng.uniform(0.5, 1.5))

        # Repayment history
        has_defaults  = bool(rng.random() < default_rate[seg])
        on_time_ratio = float(rng.uniform(0.30, 0.75) if has_defaults else rng.uniform(0.75, 1.0))

        # Seasonal / external
        seasonal_var  = float(rng.uniform(10, 45) if has_irrigation else rng.uniform(25, 80))
        weather_risk  = float(rng.uniform(10, 70))
        market_risk   = float(rng.uniform(10, 60))

        # Crop diversification — marginal = mostly monoculture
        crop_div_alpha = {"marginal": 1.5, "small": 3.0, "medium": 5.0}[seg]
        crop_div_beta  = {"marginal": 4.0, "small": 3.0, "medium": 2.0}[seg]
        crop_div       = float(rng.beta(crop_div_alpha, crop_div_beta))

        # Demographics
        dependents = int(rng.integers(1, 7))
        age        = int(rng.integers(22, 65))

        # ── Synthetic label (domain-rule score + noise) ──────────────────────
        score = 0.0
        score += min(20, income_volatility_cv * 25)
        if debt_to_income > 0.8:  score += 25
        elif debt_to_income > 0.5: score += 15
        elif debt_to_income > 0.3: score += 7
        score += 20 if has_defaults else (1 - on_time_ratio) * 15
        score += min(10, weather_risk / 7)
        score += min(7,  market_risk  / 9)
        score += min(8,  seasonal_var / 9)
        score += 5 if not has_irrigation else 0
        score += 5 if crop_div < 0.2 else 0
        score += 5 if active_loans >= 3 else 0
        score += float(rng.normal(0, 4))          # label noise

        if score < 20:   risk_category = 0   # LOW
        elif score < 40: risk_category = 1   # MEDIUM
        elif score < 60: risk_category = 2   # HIGH
        else:            risk_category = 3   # VERY_HIGH

        rows.append({
            "income_volatility_cv":       income_volatility_cv,
            "annual_income":              annual_income,
            "months_below_average":       months_below_avg,
            "debt_to_income_ratio":       debt_to_income,
            "total_outstanding":          total_outstanding,
            "active_loan_count":          active_loans,
            "credit_utilisation":         credit_util,
            "on_time_repayment_ratio":    on_time_ratio,
            "has_defaults":               int(has_defaults),
            "seasonal_variance":          seasonal_var,
            "crop_diversification_index": crop_div,
            "weather_risk_score":         weather_risk,
            "market_risk_score":          market_risk,
            "dependents":                 dependents,
            "age":                        age,
            "has_irrigation":             int(has_irrigation),
            "land_holding_acres":         land,
            "soil_quality_score":         float(rng.uniform(30, 90)),
            "risk_category":              risk_category,
        })

    df = pd.DataFrame(rows)
    path = OUTPUT_DIR / "risk_training_data.csv"
    df.to_csv(path, index=False)
    print(f"[risk]  {len(df):,} rows → {path}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Cash-flow training data (1 k profiles × 36 months)
# ─────────────────────────────────────────────────────────────────────────────
def generate_cashflow_data(n_profiles: int = 1_000, seed: int = 42) -> pd.DataFrame:
    """Generate monthly inflow/outflow time-series for population-level model."""
    rng = np.random.default_rng(seed)
    rows: list[dict] = []

    for pid in range(n_profiles):
        base_monthly_income  = float(rng.lognormal(10.1, 0.70))   # ~24 k/month median
        base_monthly_expense = base_monthly_income * float(rng.uniform(0.40, 0.75))
        has_irrigation       = bool(rng.random() < 0.35)

        for year_offset in range(3):
            year = 2023 + year_offset
            for month in range(1, 13):
                seasonal_mul = INFLOW_SEASONAL[month - 1]
                # Rainfed farms have wider seasonal spread
                noise_range = 0.08 if has_irrigation else 0.18
                inflow  = base_monthly_income  * seasonal_mul * float(rng.uniform(1 - noise_range, 1 + noise_range))
                outflow = base_monthly_expense * OUTFLOW_SEASONAL[month - 1] * float(rng.uniform(0.90, 1.10))

                rows.append({
                    "profile_id":   pid,
                    "year":         year,
                    "month":        month,
                    "inflow":       max(0.0, inflow),
                    "outflow":      max(0.0, outflow),
                    "net":          inflow - outflow,
                    "has_irrigation": int(has_irrigation),
                    "month_sin":    float(np.sin(2 * np.pi * month / 12)),
                    "month_cos":    float(np.cos(2 * np.pi * month / 12)),
                    "is_kharif":    int(month in (6, 7, 8, 9, 10)),
                    "is_rabi":      int(month in (11, 12, 1, 2, 3)),
                    "is_zaid":      int(month in (4, 5)),
                })

    df = pd.DataFrame(rows)
    path = OUTPUT_DIR / "cashflow_training_data.csv"
    df.to_csv(path, index=False)
    print(f"[cashflow]  {len(df):,} rows → {path}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Early-warning training data (30 k profiles with severity labels)
# ─────────────────────────────────────────────────────────────────────────────
def generate_early_warning_data(n: int = 30_000, seed: int = 123) -> pd.DataFrame:
    """Generate tabular early-warning features + severity labels (0/1/2)."""
    rng = np.random.default_rng(seed)

    # Class distribution: 70% OK, 20% WARNING, 10% CRITICAL
    outcomes = rng.choice([0, 1, 2], size=n, p=[0.70, 0.20, 0.10])

    rows: list[dict] = []
    for outcome in outcomes:
        if outcome == 0:          # OK — normal operation
            income_dev_3m   = float(rng.normal(0, 10))
            income_dev_6m   = float(rng.normal(0, 12))
            missed          = int(rng.integers(0, 2))
            dti             = float(rng.uniform(0.10, 0.50))
            days_overdue    = float(rng.uniform(0, 15))
            dti_delta       = float(rng.normal(0, 0.03))
            surplus_slope   = float(rng.uniform(-100, 500))
        elif outcome == 1:        # WARNING — early stress
            income_dev_3m   = float(rng.uniform(-35, -10))
            income_dev_6m   = float(rng.uniform(-30,  -5))
            missed          = int(rng.integers(1, 4))
            dti             = float(rng.uniform(0.40, 0.75))
            days_overdue    = float(rng.uniform(10, 45))
            dti_delta       = float(rng.uniform(0.03, 0.12))
            surplus_slope   = float(rng.uniform(-500, -50))
        else:                     # CRITICAL — severe financial distress
            income_dev_3m   = float(rng.uniform(-60, -30))
            income_dev_6m   = float(rng.uniform(-50, -25))
            missed          = int(rng.integers(3, 8))
            dti             = float(rng.uniform(0.65, 1.50))
            days_overdue    = float(rng.uniform(30, 120))
            dti_delta       = float(rng.uniform(0.10, 0.35))
            surplus_slope   = float(rng.uniform(-2_000, -300))

        rows.append({
            "income_deviation_3m":    income_dev_3m,
            "income_deviation_6m":    income_dev_6m,
            "missed_payments_ytd":    missed,
            "days_overdue_avg":       days_overdue,
            "dti_ratio":              dti,
            "dti_delta_3m":           dti_delta,
            "surplus_trend_slope":    surplus_slope,
            "weather_shock_score":    float(rng.uniform(0, 80)),
            "market_price_shock":     float(rng.normal(0, 20)),
            "seasonal_stress_flag":   int(rng.random() < 0.30),
            "risk_category_current":  int(rng.integers(0, 4)),
            "days_since_last_alert":  int(rng.integers(0, 365)),
            "severity":               outcome,
        })

    df = pd.DataFrame(rows)
    path = OUTPUT_DIR / "early_warning_training_data.csv"
    df.to_csv(path, index=False)
    print(f"[early_warning]  {len(df):,} rows → {path}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    print("Generating synthetic training datasets…\n")
    generate_risk_data()
    generate_cashflow_data()
    generate_early_warning_data()
    print("\nDone.")


if __name__ == "__main__":
    main()
