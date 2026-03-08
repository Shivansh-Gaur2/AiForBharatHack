"""Monte Carlo scenario simulation engine.

Generates N forward-looking cash-flow paths by sampling from fitted
marginal distributions with rank-correlated draws (Iman-Conover).
Computes repayment capacity impact, probability of default,
and scenario recommendations.
"""

from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from models.scenario_simulation.fit_distributions import (
    FittedDistribution,
    load_distributions,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
    "n_simulations": 10_000,
    "horizon_months": 12,
    "confidence_levels": [0.05, 0.25, 0.50, 0.75, 0.95],
    "default_threshold_dscr": 1.0,  # Debt Service Coverage Ratio
    "seed": 42,
}


@dataclass(frozen=True)
class ScenarioSpec:
    """Definition of a stress / optimistic scenario."""

    name: str
    description: str
    income_multiplier: float = 1.0
    expense_multiplier: float = 1.0
    weather_shock: float = 0.0  # Additional % reduction to income
    market_shock: float = 0.0  # Additional % change to expenses


# Pre-defined scenarios from domain spec
PREDEFINED_SCENARIOS: dict[str, ScenarioSpec] = {
    "drought": ScenarioSpec(
        name="drought",
        description="Severe drought – 40% income reduction, 10% expense increase",
        income_multiplier=0.6,
        expense_multiplier=1.10,
        weather_shock=-0.40,
    ),
    "flood": ScenarioSpec(
        name="flood",
        description="Flood event – 50% income loss, 15% expense increase",
        income_multiplier=0.5,
        expense_multiplier=1.15,
        weather_shock=-0.50,
    ),
    "market_crash": ScenarioSpec(
        name="market_crash",
        description="Market price crash – 30% income reduction",
        income_multiplier=0.7,
        expense_multiplier=1.0,
        market_shock=-0.30,
    ),
    "good_monsoon": ScenarioSpec(
        name="good_monsoon",
        description="Good monsoon – 20% income increase, stable expenses",
        income_multiplier=1.2,
        expense_multiplier=1.0,
        weather_shock=0.15,
    ),
    "baseline": ScenarioSpec(
        name="baseline",
        description="Normal conditions – no shocks",
    ),
}


# ---------------------------------------------------------------------------
# Correlated sampling (Iman–Conover)
# ---------------------------------------------------------------------------

