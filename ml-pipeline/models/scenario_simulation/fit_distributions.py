"""Distribution fitting for Monte Carlo scenario simulation.

Fits parametric distributions to historical income, expense, weather,
and market data using scipy. These fitted distributions are sampled
during Monte Carlo forward-propagation.
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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Distribution candidates (ranked by realism for rural income data)
# ---------------------------------------------------------------------------

CANDIDATE_DISTRIBUTIONS = [
    stats.lognorm,
    stats.gamma,
    stats.weibull_min,
    stats.norm,
    stats.beta,
]


@dataclass(frozen=True)
class FittedDistribution:
    """Immutable result of a distribution fit."""

    variable: str
    dist_name: str
    params: tuple[float, ...]
    ks_statistic: float
    p_value: float

    def sample(self, n: int = 1, rng: np.random.Generator | None = None) -> np.ndarray:
        """Draw samples from the fitted distribution."""
        dist = getattr(stats, self.dist_name)
        if rng is not None:
            return dist.rvs(*self.params, size=n, random_state=rng.integers(2**31))
        return dist.rvs(*self.params, size=n)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable": self.variable,
            "dist_name": self.dist_name,
            "params": list(self.params),
            "ks_statistic": round(self.ks_statistic, 6),
            "p_value": round(self.p_value, 6),
        }


# ---------------------------------------------------------------------------
# Distribution fitting
# ---------------------------------------------------------------------------

def fit_best_distribution(
    data: np.ndarray,
    variable_name: str,
    candidates: list[Any] | None = None,
) -> FittedDistribution:
    """Fit the best parametric distribution via KS test on the given data.

    Selects the distribution with the highest p-value (least-rejected).
    """
    candidates = candidates or CANDIDATE_DISTRIBUTIONS
    clean = data[np.isfinite(data)]
    if len(clean) < 10:
        # Not enough data → default to normal
        mu, sigma = np.mean(clean), max(np.std(clean), 1e-6)
        return FittedDistribution(variable_name, "norm", (mu, sigma), 1.0, 1.0)

    best: FittedDistribution | None = None

    for dist in candidates:
        try:
            params = dist.fit(clean)
            ks_stat, p_val = stats.kstest(clean, dist.name, args=params)
            candidate = FittedDistribution(variable_name, dist.name, params, ks_stat, p_val)
            if best is None or p_val > best.p_value:
                best = candidate
        except Exception:
            continue

    if best is None:
        mu, sigma = float(np.mean(clean)), float(max(np.std(clean), 1e-6))
        best = FittedDistribution(variable_name, "norm", (mu, sigma), 1.0, 1.0)

    logger.info(
        "Variable '%s' → %s (KS=%.4f, p=%.4f)",
        variable_name, best.dist_name, best.ks_statistic, best.p_value,
    )
    return best


def fit_all_variables(
    df: pd.DataFrame,
    variable_columns: list[str],
) -> dict[str, FittedDistribution]:
    """Fit distributions for multiple variables."""
    fitted: dict[str, FittedDistribution] = {}
    for col in variable_columns:
        if col in df.columns:
            fitted[col] = fit_best_distribution(df[col].values, col)
        else:
            logger.warning("Column '%s' not found — skipping", col)
    return fitted


# ---------------------------------------------------------------------------
# Correlation matrix estimation
# ---------------------------------------------------------------------------

def estimate_correlation_matrix(
    df: pd.DataFrame,
    variable_columns: list[str],
) -> np.ndarray:
    """Estimate rank correlation (Spearman) between variables.

    Uses Spearman because the marginals may be non-normal.
    """
    subset = df[variable_columns].dropna()
    if len(subset) < 10:
        return np.eye(len(variable_columns))

    corr = subset.corr(method="spearman").values
    # Ensure positive semi-definite
    corr = _nearest_psd(corr)
    return corr


def _nearest_psd(A: np.ndarray) -> np.ndarray:
    """Find nearest positive semi-definite matrix (Higham)."""
    B = (A + A.T) / 2
    eigvals, eigvecs = np.linalg.eigh(B)
    eigvals = np.maximum(eigvals, 0)
    return eigvecs @ np.diag(eigvals) @ eigvecs.T


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def save_distributions(
    fitted: dict[str, FittedDistribution],
    correlation: np.ndarray,
    variable_names: list[str],
    output_path: str | pathlib.Path,
) -> None:
    """Persist fitted distributions and correlation matrix."""
    out = pathlib.Path(output_path)
    out.mkdir(parents=True, exist_ok=True)

    dist_data = {k: v.to_dict() for k, v in fitted.items()}
    with open(out / "fitted_distributions.json", "w") as f:
        json.dump(dist_data, f, indent=2)

    np.save(str(out / "correlation_matrix.npy"), correlation)

    with open(out / "variable_names.json", "w") as f:
        json.dump(variable_names, f)

    logger.info("Distributions saved to %s", out)


def load_distributions(
    input_path: str | pathlib.Path,
) -> tuple[dict[str, FittedDistribution], np.ndarray, list[str]]:
    """Load previously fitted distributions."""
    inp = pathlib.Path(input_path)

    with open(inp / "fitted_distributions.json") as f:
        raw = json.load(f)

    fitted = {
        k: FittedDistribution(
            variable=v["variable"],
            dist_name=v["dist_name"],
            params=tuple(v["params"]),
            ks_statistic=v["ks_statistic"],
            p_value=v["p_value"],
        )
        for k, v in raw.items()
    }

    correlation = np.load(str(inp / "correlation_matrix.npy"))

    with open(inp / "variable_names.json") as f:
        variable_names = json.load(f)

    return fitted, correlation, variable_names
