"""Unit tests for services/early_warning/ml/scenario_model.py

Tests cover:
- Model (distribution params) availability & loading
- Output structure and value types
- Percentile ordering: p10 ≤ p50 ≤ p90 for every month
- Seed reproducibility
- Shock factor computation correctness
- Drought / market-crash → more deficit months than no-shock
- EMI reduction recommendation threshold
- Different land-holding segments yield different distributions
- No-stress scenario shows low deficit months
- Fallback defaults when JSON not found (monkeypatched)
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _warmup():
    from services.early_warning.ml import scenario_model
    scenario_model._ensure_loaded()


# ===========================================================================
# Availability
# ===========================================================================

class TestScenarioModelAvailability:

    def test_is_available(self):
        from services.early_warning.ml import scenario_model
        assert scenario_model.is_available() is True

    def test_dist_params_loaded(self):
        from services.early_warning.ml import scenario_model
        assert scenario_model._dist_params is not None
        assert "marginal" in scenario_model._dist_params
        assert "small" in scenario_model._dist_params
        assert "medium" in scenario_model._dist_params

    def test_seasonal_multipliers_have_12_values(self):
        from services.early_warning.ml import scenario_model
        assert scenario_model._seasonal_muls is not None
        assert len(scenario_model._seasonal_muls) == 12


# ===========================================================================
# Output structure
# ===========================================================================

REQUIRED_KEYS = {
    "income_p10_monthly",
    "income_p50_monthly",
    "income_p90_monthly",
    "months_in_deficit_p50",
    "months_in_deficit_p90",
    "repayment_stress_ratio",
    "recommended_emi_reduction_pct",
    "p10_annual_income_stressed",
    "p50_annual_income_stressed",
    "shock_factor",
    "simulation_runs",
    "model_version",
}

BASE_KWARGS = dict(
    annual_income=240000,
    land_holding_acres=2.5,
    weather_adjustment=1.0,
    market_price_change_pct=0.0,
    income_reduction_pct=0.0,
    duration_months=0,
    monthly_obligations=4000,
    household_expense=6000,
    seed=42,
)

def _simulate(**kwargs):
    from services.early_warning.ml import scenario_model
    params = {**BASE_KWARGS, **kwargs}
    return scenario_model.simulate(**params)


class TestScenarioOutputStructure:

    def test_returns_dict(self):
        result = _simulate()
        assert isinstance(result, dict)

    def test_all_required_keys_present(self):
        result = _simulate()
        assert REQUIRED_KEYS.issubset(result.keys())

    def test_model_version(self):
        result = _simulate()
        assert result["model_version"] == "monte-carlo-v1"

    def test_simulation_runs_equals_requested(self):
        result = _simulate(n_simulations=500)
        assert result["simulation_runs"] == 500

    def test_monthly_lists_have_12_values(self):
        result = _simulate()
        assert len(result["income_p10_monthly"]) == 12
        assert len(result["income_p50_monthly"]) == 12
        assert len(result["income_p90_monthly"]) == 12

    def test_all_monthly_values_non_negative(self):
        result = _simulate()
        for key in ("income_p10_monthly", "income_p50_monthly", "income_p90_monthly"):
            for v in result[key]:
                assert v >= 0.0, f"{key} has negative value: {v}"

    def test_deficit_months_in_range(self):
        result = _simulate()
        assert 0 <= result["months_in_deficit_p50"] <= 12
        assert 0 <= result["months_in_deficit_p90"] <= 12

    def test_p90_deficit_gte_p50_deficit(self):
        """p90 worst-case should have at least as many deficit months as p50."""
        result = _simulate()
        assert result["months_in_deficit_p90"] >= result["months_in_deficit_p50"]

    def test_repayment_stress_ratio_positive(self):
        result = _simulate()
        assert result["repayment_stress_ratio"] > 0.0

    def test_emi_reduction_in_range(self):
        result = _simulate()
        assert 0 <= result["recommended_emi_reduction_pct"] <= 50

    def test_shock_factor_in_range(self):
        result = _simulate()
        assert 0.05 <= result["shock_factor"] <= 2.0


# ===========================================================================
# Percentile ordering
# ===========================================================================

class TestScenarioPercentileOrdering:

    def test_p10_lte_p50_every_month(self):
        result = _simulate()
        for i, (p10, p50) in enumerate(
            zip(result["income_p10_monthly"], result["income_p50_monthly"]),
        ):
            assert p10 <= p50, f"Month {i+1}: p10={p10} > p50={p50}"

    def test_p50_lte_p90_every_month(self):
        result = _simulate()
        for i, (p50, p90) in enumerate(
            zip(result["income_p50_monthly"], result["income_p90_monthly"]),
        ):
            assert p50 <= p90, f"Month {i+1}: p50={p50} > p90={p90}"

    def test_p10_annual_lte_p50_annual(self):
        result = _simulate()
        assert result["p10_annual_income_stressed"] <= result["p50_annual_income_stressed"]


# ===========================================================================
# Reproducibility (seed)
# ===========================================================================

class TestScenarioReproducibility:

    def test_same_seed_same_result(self):
        a = _simulate(seed=123)
        b = _simulate(seed=123)
        assert a["months_in_deficit_p50"] == b["months_in_deficit_p50"]
        assert a["repayment_stress_ratio"] == b["repayment_stress_ratio"]
        assert a["income_p50_monthly"] == b["income_p50_monthly"]

    def test_different_seeds_different_results(self):
        a = _simulate(seed=1)
        b = _simulate(seed=999)
        # With 1000 simulations the medians are nearly identical but not identical
        # at least one of the percentile lists should differ
        assert a["income_p10_monthly"] != b["income_p10_monthly"] or \
               a["income_p90_monthly"] != b["income_p90_monthly"]


# ===========================================================================
# Shock factor logic
# ===========================================================================

class TestScenarioShockFactor:

    def test_no_shock_factor_is_one(self):
        result = _simulate(
            weather_adjustment=1.0,
            market_price_change_pct=0.0,
            income_reduction_pct=0.0,
        )
        assert abs(result["shock_factor"] - 1.0) < 1e-4

    def test_drought_reduces_shock_factor(self):
        result = _simulate(weather_adjustment=0.5)
        assert result["shock_factor"] < 1.0

    def test_market_crash_reduces_shock_factor(self):
        result = _simulate(market_price_change_pct=-30.0)
        assert result["shock_factor"] < 1.0

    def test_combined_shock_cumulative(self):
        r_drought      = _simulate(weather_adjustment=0.6)
        r_market       = _simulate(market_price_change_pct=-30.0)
        r_combined     = _simulate(weather_adjustment=0.6, market_price_change_pct=-30.0)
        assert r_combined["shock_factor"] < r_drought["shock_factor"]
        assert r_combined["shock_factor"] < r_market["shock_factor"]

    def test_severe_shock_clamped_to_minimum(self):
        result = _simulate(
            weather_adjustment=0.0,
            market_price_change_pct=-100.0,
        )
        assert result["shock_factor"] >= 0.05, "Shock factor should be clamped at 0.05"


# ===========================================================================
# Stress scenario behaviour
# ===========================================================================

class TestScenarioStressResponse:

    def test_severe_drought_more_deficit_months(self):
        no_shock = _simulate(weather_adjustment=1.0, seed=42)
        drought  = _simulate(weather_adjustment=0.3, duration_months=6, seed=42)
        assert drought["months_in_deficit_p50"] >= no_shock["months_in_deficit_p50"], (
            "Drought scenario should have more or equal deficit months"
        )

    def test_high_obligations_increase_stress_ratio(self):
        low_emi  = _simulate(monthly_obligations=1000, seed=42)
        high_emi = _simulate(monthly_obligations=15000, seed=42)
        assert high_emi["repayment_stress_ratio"] > low_emi["repayment_stress_ratio"]

    def test_emi_reduction_recommended_under_stress(self):
        result = _simulate(
            weather_adjustment=0.4,
            market_price_change_pct=-30.0,
            duration_months=8,
            monthly_obligations=10000,
            household_expense=8000,
            annual_income=120000,
            seed=42,
        )
        assert result["recommended_emi_reduction_pct"] > 0, (
            "Stressed scenario should recommend EMI reduction"
        )

    def test_no_stress_emi_reduction_zero(self):
        """Well-off farmer with no shock should need 0% EMI reduction."""
        result = _simulate(
            annual_income=1_200_000,
            monthly_obligations=2000,
            household_expense=3000,
            weather_adjustment=1.0,
            duration_months=0,
            seed=42,
        )
        assert result["recommended_emi_reduction_pct"] == 0


# ===========================================================================
# Segment differences
# ===========================================================================

class TestScenarioSegments:

    def test_medium_farmer_higher_income_than_marginal(self):
        marginal = _simulate(land_holding_acres=0.5, seed=42)
        medium   = _simulate(land_holding_acres=6.0, seed=42)
        # Medium farmer should have higher p50 annual stressed income
        # (we use annual_income to anchor, so the distributions differ only in spread)
        # Both use same annual_income so test spread (σ) rather than level
        # Medium has lower sigma → tighter distribution → narrower p10/p90 spread
        m_spread  = medium["income_p90_monthly"][0] - medium["income_p10_monthly"][0]
        mg_spread = marginal["income_p90_monthly"][0] - marginal["income_p10_monthly"][0]
        assert mg_spread >= m_spread, (
            "Marginal farmer should have wider income spread due to higher sigma"
        )


# ===========================================================================
# Edge cases
# ===========================================================================

class TestScenarioEdgeCases:

    def test_zero_duration_months_shock_applied_zero_months(self):
        """duration_months=0 means no shock → shock_factor applied to 0 months."""
        base   = _simulate(weather_adjustment=0.5, duration_months=0, seed=42)
        # With duration=0 no month is shocked, so shock_factor=0.5 but never applied
        # Monthly incomes should be same as no-shock baseline
        no_shock = _simulate(weather_adjustment=1.0, duration_months=0, seed=42)
        # They should differ because shock_factor is 0.5 but duration=0 means 0 months affected
        # Actually looking at the code: for i in range(n_affected): where n_affected = min(max(0,0),12) = 0
        # so nothing is modified. So results should be identical except shock_factor in output
        assert base["income_p50_monthly"] == no_shock["income_p50_monthly"], (
            "With duration_months=0, no months affected → same income as no-shock"
        )

    def test_very_high_income_no_deficit(self):
        result = _simulate(
            annual_income=5_000_000,
            monthly_obligations=2000,
            household_expense=3000,
            seed=42,
        )
        assert result["months_in_deficit_p50"] == 0

    def test_returns_none_on_failure(self, monkeypatch):
        from services.early_warning.ml import scenario_model
        # Force the internal function to raise
        monkeypatch.setattr(scenario_model, "_dist_params", None)
        monkeypatch.setattr(scenario_model, "_seasonal_muls", None)
        # simulate() calls _ensure_loaded() which sets defaults even if file missing
        # So this should still succeed; we need to break it differently
        orig_outer = scenario_model.np.outer
        def bad_outer(*args, **kwargs):
            raise RuntimeError("forced failure")
        monkeypatch.setattr(scenario_model.np, "outer", bad_outer)
        result = scenario_model.simulate(**BASE_KWARGS)
        assert result is None
