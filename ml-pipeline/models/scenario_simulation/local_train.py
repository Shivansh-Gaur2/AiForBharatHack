"""Fit income-distribution parameters for Monte Carlo scenario simulation.

No gradient-based training — this script fits log-normal (μ, σ) parameters
per farmer segment from synthetic data so the Monte Carlo engine can draw
realistic income samples.

Usage:
    python ml-pipeline/models/scenario_simulation/local_train.py

Outputs saved to ml-pipeline/saved_models/:
    scenario_dist_params.json   — {segment: {mu_ln, sigma_ln, n_samples}}
    scenario_seasonal.json      — 12-month seasonal inflow multipliers
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from scipy import stats

DATA_DIR     = ROOT / "ml-pipeline" / "data"  / "synthetic"
SAVED_MODELS = ROOT / "ml-pipeline" / "saved_models"
SAVED_MODELS.mkdir(parents=True, exist_ok=True)

# Seasonal multipliers (Jan–Dec) calibrated to Indian crop calendar
SEASONAL_MULTIPLIERS = [0.70, 0.60, 1.30, 1.40, 0.90, 0.55, 0.50, 0.60, 0.80, 1.45, 1.55, 1.10]


def fit() -> None:
    data_path = DATA_DIR / "risk_training_data.csv"
    if not data_path.exists():
        print(f"Training data not found at {data_path}")
        print("Run: python ml-pipeline/data/synthetic/generate_synthetic_data.py")
        sys.exit(1)

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df):,} profiles for distribution fitting.\n")

    # Segment by land holding (same bins used in MC engine)
    segments = {
        "marginal": df[df["land_holding_acres"] <  2.0],
        "small":    df[(df["land_holding_acres"] >= 2.0) & (df["land_holding_acres"] < 5.0)],
        "medium":   df[df["land_holding_acres"] >= 5.0],
    }

    dist_params: dict[str, dict] = {}
    for seg, sub in segments.items():
        income = sub["annual_income"].values
        income = income[income > 0]

        # Fit log-normal via MLE
        ln_income = np.log(income)
        mu_ln     = float(np.mean(ln_income))
        sigma_ln  = float(np.std(ln_income))

        # Goodness-of-fit (KS test against fitted log-normal)
        ks_stat, ks_p = stats.kstest(income, "lognorm", args=(sigma_ln, 0, np.exp(mu_ln)))

        dist_params[seg] = {
            "mu_ln":    round(mu_ln,    4),
            "sigma_ln": round(sigma_ln, 4),
            "n_samples": int(len(income)),
            "median_annual_income_inr": round(float(np.median(income)), 0),
            "ks_statistic": round(float(ks_stat), 4),
            "ks_p_value":   round(float(ks_p),    4),
        }
        print(
            f"  [{seg:<10}] n={len(income):,}  μ_ln={mu_ln:.3f}  σ_ln={sigma_ln:.3f}"
            f"  median=₹{np.median(income):,.0f}  KS p={ks_p:.3f}"
        )

    # Save distribution params
    params_path = SAVED_MODELS / "scenario_dist_params.json"
    with open(params_path, "w") as f:
        json.dump(dist_params, f, indent=2)
    print(f"\nSaved {params_path}")

    # Save seasonal multipliers
    seasonal_path = SAVED_MODELS / "scenario_seasonal.json"
    with open(seasonal_path, "w") as f:
        json.dump({"monthly_inflow_multipliers": SEASONAL_MULTIPLIERS}, f, indent=2)
    print(f"Saved {seasonal_path}")


if __name__ == "__main__":
    fit()
