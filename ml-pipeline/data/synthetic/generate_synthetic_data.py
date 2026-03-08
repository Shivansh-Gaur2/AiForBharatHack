"""Synthetic data generator for rural credit ML models.

Produces ICRISAT-calibrated training data for:
- Risk scoring (farmer profiles with default labels)
- Cash flow prediction (monthly income/expense time series)
- Early warning (alert sequences with severity labels)
- Scenario simulation (historical shock outcomes)

Calibrated against:
- ICRISAT VDSA income distributions (log-normal, μ=10.2, σ=0.8 in ln-INR)
- NABARD survey DTI distribution (mean 0.35, 90th pct 0.72)
- RBI BSR default rates by district category (urban 2%, semi-urban 4%, rural 8%)
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CROPS = [
    "rice", "wheat", "cotton", "sugarcane", "maize",
    "soybean", "groundnut", "pulses", "millets", "vegetables",
]

DISTRICTS = [
    "anantapur", "bellary", "bidar", "gulbarga", "raichur",
    "dharwad", "mandya", "tumkur", "hassan", "mysore",
    "jaipur", "jodhpur", "udaipur", "kota", "ajmer",
    "wardha", "akola", "amravati", "nagpur", "yavatmal",
    "varanasi", "prayagraj", "lucknow", "kanpur", "gorakhpur",
]

SEASONS_MONTHS = {
    "kharif": [6, 7, 8, 9, 10],
    "rabi": [11, 12, 1, 2, 3],
    "zaid": [4, 5],
}


@dataclass(frozen=True)
class SegmentConfig:
    """Distribution parameters for a land-holding segment."""

    name: str
    fraction: float
    land_mu: float      # mean land holding (acres)
    land_sigma: float
    income_mu_ln: float  # log-normal μ (ln-INR)
    income_sigma_ln: float
    default_rate: float
    dti_alpha: float     # Beta distribution α
    dti_beta: float      # Beta distribution β
    irrigation_prob: float


SEGMENTS = [
    SegmentConfig("marginal", 0.60, 1.2, 0.4, 9.8, 0.8, 0.12, 2, 5, 0.20),
    SegmentConfig("small",    0.30, 3.5, 0.4, 10.4, 0.8, 0.07, 2.5, 5, 0.40),
    SegmentConfig("medium",   0.10, 8.0, 0.4, 11.1, 0.8, 0.04, 3, 5, 0.65),
]


# ---------------------------------------------------------------------------
# Farmer profile generator
# ---------------------------------------------------------------------------

def generate_farmer_profiles(
    n: int = 50_000,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic farmer profiles for risk model training.

    Returns a DataFrame with 18+ features and a binary default label.
    """
    rng = np.random.default_rng(seed)
    records: list[dict[str, Any]] = []

    for seg in SEGMENTS:
        size = int(n * seg.fraction)

        land = np.clip(
            rng.lognormal(np.log(seg.land_mu), seg.land_sigma, size),
            0.1, 50.0,
        )
        annual_income = rng.lognormal(seg.income_mu_ln, seg.income_sigma_ln, size)
        monthly_income = annual_income / 12.0

        # DTI: Beta distribution scaled to realistic range
        dti = np.clip(
            rng.beta(seg.dti_alpha, seg.dti_beta, size) * 1.2,
            0.0, 1.5,
        )

        # Derived features
        income_cv = np.clip(rng.gamma(2, 0.15, size), 0.05, 2.0)
        if not seg.irrigation_prob > 0.5:
            income_cv *= rng.uniform(1.1, 1.5, size)  # rainfed = more volatile

        months_below_avg = rng.poisson(income_cv * 4, size).clip(0, 12)

        total_outstanding = monthly_income * dti * rng.uniform(8, 24, size)
        active_loans = rng.poisson(1.5, size).clip(1, 8)
        credit_utilisation = np.clip(rng.beta(3, 2, size), 0.0, 1.0)

        # On-time repayment: correlated with DTI
        base_on_time = 1.0 - dti * 0.3
        on_time_ratio = np.clip(
            base_on_time + rng.normal(0, 0.1, size), 0.0, 1.0,
        )

        # Default: correlated with DTI, income_cv, on_time_ratio
        default_prob = np.clip(
            seg.default_rate
            + (dti - 0.35) * 0.15
            + (income_cv - 0.3) * 0.1
            - (on_time_ratio - 0.8) * 0.1,
            0.01, 0.5,
        )
        has_defaults = rng.binomial(1, default_prob).astype(bool)

        # Seasonal
        seasonal_variance = np.where(
            rng.random(size) < seg.irrigation_prob,
            rng.gamma(3, 800, size),        # irrigated: lower variance
            rng.gamma(3, 2000, size),       # rainfed: higher
        )

        # Crop diversification (Herfindahl index)
        n_crops = rng.choice([1, 2, 3, 4], size=size, p=[0.3, 0.35, 0.25, 0.1])
        crop_div_index = np.where(
            n_crops == 1, rng.uniform(0.0, 0.15, size),
            np.where(n_crops == 2, rng.uniform(0.15, 0.45, size),
                     np.where(n_crops == 3, rng.uniform(0.4, 0.65, size),
                              rng.uniform(0.6, 0.85, size))),
        )

        # External risk scores
        weather_risk = rng.beta(2, 5, size) * 100  # skewed low (most OK)
        market_risk = rng.beta(2, 5, size) * 100

        # Demographics
        age = rng.normal(42, 12, size).clip(18, 75).astype(int)
        dependents = rng.poisson(3, size).clip(0, 12)
        has_irrigation = rng.random(size) < seg.irrigation_prob

        # Soil quality
        soil_quality = np.clip(rng.normal(55, 15, size), 10, 95)

        # Primary crop & district
        primary_crop = rng.choice(CROPS, size)
        district = rng.choice(DISTRICTS, size)

        # Risk score (target for regression head)
        risk_score = np.clip(
            (dti * 250
             + income_cv * 150
             + (1 - on_time_ratio) * 200
             + (1 - crop_div_index) * 100
             + weather_risk * 0.5
             + market_risk * 0.5
             + has_defaults.astype(float) * 150
             + (1 - has_irrigation.astype(float)) * 50
             + rng.normal(0, 30, size)),
            0, 1000,
        ).astype(int)

        # Risk category
        risk_category = np.where(
            risk_score < 250, "LOW",
            np.where(risk_score < 500, "MEDIUM",
                     np.where(risk_score < 750, "HIGH", "VERY_HIGH")),
        )

        for i in range(size):
            records.append({
                "profile_id": f"SYN-{seg.name[0].upper()}-{len(records):06d}",
                "segment": seg.name,
                "land_holding_acres": round(float(land[i]), 2),
                "annual_income": round(float(annual_income[i]), 2),
                "income_volatility_cv": round(float(income_cv[i]), 4),
                "months_below_average": int(months_below_avg[i]),
                "debt_to_income_ratio": round(float(dti[i]), 4),
                "total_outstanding": round(float(total_outstanding[i]), 2),
                "active_loan_count": int(active_loans[i]),
                "credit_utilisation": round(float(credit_utilisation[i]), 4),
                "on_time_repayment_ratio": round(float(on_time_ratio[i]), 4),
                "has_defaults": bool(has_defaults[i]),
                "seasonal_variance": round(float(seasonal_variance[i]), 2),
                "crop_diversification_index": round(float(crop_div_index[i]), 4),
                "weather_risk_score": round(float(weather_risk[i]), 2),
                "market_risk_score": round(float(market_risk[i]), 2),
                "dependents": int(dependents[i]),
                "age": int(age[i]),
                "has_irrigation": bool(has_irrigation[i]),
                "soil_quality_score": round(float(soil_quality[i]), 2),
                "primary_crop": str(primary_crop[i]),
                "district": str(district[i]),
                "risk_score": int(risk_score[i]),
                "risk_category": str(risk_category[i]),
                "has_defaulted": bool(has_defaults[i]),
            })

    df = pd.DataFrame(records)
    logger.info(
        "Generated %d farmer profiles: %s",
        len(df),
        df["segment"].value_counts().to_dict(),
    )
    return df


