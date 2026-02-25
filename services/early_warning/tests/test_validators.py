"""Unit tests for Early Warning domain validators."""

from __future__ import annotations

import pytest

from services.early_warning.app.domain.models import ScenarioParameters, ScenarioType
from services.early_warning.app.domain.validators import (
    validate_monitor_request,
    validate_multi_scenario_request,
    validate_scenario_params,
)


# ===========================================================================
# Monitor Request Validation
# ===========================================================================
class TestValidateMonitorRequest:
    def test_valid_profile_id(self):
        validate_monitor_request("prof-123")  # no error

    def test_empty_profile_id(self):
        with pytest.raises(ValueError, match="profile_id"):
            validate_monitor_request("")

    def test_whitespace_profile_id(self):
        with pytest.raises(ValueError, match="profile_id"):
            validate_monitor_request("   ")

    def test_none_profile_id(self):
        with pytest.raises((ValueError, TypeError)):
            validate_monitor_request(None)  # type: ignore


# ===========================================================================
# Scenario Params Validation
# ===========================================================================
class TestValidateScenarioParams:
    def _make_params(self, **overrides) -> ScenarioParameters:
        defaults = {
            "scenario_type": ScenarioType.INCOME_SHOCK,
            "name": "Test Scenario",
            "income_reduction_pct": 20.0,
            "weather_adjustment": 1.0,
            "market_price_change_pct": 0.0,
            "duration_months": 6,
        }
        defaults.update(overrides)
        return ScenarioParameters(**defaults)

    def test_valid_params(self):
        validate_scenario_params(self._make_params())

    def test_empty_name(self):
        with pytest.raises(ValueError, match=r"[Nn]ame"):
            validate_scenario_params(self._make_params(name=""))

    def test_whitespace_name(self):
        with pytest.raises(ValueError, match=r"[Nn]ame"):
            validate_scenario_params(self._make_params(name="  "))

    def test_income_reduction_negative(self):
        with pytest.raises(ValueError, match="income_reduction_pct"):
            validate_scenario_params(self._make_params(income_reduction_pct=-5))

    def test_income_reduction_over_100(self):
        with pytest.raises(ValueError, match="income_reduction_pct"):
            validate_scenario_params(self._make_params(income_reduction_pct=101))

    def test_weather_adjustment_negative(self):
        with pytest.raises(ValueError, match="weather_adjustment"):
            validate_scenario_params(self._make_params(weather_adjustment=-0.1))

    def test_weather_adjustment_over_2(self):
        with pytest.raises(ValueError, match="weather_adjustment"):
            validate_scenario_params(self._make_params(weather_adjustment=2.1))

    def test_market_change_too_low(self):
        with pytest.raises(ValueError, match="market_price_change_pct"):
            validate_scenario_params(self._make_params(market_price_change_pct=-101))

    def test_market_change_too_high(self):
        with pytest.raises(ValueError, match="market_price_change_pct"):
            validate_scenario_params(self._make_params(market_price_change_pct=101))

    def test_duration_zero(self):
        with pytest.raises(ValueError, match="duration_months"):
            validate_scenario_params(self._make_params(duration_months=0))

    def test_duration_too_long(self):
        with pytest.raises(ValueError, match="duration_months"):
            validate_scenario_params(self._make_params(duration_months=61))

    def test_boundary_values_accepted(self):
        validate_scenario_params(self._make_params(
            income_reduction_pct=0, weather_adjustment=0.0,
            market_price_change_pct=-100, duration_months=1,
        ))
        validate_scenario_params(self._make_params(
            income_reduction_pct=100, weather_adjustment=2.0,
            market_price_change_pct=100, duration_months=60,
        ))


# ===========================================================================
# Multi-Scenario Validation
# ===========================================================================
class TestValidateMultiScenarioRequest:
    def _param(self, name="Test") -> ScenarioParameters:
        return ScenarioParameters(
            scenario_type=ScenarioType.INCOME_SHOCK,
            name=name,
            income_reduction_pct=20.0,
        )

    def test_valid_single_scenario(self):
        validate_multi_scenario_request([self._param()])

    def test_valid_multiple_scenarios(self):
        validate_multi_scenario_request([self._param(f"S{i}") for i in range(5)])

    def test_empty_list(self):
        with pytest.raises(ValueError, match=r"[Aa]t least one"):
            validate_multi_scenario_request([])

    def test_too_many_scenarios(self):
        with pytest.raises(ValueError, match=r"[Mm]aximum"):
            validate_multi_scenario_request([self._param(f"S{i}") for i in range(11)])

    def test_invalid_scenario_in_list(self):
        invalid = ScenarioParameters(
            scenario_type=ScenarioType.INCOME_SHOCK,
            name="",  # invalid
        )
        with pytest.raises(ValueError):
            validate_multi_scenario_request([self._param(), invalid])

    def test_custom_max(self):
        with pytest.raises(ValueError, match="3"):
            validate_multi_scenario_request(
                [self._param(f"S{i}") for i in range(4)],
                max_scenarios=3,
            )