def generate_correlated_samples(
    n: int,
    fitted: dict[str, FittedDistribution],
    correlation: np.ndarray,
    variable_names: list[str],
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate correlated samples from marginal distributions.

    Uses the Iman–Conover method: generate independent marginal samples,
    then reorder them to match a target rank correlation structure.
    """
    k = len(variable_names)

    # Step 1: Generate independent marginal samples
    independent = np.zeros((n, k))
    for i, var in enumerate(variable_names):
        if var in fitted:
            independent[:, i] = fitted[var].sample(n, rng)
        else:
            independent[:, i] = rng.normal(0, 1, n)

    # Step 2: Generate reference matrix with desired correlation
    L = np.linalg.cholesky(correlation + 1e-10 * np.eye(k))
    z = rng.standard_normal((n, k))
    reference = z @ L.T

    # Step 3: Reorder independent samples to match reference rank ordering
    result = np.zeros_like(independent)
    for j in range(k):
        target_ranks = np.argsort(np.argsort(reference[:, j]))
        sorted_marginal = np.sort(independent[:, j])
        result[:, j] = sorted_marginal[target_ranks]

    return pd.DataFrame(result, columns=variable_names)


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------

@dataclass
class SimulationResult:
    """Aggregated results from Monte Carlo simulation."""

    scenario_name: str
    n_simulations: int
    horizon_months: int
    monthly_projections: list[dict[str, Any]]  # percentile bands per month
    probability_of_default: float
    expected_dscr: float
    dscr_distribution: dict[str, float]  # percentile → dscr
    total_surplus_distribution: dict[str, float]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "n_simulations": self.n_simulations,
            "horizon_months": self.horizon_months,
            "monthly_projections": self.monthly_projections,
            "probability_of_default": round(self.probability_of_default, 4),
            "expected_dscr": round(self.expected_dscr, 3),
            "dscr_distribution": {k: round(v, 3) for k, v in self.dscr_distribution.items()},
            "total_surplus_distribution": {k: round(v, 2) for k, v in self.total_surplus_distribution.items()},
            "recommendations": self.recommendations,
        }


def run_simulation(
    fitted: dict[str, FittedDistribution],
    correlation: np.ndarray,
    variable_names: list[str],
    monthly_emi: float,
    scenario: ScenarioSpec | None = None,
    config: dict[str, Any] | None = None,
) -> SimulationResult:
    """Run Monte Carlo simulation for a given scenario.

    Args:
        fitted: Marginal distributions per variable.
        correlation: Rank correlation matrix.
        variable_names: Ordered list of variable names.
        monthly_emi: Monthly EMI / debt service obligation.
        scenario: Optional stress scenario to apply.
        config: Simulation configuration overrides.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    scenario = scenario or PREDEFINED_SCENARIOS["baseline"]
    n = int(cfg["n_simulations"])
    horizon = int(cfg["horizon_months"])
    rng = np.random.default_rng(cfg.get("seed", 42))
    confidence_levels = cfg["confidence_levels"]

    # Generate samples for each month
    monthly_incomes = np.zeros((n, horizon))
    monthly_expenses = np.zeros((n, horizon))

    for m in range(horizon):
        samples = generate_correlated_samples(n, fitted, correlation, variable_names, rng)

        income = samples.get("monthly_income", pd.Series(np.zeros(n))).values
        expense = samples.get("monthly_expense", pd.Series(np.zeros(n))).values

        # Apply scenario shocks
        income = income * scenario.income_multiplier
        expense = expense * scenario.expense_multiplier

        if scenario.weather_shock != 0:
            income = income * (1 + scenario.weather_shock)
        if scenario.market_shock != 0:
            expense = expense * (1 - scenario.market_shock)

        # Apply seasonality modifier (rougher months have more variance)
        month_idx = m % 12
        if month_idx in (4, 5, 6):  # pre-monsoon lean
            income *= rng.uniform(0.8, 1.0, n)

        monthly_incomes[:, m] = np.maximum(income, 0)
        monthly_expenses[:, m] = np.maximum(expense, 0)

    # Compute metrics
    monthly_surplus = monthly_incomes - monthly_expenses
    total_surplus = monthly_surplus.sum(axis=1)

    # DSCR = total income / total debt service
    total_debt_service = monthly_emi * horizon
    total_income = monthly_incomes.sum(axis=1)
    dscr = total_income / max(total_debt_service, 1.0)

    # Default: any month where surplus < EMI
    default_months = (monthly_surplus < monthly_emi).any(axis=1)
    prob_default = float(default_months.mean())

    # Build monthly projections with percentile bands
    monthly_projections = []
    for m in range(horizon):
        proj: dict[str, Any] = {"month": m + 1}
        for pct in confidence_levels:
            label = f"p{int(pct * 100)}"
            proj[f"income_{label}"] = round(float(np.percentile(monthly_incomes[:, m], pct * 100)), 2)
            proj[f"expense_{label}"] = round(float(np.percentile(monthly_expenses[:, m], pct * 100)), 2)
            proj[f"surplus_{label}"] = round(float(np.percentile(monthly_surplus[:, m], pct * 100)), 2)
        monthly_projections.append(proj)

    # Distribution summaries
    dscr_dist = {
        f"p{int(p * 100)}": float(np.percentile(dscr, p * 100))
        for p in confidence_levels
    }
    surplus_dist = {
        f"p{int(p * 100)}": float(np.percentile(total_surplus, p * 100))
        for p in confidence_levels
    }

    # Recommendations
    recommendations = _generate_recommendations(
        prob_default, float(np.mean(dscr)), scenario.name,
    )

    return SimulationResult(
        scenario_name=scenario.name,
        n_simulations=n,
        horizon_months=horizon,
        monthly_projections=monthly_projections,
        probability_of_default=prob_default,
        expected_dscr=float(np.mean(dscr)),
        dscr_distribution=dscr_dist,
        total_surplus_distribution=surplus_dist,
        recommendations=recommendations,
    )


def compare_scenarios(
    fitted: dict[str, FittedDistribution],
    correlation: np.ndarray,
    variable_names: list[str],
    monthly_emi: float,
    scenario_names: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, SimulationResult]:
    """Run simulation across multiple scenarios for comparison."""
    names = scenario_names or list(PREDEFINED_SCENARIOS.keys())
    results: dict[str, SimulationResult] = {}

    for name in names:
        if name not in PREDEFINED_SCENARIOS:
            logger.warning("Unknown scenario '%s' – skipping", name)
            continue
        scenario = PREDEFINED_SCENARIOS[name]
        logger.info("Simulating scenario: %s …", name)
        results[name] = run_simulation(
            fitted, correlation, variable_names, monthly_emi, scenario, config,
        )

    return results


# ---------------------------------------------------------------------------
# Recommendation logic
# ---------------------------------------------------------------------------

def _generate_recommendations(
    prob_default: float,
    mean_dscr: float,
    scenario_name: str,
) -> list[str]:
    recs: list[str] = []

    if prob_default > 0.30:
        recs.append("HIGH DEFAULT RISK: Consider restructuring the loan with lower EMI or extended tenure.")
    elif prob_default > 0.15:
        recs.append("MODERATE DEFAULT RISK: Recommend building a 3-month cash reserve before borrowing.")

    if mean_dscr < 1.2:
        recs.append("DSCR below 1.2× – the borrower may struggle in adverse months. Consider loan insurance.")
    elif mean_dscr > 2.0:
        recs.append("Strong repayment capacity. Eligible for higher loan amount if needed.")

    if scenario_name in ("drought", "flood"):
        recs.append(f"Under {scenario_name} stress, recommend crop insurance and access to emergency credit.")

    if not recs:
        recs.append("Repayment capacity looks healthy under this scenario.")

    return recs