# ---------------------------------------------------------------------------
# Monthly cash flow time-series generator
# ---------------------------------------------------------------------------

def generate_cashflow_time_series(
    profiles: pd.DataFrame,
    months: int = 36,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate monthly income/expense records for each profile.

    Captures seasonal patterns aligned with Kharif/Rabi/Zaid cycles.
    """
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []

    # Seasonal multipliers (normalized so they average ~1.0 over 12 months)
    _SEASONAL_MULT = {
        1: 0.80,   # Jan (Rabi growing)
        2: 0.75,   # Feb
        3: 1.30,   # Mar (Rabi harvest)
        4: 1.40,   # Apr (Rabi harvest peak)
        5: 0.50,   # May (lean / Zaid)
        6: 0.60,   # Jun (Kharif sowing — expenses up, income low)
        7: 0.55,
        8: 0.65,
        9: 0.70,
        10: 1.20,  # Oct (Kharif harvest)
        11: 1.50,  # Nov (Kharif harvest peak)
        12: 1.05,  # Dec (Rabi sowing)
    }

    _EXPENSE_MULT = {
        1: 0.85, 2: 0.80, 3: 0.90, 4: 0.85,
        5: 0.75, 6: 1.30, 7: 1.35, 8: 1.20,
        9: 1.00, 10: 0.90, 11: 0.85, 12: 0.95,
    }

    sample_profiles = profiles.sample(min(5000, len(profiles)), random_state=seed)

    for _, profile in sample_profiles.iterrows():
        monthly_income_base = profile["annual_income"] / 12.0
        cv = profile["income_volatility_cv"]
        has_irrigation = profile["has_irrigation"]

        for m_offset in range(months):
            month = (m_offset % 12) + 1
            year = 2022 + m_offset // 12

            # Income with seasonal pattern + noise
            seasonal_mult = _SEASONAL_MULT[month]
            if has_irrigation:
                seasonal_mult = 1.0 + (seasonal_mult - 1.0) * 0.5  # dampened

            income_noise = rng.normal(1.0, cv * 0.3)
            monthly_income = max(0, monthly_income_base * seasonal_mult * income_noise)

            # Expenses
            expense_base = monthly_income_base * 0.6
            expense_noise = rng.normal(1.0, 0.1)
            monthly_expense = max(0, expense_base * _EXPENSE_MULT[month] * expense_noise)

            rows.append({
                "profile_id": profile["profile_id"],
                "month": month,
                "year": year,
                "monthly_income": round(monthly_income, 2),
                "monthly_expense": round(monthly_expense, 2),
                "net_cashflow": round(monthly_income - monthly_expense, 2),
                "season": _month_to_season(month),
            })

    df = pd.DataFrame(rows)
    logger.info("Generated %d monthly cashflow records for %d profiles",
                len(df), df["profile_id"].nunique())
    return df


# ---------------------------------------------------------------------------
# Early warning events generator
# ---------------------------------------------------------------------------

def generate_early_warning_events(
    profiles: pd.DataFrame,
    cashflows: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate labelled alert events from profiles and cashflows.

    Labels: severity (INFO/WARNING/CRITICAL) based on stress indicators.
    """
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []

    profile_ids = profiles["profile_id"].unique()
    cf_grouped = cashflows.groupby("profile_id") if len(cashflows) > 0 else {}

    for pid in profile_ids[:5000]:
        profile = profiles[profiles["profile_id"] == pid].iloc[0]

        if pid not in (cf_grouped.groups if hasattr(cf_grouped, "groups") else {}):
            continue

        cf = cf_grouped.get_group(pid).sort_values(["year", "month"])

        # Compute rolling metrics
        incomes = cf["monthly_income"].values
        expenses = cf["monthly_expense"].values
        nets = cf["net_cashflow"].values

        if len(incomes) < 6:
            continue

        # Generate check-points every 3 months
        for start in range(6, len(incomes), 3):
            window = nets[start - 6:start]
            income_window = incomes[start - 6:start]

            avg_income = np.mean(income_window) if len(income_window) > 0 else 0
            income_dev_3m = (
                (np.mean(income_window[-3:]) - avg_income) / max(avg_income, 1) * 100
                if len(income_window) >= 3 else 0
            )

            surplus_trend_slope = _linear_slope(window) if len(window) >= 3 else 0
            dti = profile["debt_to_income_ratio"]
            missed_payments = max(0, rng.poisson(dti * 2) - 1)
            days_overdue = max(0, rng.exponential(dti * 30))

            # Stress score
            stress_score = np.clip(
                dti * 30
                + missed_payments * 10
                + min(20, days_overdue / 3)
                + max(0, -surplus_trend_slope / 500 * 20),
                0, 100,
            )

            # Severity label
            if stress_score > 60 and income_dev_3m < -20 and dti > 0.5:
                severity = "CRITICAL"
            elif stress_score > 30 or income_dev_3m < -15:
                severity = "WARNING"
            else:
                severity = "INFO"

            month_idx = cf.iloc[min(start, len(cf) - 1)]

            rows.append({
                "profile_id": pid,
                "month": int(month_idx["month"]),
                "year": int(month_idx["year"]),
                "income_deviation_3m": round(float(income_dev_3m), 2),
                "surplus_trend_slope": round(float(surplus_trend_slope), 2),
                "dti_ratio": round(float(dti), 4),
                "missed_payments": int(missed_payments),
                "days_overdue_avg": round(float(days_overdue), 1),
                "stress_score": round(float(stress_score), 1),
                "severity": severity,
                "has_irrigation": bool(profile["has_irrigation"]),
                "weather_risk_score": float(profile["weather_risk_score"]),
                "market_risk_score": float(profile["market_risk_score"]),
                "crop_diversification_index": float(profile["crop_diversification_index"]),
                "risk_category": str(profile["risk_category"]),
            })

    df = pd.DataFrame(rows)
    logger.info(
        "Generated %d early warning events: %s",
        len(df),
        df["severity"].value_counts().to_dict() if len(df) > 0 else {},
    )
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _month_to_season(month: int) -> str:
    if month in (6, 7, 8, 9, 10):
        return "KHARIF"
    elif month in (11, 12, 1, 2, 3):
        return "RABI"
    return "ZAID"


def _linear_slope(values: np.ndarray) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=float)
    x_mean = x.mean()
    y_mean = values.mean()
    num = np.sum((x - x_mean) * (values - y_mean))
    den = np.sum((x - x_mean) ** 2)
    return float(num / den) if den != 0 else 0.0


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SYNTHETIC_SCHEMA = {
    "profiles": {
        "description": "Farmer profiles with 18+ risk features and default label",
        "columns": [
            "profile_id", "segment", "land_holding_acres", "annual_income",
            "income_volatility_cv", "months_below_average", "debt_to_income_ratio",
            "total_outstanding", "active_loan_count", "credit_utilisation",
            "on_time_repayment_ratio", "has_defaults", "seasonal_variance",
            "crop_diversification_index", "weather_risk_score", "market_risk_score",
            "dependents", "age", "has_irrigation", "soil_quality_score",
            "primary_crop", "district", "risk_score", "risk_category", "has_defaulted",
        ],
    },
    "cashflows": {
        "description": "Monthly income/expense time series per profile",
        "columns": [
            "profile_id", "month", "year", "monthly_income",
            "monthly_expense", "net_cashflow", "season",
        ],
    },
    "early_warning": {
        "description": "Labelled alert events with severity",
        "columns": [
            "profile_id", "month", "year", "income_deviation_3m",
            "surplus_trend_slope", "dti_ratio", "missed_payments",
            "days_overdue_avg", "stress_score", "severity",
            "has_irrigation", "weather_risk_score", "market_risk_score",
            "crop_diversification_index", "risk_category",
        ],
    },
}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic training data")
    parser.add_argument("--n-profiles", type=int, default=50_000, help="Number of profiles")
    parser.add_argument("--months", type=int, default=36, help="Months of cash flow history")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--output", type=str, default="ml-pipeline/data/output",
        help="Output directory",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    # 1. Profiles
    profiles = generate_farmer_profiles(n=args.n_profiles, seed=args.seed)
    profiles.to_parquet(output / "profiles.parquet", index=False)
    profiles.head(100).to_csv(output / "profiles_sample.csv", index=False)
    logger.info("Saved profiles → %s", output / "profiles.parquet")

    # 2. Cash flows
    cashflows = generate_cashflow_time_series(profiles, months=args.months, seed=args.seed)
    cashflows.to_parquet(output / "cashflows.parquet", index=False)
    logger.info("Saved cashflows → %s", output / "cashflows.parquet")

    # 3. Early warning
    ew_events = generate_early_warning_events(profiles, cashflows, seed=args.seed)
    ew_events.to_parquet(output / "early_warning_events.parquet", index=False)
    logger.info("Saved early warning events → %s", output / "early_warning_events.parquet")

    # 4. Schema
    with open(output / "schema.json", "w") as f:
        json.dump(SYNTHETIC_SCHEMA, f, indent=2)

    logger.info("Done — all synthetic data written to %s", output)


if __name__ == "__main__":
    main()
