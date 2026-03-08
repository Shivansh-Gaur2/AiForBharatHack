"""Monte Carlo scenario model – service-side wrapper.

Provides scenario simulation backed by the ML pipeline's
fitted distributions and Monte Carlo engine.

Flag-gated via ``USE_ML_SCENARIO_MODEL`` environment variable.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

USE_ML_MODEL = os.environ.get("USE_ML_SCENARIO_MODEL", "false").lower() == "true"
DISTRIBUTION_DIR = os.environ.get("SCENARIO_DISTRIBUTION_DIR", "")


@dataclass
class ScenarioSimulationResult:
    """Result from Monte Carlo simulation."""

    scenario_name: str
    probability_of_default: float
    expected_dscr: float
    monthly_projections: list[dict[str, Any]]
    recommendations: list[str]
    model_version: str = "monte-carlo-v1"


class MonteCarloScenarioModel:
    """Scenario simulator backed by fitted distribution artefacts."""

    def __init__(self, distribution_dir: str = DISTRIBUTION_DIR) -> None:
        self._dist_dir = distribution_dir
        self._fitted = None
        self._correlation = None
        self._variable_names = None
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return

        from ml_pipeline.models.scenario_simulation.fit_distributions import load_distributions

        self._fitted, self._correlation, self._variable_names = load_distributions(
            self._dist_dir
        )
        self._loaded = True
        logger.info("Loaded fitted distributions from %s", self._dist_dir)

    def simulate(
        self,
        monthly_emi: float,
        scenario_name: str = "baseline",
        n_simulations: int = 10_000,
        horizon_months: int = 12,
    ) -> ScenarioSimulationResult:
        self._load()

        from ml_pipeline.models.scenario_simulation.monte_carlo import (
            PREDEFINED_SCENARIOS,
            run_simulation,
        )

        scenario = PREDEFINED_SCENARIOS.get(scenario_name)
        if scenario is None:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        config = {
            "n_simulations": n_simulations,
            "horizon_months": horizon_months,
        }

        result = run_simulation(
            self._fitted,
            self._correlation,
            self._variable_names,
            monthly_emi,
            scenario,
            config,
        )

        return ScenarioSimulationResult(
            scenario_name=result.scenario_name,
            probability_of_default=result.probability_of_default,
            expected_dscr=result.expected_dscr,
            monthly_projections=result.monthly_projections,
            recommendations=result.recommendations,
        )

    def compare_scenarios(
        self,
        monthly_emi: float,
        scenario_names: list[str] | None = None,
        n_simulations: int = 10_000,
    ) -> dict[str, ScenarioSimulationResult]:
        self._load()

        from ml_pipeline.models.scenario_simulation.monte_carlo import (
            compare_scenarios,
        )

        config = {"n_simulations": n_simulations}
        results = compare_scenarios(
            self._fitted,
            self._correlation,
            self._variable_names,
            monthly_emi,
            scenario_names,
            config,
        )

        return {
            name: ScenarioSimulationResult(
                scenario_name=r.scenario_name,
                probability_of_default=r.probability_of_default,
                expected_dscr=r.expected_dscr,
                monthly_projections=r.monthly_projections,
                recommendations=r.recommendations,
            )
            for name, r in results.items()
        }

    def get_model_version(self) -> str:
        return "monte-carlo-v1"


def get_ml_scenario_model() -> MonteCarloScenarioModel | None:
    """Factory: return scenario model if enabled and artefacts are available."""
    if not USE_ML_MODEL:
        return None
    if not DISTRIBUTION_DIR:
        return None
    return MonteCarloScenarioModel(DISTRIBUTION_DIR)
