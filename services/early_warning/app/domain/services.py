"""Early Warning & Scenario domain service — orchestrates use cases.

Consumes data from Risk, CashFlow, Loan, and Profile services (via ports),
generates alerts, runs scenario simulations, and publishes events.
"""

from __future__ import annotations

import logging
import os

from services.shared.events import AsyncEventPublisher, DomainEvent
from services.shared.models import AlertType, ProfileId, RiskCategory

from .interfaces import (
    AlertRepository,
    CashFlowDataProvider,
    LoanDataProvider,
    ProfileDataProvider,
    RiskDataProvider,
)
from .models import (
    Alert,
    ScenarioParameters,
    SimulationResult,
    build_alert,
    compute_income_deviations,
    compute_repayment_stress,
    run_multi_scenario_comparison,
    simulate_scenario,
)
from .validators import (
    validate_monitor_request,
    validate_multi_scenario_request,
    validate_scenario_params,
)

logger = logging.getLogger(__name__)


class EarlyWarningService:
    """Application service for Early Warning & Scenario Simulation.

    Req 5.1–5.5 (Early Warning), Req 6.1–6.5 (Scenario Simulation).
    """

    def __init__(
        self,
        repo: AlertRepository,
        risk_provider: RiskDataProvider,
        cashflow_provider: CashFlowDataProvider,
        loan_provider: LoanDataProvider,
        profile_provider: ProfileDataProvider,
        events: AsyncEventPublisher,
    ) -> None:
        self._repo = repo
        self._risk = risk_provider
        self._cashflow = cashflow_provider
        self._loans = loan_provider
        self._profiles = profile_provider
        self._events = events

    # -----------------------------------------------------------------------
    # Early Warning — Monitoring & Alert Generation
    # -----------------------------------------------------------------------
    async def monitor_and_alert(self, profile_id: ProfileId) -> Alert:
        """Run full monitoring pipeline: gather data → detect stress → generate alert.

        Cross-service orchestration: fetches from Risk, CashFlow, Loan, Profile.
        Req 5.1, 5.2, 5.3, 5.4.
        """
        validate_monitor_request(profile_id)

        # Gather data from other services
        risk_cat_str = await self._risk.get_latest_risk_category(profile_id)
        risk_category = RiskCategory(risk_cat_str) if risk_cat_str else None

        projections = await self._cashflow.get_latest_forecast_projections(profile_id)
        expected_incomes = [(m, y, inf) for m, y, inf, _ in projections]

        actual_incomes = await self._profiles.get_actual_incomes(profile_id)

        exposure = await self._loans.get_debt_exposure(profile_id)
        repayment_stats = await self._loans.get_repayment_stats(profile_id)

        # Compute deviations
        deviations = compute_income_deviations(expected_incomes, actual_incomes)

        # Compute repayment stress
        # Build surplus trend from projections
        surplus_trend = [inf - outf for _, _, inf, outf in projections[-6:]]
        stress = compute_repayment_stress(
            dti_ratio=exposure.get("debt_to_income_ratio", 0.0),
            missed_payments=repayment_stats.get("missed_payments", 0),
            days_overdue_avg=repayment_stats.get("days_overdue_avg", 0.0),
            recent_surplus_trend=surplus_trend,
        )

        # Build alert
        alert = build_alert(
            profile_id=profile_id,
            stress=stress,
            deviations=deviations,
            risk_category=risk_category,
        )

        # ML severity override (flag-gated: EARLY_WARNING_ML_ENABLED=true)
        if os.getenv("EARLY_WARNING_ML_ENABLED", "false").lower() == "true":
            from services.early_warning.ml import warning_model as _ml_ew  # lazy
            from services.shared.models import AlertSeverity as _AS

            _risk_idx = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "VERY_HIGH": 3}
            _ml_features = {
                "income_deviation_3m":   deviations[-1].deviation_pct if deviations else 0.0,
                "income_deviation_6m":   (
                    sum(d.deviation_pct for d in deviations) / len(deviations)
                    if deviations else 0.0
                ),
                "missed_payments_ytd":   repayment_stats.get("missed_payments", 0),
                "days_overdue_avg":      repayment_stats.get("days_overdue_avg", 0.0),
                "dti_ratio":             exposure.get("debt_to_income_ratio", 0.0),
                "dti_delta_3m":          0.0,
                "surplus_trend_slope":   (
                    (surplus_trend[-1] - surplus_trend[0]) / max(len(surplus_trend), 1)
                    if len(surplus_trend) >= 2 else 0.0
                ),
                "weather_shock_score":   0.0,
                "market_price_shock":    0.0,
                "seasonal_stress_flag":  0,
                "risk_category_current": _risk_idx.get(risk_cat_str or "LOW", 0),
                "days_since_last_alert": 0,
            }
            _ml_result = _ml_ew.predict(_ml_features)
            if _ml_result is not None:
                _ml_sev = _AS(_ml_result["severity"])
                _sev_order = {_AS.INFO: 0, _AS.WARNING: 1, _AS.CRITICAL: 2}
                if _sev_order.get(_ml_sev, 0) > _sev_order.get(alert.severity, 0):
                    alert.escalate(_ml_sev, f"ML model (anomaly_score={_ml_result['anomaly_score']:.1f})")

        # Persist
        await self._repo.save_alert(alert)

        # Publish event
        await self._events.publish(DomainEvent(
            event_type="alert.generated",
            aggregate_id=alert.alert_id,
            payload={
                "profile_id": profile_id,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "title": alert.title,
            },
        ))

        logger.info(
            "Alert generated: %s severity=%s for profile %s",
            alert.alert_id, alert.severity, profile_id,
        )
        return alert

    async def generate_alert_direct(
        self,
        profile_id: ProfileId,
        dti_ratio: float = 0.0,
        missed_payments: int = 0,
        days_overdue_avg: float = 0.0,
        recent_surplus_trend: list[float] | None = None,
        expected_incomes: list[tuple[int, int, float]] | None = None,
        actual_incomes: list[tuple[int, int, float]] | None = None,
        risk_category: str | None = None,
        alert_type: str | None = None,
    ) -> Alert:
        """Generate an alert from directly-provided data (no cross-service calls).

        Useful for testing and for event-driven triggers.
        """
        validate_monitor_request(profile_id)

        deviations = compute_income_deviations(
            expected_incomes or [], actual_incomes or [],
        )

        stress = compute_repayment_stress(
            dti_ratio=dti_ratio,
            missed_payments=missed_payments,
            days_overdue_avg=days_overdue_avg,
            recent_surplus_trend=recent_surplus_trend or [],
        )

        risk_cat = RiskCategory(risk_category) if risk_category else None
        a_type = AlertType(alert_type) if alert_type else None

        alert = build_alert(
            profile_id=profile_id,
            stress=stress,
            deviations=deviations,
            risk_category=risk_cat,
            alert_type=a_type,
        )

        await self._repo.save_alert(alert)

        await self._events.publish(DomainEvent(
            event_type="alert.generated",
            aggregate_id=alert.alert_id,
            payload={
                "profile_id": profile_id,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
            },
        ))

        return alert

    async def escalate_alert(
        self, alert_id: str, new_severity: str, reason: str,
    ) -> Alert:
        """Escalate an existing alert to a higher severity (Req 5.3)."""
        from services.shared.models import AlertSeverity

        alert = await self._repo.find_alert_by_id(alert_id)
        if alert is None:
            raise ValueError(f"Alert {alert_id} not found")

        alert.escalate(AlertSeverity(new_severity), reason)
        await self._repo.save_alert(alert)

        await self._events.publish(DomainEvent(
            event_type="alert.escalated",
            aggregate_id=alert.alert_id,
            payload={
                "profile_id": alert.profile_id,
                "new_severity": new_severity,
                "reason": reason,
            },
        ))

        return alert

    async def acknowledge_alert(self, alert_id: str) -> Alert:
        """Mark an alert as acknowledged."""
        alert = await self._repo.find_alert_by_id(alert_id)
        if alert is None:
            raise ValueError(f"Alert {alert_id} not found")

        alert.acknowledge()
        await self._repo.save_alert(alert)
        return alert

    async def resolve_alert(self, alert_id: str) -> Alert:
        """Mark an alert as resolved."""
        alert = await self._repo.find_alert_by_id(alert_id)
        if alert is None:
            raise ValueError(f"Alert {alert_id} not found")

        alert.resolve()
        await self._repo.save_alert(alert)
        return alert

    # -----------------------------------------------------------------------
    # Queries — Alerts
    # -----------------------------------------------------------------------
    async def get_alert(self, alert_id: str) -> Alert | None:
        return await self._repo.find_alert_by_id(alert_id)

    async def get_alerts_for_profile(
        self, profile_id: ProfileId, limit: int = 50,
    ) -> list[Alert]:
        return await self._repo.find_alerts_by_profile(profile_id, limit)

    async def get_active_alerts(self, profile_id: ProfileId) -> list[Alert]:
        return await self._repo.find_active_alerts(profile_id)

    # -----------------------------------------------------------------------
    # Scenario Simulation
    # -----------------------------------------------------------------------
    async def run_scenario(
        self, profile_id: ProfileId, params: ScenarioParameters,
    ) -> SimulationResult:
        """Run a single scenario simulation against the profile's cash flow forecast.

        Cross-service: fetches baseline projections from Cash Flow service.
        Req 6.1, 6.2, 6.3, 6.4, 6.5.
        """
        validate_scenario_params(params)

        # Get baseline from cash flow service
        projections = await self._cashflow.get_latest_forecast_projections(profile_id)
        if not projections:
            raise ValueError(f"No cash flow forecast found for profile {profile_id}")

        capacity = await self._cashflow.get_repayment_capacity(profile_id)  # noqa: F841
        household_expense = await self._profiles.get_household_expense(profile_id)
        exposure = await self._loans.get_debt_exposure(profile_id)

        result = simulate_scenario(
            baseline_projections=projections,
            params=params,
            existing_monthly_obligations=exposure.get("monthly_obligations", 0.0),
            household_monthly_expense=household_expense,
        )
        # Set profile_id on result
        object.__setattr__(result, "profile_id", profile_id)

        # Monte Carlo enhancement (flag-gated: SCENARIO_ML_ENABLED=true)
        if os.getenv("SCENARIO_ML_ENABLED", "false").lower() == "true":
            from services.early_warning.ml import scenario_model as _ml_sc  # lazy

            _annual_income = sum(inf for _, _, inf, _ in projections) if projections else 0.0
            _profile_info  = await self._profiles.get_household_expense(profile_id)
            _mc = _ml_sc.simulate(
                annual_income=_annual_income,
                land_holding_acres=2.0,
                weather_adjustment=params.weather_adjustment,
                market_price_change_pct=params.market_price_change_pct,
                income_reduction_pct=params.income_reduction_pct,
                duration_months=params.duration_months,
                monthly_obligations=exposure.get("monthly_obligations", 0.0),
                household_expense=household_expense,
                start_month=projections[0][0] if projections else 1,
                n_simulations=1_000,
            )
            if _mc is not None:
                # Tighten risk level if MC says most simulations end in deficit
                if _mc["months_in_deficit_p50"] >= 4:
                    result.overall_risk_level = "CRITICAL"
                elif _mc["months_in_deficit_p50"] >= 2:
                    result.overall_risk_level = "HIGH"
                # Attach MC distribution as an ad-hoc attribute for API consumers
                result.mc_distribution = _mc

        await self._repo.save_simulation(result)

        await self._events.publish(DomainEvent(
            event_type="scenario.simulated",
            aggregate_id=result.simulation_id,
            payload={
                "profile_id": profile_id,
                "scenario_type": params.scenario_type,
                "risk_level": result.overall_risk_level,
            },
        ))

        return result

    async def run_scenario_direct(
        self,
        profile_id: ProfileId,
        params: ScenarioParameters,
        baseline_projections: list[tuple[int, int, float, float]],
        existing_obligations: float = 0.0,
        household_expense: float = 5000.0,
    ) -> SimulationResult:
        """Run a scenario with directly-provided baseline data (no cross-service calls)."""
        validate_scenario_params(params)

        if not baseline_projections:
            raise ValueError("At least one baseline projection is required")

        result = simulate_scenario(
            baseline_projections=baseline_projections,
            params=params,
            existing_monthly_obligations=existing_obligations,
            household_monthly_expense=household_expense,
        )
        object.__setattr__(result, "profile_id", profile_id)

        await self._repo.save_simulation(result)

        await self._events.publish(DomainEvent(
            event_type="scenario.simulated",
            aggregate_id=result.simulation_id,
            payload={
                "profile_id": profile_id,
                "scenario_type": params.scenario_type,
                "risk_level": result.overall_risk_level,
            },
        ))

        return result

    async def compare_scenarios(
        self,
        profile_id: ProfileId,
        scenarios: list[ScenarioParameters],
    ) -> list[SimulationResult]:
        """Run multiple scenarios and return for side-by-side comparison (Req 6.1)."""
        validate_multi_scenario_request(scenarios)

        projections = await self._cashflow.get_latest_forecast_projections(profile_id)
        if not projections:
            raise ValueError(f"No cash flow forecast found for profile {profile_id}")

        exposure = await self._loans.get_debt_exposure(profile_id)
        household_expense = await self._profiles.get_household_expense(profile_id)

        results = run_multi_scenario_comparison(
            baseline_projections=projections,
            scenarios=scenarios,
            existing_obligations=exposure.get("monthly_obligations", 0.0),
            household_expense=household_expense,
        )

        for result in results:
            object.__setattr__(result, "profile_id", profile_id)
            await self._repo.save_simulation(result)

        return results

    async def compare_scenarios_direct(
        self,
        profile_id: ProfileId,
        scenarios: list[ScenarioParameters],
        baseline_projections: list[tuple[int, int, float, float]],
        existing_obligations: float = 0.0,
        household_expense: float = 5000.0,
    ) -> list[SimulationResult]:
        """Compare scenarios with directly-provided data."""
        validate_multi_scenario_request(scenarios)

        if not baseline_projections:
            raise ValueError("At least one baseline projection is required")

        results = run_multi_scenario_comparison(
            baseline_projections=baseline_projections,
            scenarios=scenarios,
            existing_obligations=existing_obligations,
            household_expense=household_expense,
        )

        for result in results:
            object.__setattr__(result, "profile_id", profile_id)
            await self._repo.save_simulation(result)

        return results

    # -----------------------------------------------------------------------
    # Queries — Simulations
    # -----------------------------------------------------------------------
    async def get_simulation(self, simulation_id: str) -> SimulationResult | None:
        return await self._repo.find_simulation_by_id(simulation_id)

    async def get_simulation_history(
        self, profile_id: ProfileId, limit: int = 20,
    ) -> list[SimulationResult]:
        return await self._repo.find_simulations_by_profile(profile_id, limit)
