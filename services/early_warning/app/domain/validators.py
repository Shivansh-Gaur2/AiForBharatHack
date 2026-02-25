"""Validation functions for the Early Warning & Scenario service.

Data quality and input validation — keeps the service layer clean.
"""

from __future__ import annotations

from .models import ScenarioParameters


def validate_monitor_request(profile_id: str) -> None:
    """Validate a monitoring / alert-generation request."""
    if not profile_id or not profile_id.strip():
        raise ValueError("profile_id is required")


def validate_scenario_params(params: ScenarioParameters) -> None:
    """Validate scenario simulation parameters."""
    if not params.name or not params.name.strip():
        raise ValueError("Scenario name is required")

    if params.income_reduction_pct < 0 or params.income_reduction_pct > 100:
        raise ValueError("income_reduction_pct must be between 0 and 100")

    if params.weather_adjustment < 0.0 or params.weather_adjustment > 2.0:
        raise ValueError("weather_adjustment must be between 0.0 and 2.0")

    if params.market_price_change_pct < -100 or params.market_price_change_pct > 100:
        raise ValueError("market_price_change_pct must be between -100 and 100")

    if params.duration_months < 1 or params.duration_months > 60:
        raise ValueError("duration_months must be between 1 and 60")


def validate_multi_scenario_request(
    scenarios: list[ScenarioParameters],
    max_scenarios: int = 10,
) -> None:
    """Validate a multi-scenario comparison request."""
    if not scenarios:
        raise ValueError("At least one scenario is required")
    if len(scenarios) > max_scenarios:
        raise ValueError(f"Maximum {max_scenarios} scenarios allowed per request")
    for s in scenarios:
        validate_scenario_params(s)
