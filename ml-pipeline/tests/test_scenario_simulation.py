"""Tests for ML Pipeline — Monte Carlo Scenario Engine.

Validates distribution fitting, correlated sampling, and scenario
simulation produce valid and consistent results.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats


# ---------------------------------------------------------------------------
# Distribution fitting
# ---------------------------------------------------------------------------


class TestFitDistributions:
    def test_fit_best_distribution_normal(self):
        from models.scenario_simulation.fit_distributions import (
            fit_best_distribution,
        )

        rng = np.random.default_rng(42)
        data = rng.normal(50_000, 10_000, size=500)
        result = fit_best_distribution(data, "test_income")

        assert result.variable == "test_income"
        assert result.dist_name in ("norm", "lognorm", "gamma", "weibull_min", "beta")
        assert result.ks_statistic >= 0
        assert 0 < result.p_value <= 1.0

    def test_fit_best_distribution_lognormal(self):
        from models.scenario_simulation.fit_distributions import (
            fit_best_distribution,
        )

        rng = np.random.default_rng(42)
        data = rng.lognormal(10, 0.5, size=1000)
        result = fit_best_distribution(data, "income")
        assert result.p_value > 0.01

    def test_fit_small_sample_defaults_to_normal(self):
        from models.scenario_simulation.fit_distributions import (
            fit_best_distribution,
        )

        data = np.array([100, 200, 300, 400, 500])
        result = fit_best_distribution(data, "tiny")
        assert result.dist_name == "norm"

    def test_fitted_distribution_sampling(self):
        from models.scenario_simulation.fit_distributions import (
            fit_best_distribution,
        )

        rng = np.random.default_rng(42)
        data = rng.normal(1000, 100, size=500)
        fitted = fit_best_distribution(data, "x")

        samples = fitted.sample(10_000, rng=rng)
        assert samples.shape == (10_000,)
        assert abs(np.mean(samples) - 1000) < 50

    def test_correlation_matrix_estimation(self):
        from models.scenario_simulation.fit_distributions import (
            estimate_correlation_matrix,
        )

        rng = np.random.default_rng(42)
        n = 500
        x = rng.normal(0, 1, n)
        y = 0.8 * x + 0.2 * rng.normal(0, 1, n)
        z = rng.normal(0, 1, n)

        import pandas as pd
        data = pd.DataFrame({"x": x, "y": y, "z": z})
        corr = estimate_correlation_matrix(data, ["x", "y", "z"])

        assert corr.shape == (3, 3)
        np.testing.assert_allclose(np.diag(corr), 1.0, atol=0.01)
        assert corr[0, 1] > 0.6

    def test_serialization_roundtrip(self, tmp_path):
        from models.scenario_simulation.fit_distributions import (
            estimate_correlation_matrix,
            fit_best_distribution,
            load_distributions,
            save_distributions,
        )

        rng = np.random.default_rng(42)
        data = rng.normal(1000, 100, size=200)
        fitted = {"var1": fit_best_distribution(data, "var1")}
        corr = np.array([[1.0]])
        names = ["var1"]

        save_distributions(fitted, corr, names, str(tmp_path))
        loaded_fitted, loaded_corr, loaded_names = load_distributions(str(tmp_path))

        assert loaded_names == names
        assert loaded_fitted["var1"].variable == "var1"
        np.testing.assert_allclose(loaded_corr, corr)


# ---------------------------------------------------------------------------
# Monte Carlo simulation
# ---------------------------------------------------------------------------


class TestMonteCarloSimulation:
    def _make_fitted(self):
        """Create synthetic fitted distributions for testing."""
        from models.scenario_simulation.fit_distributions import (
            fit_best_distribution,
        )

        rng = np.random.default_rng(42)
        data_income = rng.lognormal(10, 0.3, 500)
        data_expense = rng.lognormal(9, 0.2, 500)

        fitted = {
            "monthly_income": fit_best_distribution(data_income, "monthly_income"),
            "monthly_expense": fit_best_distribution(data_expense, "monthly_expense"),
        }
        corr = np.array([[1.0, 0.3], [0.3, 1.0]])
        names = ["monthly_income", "monthly_expense"]
        return fitted, corr, names

    def test_generate_correlated_samples(self):
        from models.scenario_simulation.monte_carlo import (
            generate_correlated_samples,
        )

        fitted, corr, names = self._make_fitted()
        rng = np.random.default_rng(42)
        samples = generate_correlated_samples(5000, fitted, corr, names, rng)
        assert samples.shape == (5000, 2)
        assert list(samples.columns) == names
        assert np.all(np.isfinite(samples.values))

    def test_predefined_scenarios_exist(self):
        from models.scenario_simulation.monte_carlo import (
            PREDEFINED_SCENARIOS,
            ScenarioSpec,
        )

        for name in ["drought", "flood", "market_crash", "good_monsoon", "baseline"]:
            assert name in PREDEFINED_SCENARIOS
            spec = PREDEFINED_SCENARIOS[name]
            assert isinstance(spec, ScenarioSpec)

    def test_drought_scenario_parameters(self):
        from models.scenario_simulation.monte_carlo import (
            PREDEFINED_SCENARIOS,
        )

        drought = PREDEFINED_SCENARIOS["drought"]
        assert drought.income_multiplier < 1.0
        assert drought.expense_multiplier >= 1.0

    def test_run_simulation_baseline(self):
        from models.scenario_simulation.monte_carlo import (
            PREDEFINED_SCENARIOS,
            run_simulation,
        )

        fitted, corr, names = self._make_fitted()
        result = run_simulation(
            fitted, corr, names,
            monthly_emi=5000,
            scenario=PREDEFINED_SCENARIOS["baseline"],
            config={"n_simulations": 1000, "horizon_months": 6, "seed": 42},
        )

        assert hasattr(result, "probability_of_default")
        assert hasattr(result, "expected_dscr")
        assert 0 <= result.probability_of_default <= 1
        assert result.expected_dscr > 0
        assert len(result.monthly_projections) == 6

    def test_drought_increases_default_probability(self):
        from models.scenario_simulation.monte_carlo import (
            PREDEFINED_SCENARIOS,
            run_simulation,
        )

        fitted, corr, names = self._make_fitted()
        cfg = {"n_simulations": 2000, "horizon_months": 6, "seed": 42}

        baseline = run_simulation(
            fitted, corr, names, 5000,
            PREDEFINED_SCENARIOS["baseline"], cfg,
        )
        drought = run_simulation(
            fitted, corr, names, 5000,
            PREDEFINED_SCENARIOS["drought"], cfg,
        )

        assert drought.probability_of_default >= baseline.probability_of_default

    def test_scenario_spec_immutable(self):
        from models.scenario_simulation.monte_carlo import ScenarioSpec

        spec = ScenarioSpec(name="test", description="Test scenario")
        with pytest.raises(AttributeError):
            spec.name = "modified"  # type: ignore[misc]

    def test_simulation_result_to_dict(self):
        from models.scenario_simulation.monte_carlo import (
            PREDEFINED_SCENARIOS,
            run_simulation,
        )

        fitted, corr, names = self._make_fitted()
        result = run_simulation(
            fitted, corr, names,
            monthly_emi=5000,
            config={"n_simulations": 500, "horizon_months": 3, "seed": 42},
        )

        d = result.to_dict()
        assert isinstance(d, dict)
        assert "scenario_name" in d
        assert "probability_of_default" in d
        assert "recommendations" in d
